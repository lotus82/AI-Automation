"""ARI: REST (httpx) + WebSocket события; мост SIP → RTP → Pipecat.

# TODO: Исходящий вызов (Originate) и очередь портов под высокую нагрузку.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal, cast
from urllib.parse import urlparse, urlunparse
from uuid import UUID

import httpx
import websockets
from loguru import logger
from redis.asyncio import Redis

from src.core.config import Settings
from src.domain.entities import TrainingScenario
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.repositories import SqlAlchemyTrainingScenarioRepository
from src.infrastructure.sip_call_redis import (
    analyst_call_meta_redis_key,
    encode_analyst_call_meta,
    encode_sip_call_map,
    sip_call_map_redis_key,
)
from src.infrastructure.training_session_redis import (
    decode_trainer_meta,
    trainer_session_redis_key,
)
from src.infrastructure.voice.asterisk_rtp_transport import (
    AsteriskRtpPipecatTransport,
    PipecatAsteriskRtpVoiceTransport,
)
from src.infrastructure.voice.sip_pipecat_adapter import build_telephony_service
from src.infrastructure.voice.voice_session import (
    run_voice_pipeline_session,
    schedule_analyze_after_voice,
)


def _http_to_ws_wsurl(asterisk_url: str) -> str:
    """http://host:8088/ari → ws://host:8088/ari"""
    p = urlparse(asterisk_url.strip())
    scheme = "wss" if p.scheme == "https" else "ws"
    return urlunparse((scheme, p.netloc, p.path, "", "", "")).rstrip("/")


class AriRestClient:
    """Минимальный async-клиент ARI (Basic auth)."""

    def __init__(self, *, base_url: str, user: str, password: str) -> None:
        root = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=root,
            auth=(user, password),
            timeout=httpx.Timeout(60.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_external_media(
        self,
        *,
        app: str,
        external_host: str,
        fmt: str = "ulaw",
        direction: str = "both",
    ) -> dict[str, Any]:
        """POST /channels/externalMedia — UDP RTP на host:port (не WebSocket)."""
        r = await self._client.post(
            "/channels/externalMedia",
            params={
                "app": app,
                "external_host": external_host,
                "format": fmt,
                "direction": direction,
            },
        )
        r.raise_for_status()
        return r.json()

    async def create_mixing_bridge(self) -> str:
        r = await self._client.post("/bridges", json={"type": "mixing"})
        r.raise_for_status()
        return str(r.json()["id"])

    async def bridge_add_channel(self, bridge_id: str, channel_id: str) -> None:
        r = await self._client.post(
            f"/bridges/{bridge_id}/addChannel",
            params={"channel": channel_id},
        )
        r.raise_for_status()

    async def delete_bridge(self, bridge_id: str) -> None:
        try:
            r = await self._client.delete(f"/bridges/{bridge_id}")
            if r.status_code not in (404, 204) and not r.is_success:
                r.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("ARI delete_bridge {}: {}", bridge_id, e)

    async def hangup_channel(self, channel_id: str) -> None:
        try:
            r = await self._client.delete(f"/channels/{channel_id}")
            if r.status_code not in (404, 204) and not r.is_success:
                r.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("ARI hangup_channel {}: {}", channel_id, e)

    async def originate_channel(
        self,
        *,
        endpoint: str,
        app: str,
        app_args: str | None = None,
        caller_id: str | None = None,
    ) -> dict[str, Any]:
        """Исходящий вызов в Stasis (например Local/xxx или PJSIP/добавочный)."""
        body: dict[str, Any] = {"endpoint": endpoint.strip(), "app": app.strip()}
        if app_args:
            body["appArgs"] = app_args.strip()
        if caller_id:
            body["callerId"] = caller_id.strip()
        r = await self._client.post("/channels", json=body)
        r.raise_for_status()
        return r.json()


@dataclass
class _RtpPortPool:
    """Пул UDP-портов на контейнере web для externalMedia."""

    lo: int
    hi: int
    _avail: list[int] = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self._avail = list(range(self.lo, self.hi + 1))

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[int]:
        async with self._lock:
            if not self._avail:
                raise RuntimeError("Исчерпан пул RTP-портов (увеличьте ASTERISK_RTP_PORT_*)")
            port = self._avail.pop(0)
        try:
            yield port
        finally:
            async with self._lock:
                self._avail.append(port)
                self._avail.sort()


@dataclass
class _ActiveLeg:
    """Связка каналов одного входящего звонка."""

    sip_channel_id: str
    ext_channel_id: str
    bridge_id: str
    session_id: str
    rtp: AsteriskRtpPipecatTransport


def _is_pjsip_inbound_channel(channel: dict[str, Any]) -> bool:
    name = str(channel.get("name") or "")
    # Канал externalMedia часто не PJSIP — не обрабатываем повторный StasisStart.
    return name.startswith("PJSIP/")


async def _run_stasis_inbound_call(
    *,
    event: dict[str, Any],
    settings: Settings,
    redis: Redis,
    rest: AriRestClient,
    port_pool: _RtpPortPool,
    stasis_app: str,
    index: dict[str, _ActiveLeg],
    inflight: set[str],
) -> None:
    channel = event.get("channel") or {}
    if not _is_pjsip_inbound_channel(channel):
        return
    channel_id = str(channel.get("id") or "")
    if not channel_id:
        return
    if channel_id in inflight:
        return
    inflight.add(channel_id)

    caller = channel.get("caller") or {}
    caller_num = str(caller.get("number") or "").strip()

    st_args = list(event.get("args") or [])
    trainer_mode = len(st_args) >= 3 and str(st_args[0]).strip().lower() == "trainer"
    training_scenario: TrainingScenario | None = None
    voice_mode: str = "consultant"

    if trainer_mode:
        session_id = str(st_args[1]).strip()
        if not session_id:
            logger.warning("ARI: trainer StasisStart без session_id")
            inflight.discard(channel_id)
            return
        try:
            scenario_uuid = UUID(str(st_args[2]).strip())
        except ValueError:
            logger.warning("ARI: trainer некорректный scenario_id в appArgs")
            inflight.discard(channel_id)
            return
        raw_trainer = await redis.get(trainer_session_redis_key(session_id))
        manager_phone = ""
        if raw_trainer:
            decoded = decode_trainer_meta(raw_trainer)
            if decoded:
                _sc_redis, manager_phone = decoded
        async with AsyncSessionLocal() as db:
            try:
                repo = SqlAlchemyTrainingScenarioRepository(db)
                training_scenario = await repo.get_by_id(scenario_uuid)
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        if training_scenario is None:
            logger.error("ARI: сценарий тренажёра {} не найден", scenario_uuid)
            inflight.discard(channel_id)
            try:
                await rest.hangup_channel(channel_id)
            except Exception:
                pass
            return
        voice_mode = "trainer_client"
        remote_phone = (manager_phone or caller_num or "").strip()
        direction = "outbound_trainer"
    else:
        telephony = build_telephony_service(settings)
        session_id = await telephony.handle_inbound_call(channel_id)
        remote_phone = caller_num
        direction = "inbound"

    ttl = settings.chat_memory_ttl_seconds
    await redis.setex(
        analyst_call_meta_redis_key(session_id),
        ttl,
        encode_analyst_call_meta(direction=direction, remote_phone=remote_phone),
    )
    await redis.setex(
        sip_call_map_redis_key(channel_id),
        ttl,
        encode_sip_call_map(session_id=session_id),
    )

    host = (settings.asterisk_rtp_advertise_host or "web").strip()

    try:
        async with port_pool.acquire() as rtp_port:
            rtp = AsteriskRtpPipecatTransport(rtp_port)
            await rtp.open_udp_socket()
            external_host = f"{host}:{rtp_port}"
            try:
                ext = await rest.create_external_media(
                    app=stasis_app,
                    external_host=external_host,
                    fmt="ulaw",
                    direction="both",
                )
                ext_id = str(ext.get("id") or "")
                bridge_id = await rest.create_mixing_bridge()
                await rest.bridge_add_channel(bridge_id, channel_id)
                await rest.bridge_add_channel(bridge_id, ext_id)

                leg = _ActiveLeg(
                    sip_channel_id=channel_id,
                    ext_channel_id=ext_id,
                    bridge_id=bridge_id,
                    session_id=session_id,
                    rtp=rtp,
                )
                index[channel_id] = leg
                index[ext_id] = leg

                logger.info(
                    "ARI: мост SIP {} ↔ RTP {}, session_id={}, mode={}, ext={}",
                    channel_id,
                    external_host,
                    session_id,
                    voice_mode,
                    ext_id,
                )

                voice = PipecatAsteriskRtpVoiceTransport(rtp)
                try:
                    await run_voice_pipeline_session(
                        session_id=session_id,
                        voice_transport=voice,
                        redis=redis,
                        settings=settings,
                        voice_mode=cast(
                            Literal["consultant", "trainer_client"],
                            voice_mode,
                        ),
                        training_scenario=training_scenario,
                    )
                finally:
                    schedule_analyze_after_voice(session_id)
                    await rest.delete_bridge(bridge_id)
                    index.pop(channel_id, None)
                    index.pop(ext_id, None)
            except Exception:
                logger.exception("ARI: сбой обработки входящего {}", channel_id)
                index.pop(channel_id, None)
                raise
    finally:
        inflight.discard(channel_id)


async def _on_channel_destroyed(
    destroyed_id: str,
    index: dict[str, _ActiveLeg],
) -> None:
    leg = index.pop(destroyed_id, None)
    if leg is None:
        return
    index.pop(leg.sip_channel_id, None)
    index.pop(leg.ext_channel_id, None)
    logger.info("ARI: ChannelDestroyed {} — останавливаем RTP/Pipecat", destroyed_id)
    try:
        await leg.rtp.signal_disconnect()
    except Exception:
        logger.exception("signal_disconnect")


def _build_events_ws_uri(settings: Settings) -> str:
    base_ws = _http_to_ws_wsurl(settings.asterisk_url or "")
    user = settings.asterisk_ari_user or ""
    password = settings.asterisk_ari_password or ""
    app = settings.asterisk_stasis_app or "voice_ai_app"
    from urllib.parse import quote

    key = quote(f"{user}:{password}", safe="")
    return f"{base_ws}/events?api_key={key}&app={quote(app, safe='')}&subscribeAll=true"


async def run_ari_event_listener(
    settings: Settings,
    redis: Redis,
    stop: asyncio.Event,
) -> None:
    """Фоновая задача FastAPI: слушает ARI и поднимает Pipecat на входящих."""
    if not settings.asterisk_url or not settings.asterisk_ari_user or not settings.asterisk_ari_password:
        logger.info("ARI: отключено (нет ASTERISK_URL / учётных данных)")
        return

    uri = _build_events_ws_uri(settings)
    port_pool = _RtpPortPool(settings.asterisk_rtp_port_min, settings.asterisk_rtp_port_max)
    index: dict[str, _ActiveLeg] = {}
    inflight: set[str] = set()
    rest = AriRestClient(
        base_url=settings.asterisk_url,
        user=settings.asterisk_ari_user,
        password=settings.asterisk_ari_password,
    )

    try:
        while not stop.is_set():
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=60) as ws:
                    logger.info("ARI: WebSocket событий подключён")
                    await _consume_ari_ws(
                        ws,
                        settings=settings,
                        redis=redis,
                        rest=rest,
                        port_pool=port_pool,
                        index=index,
                        inflight=inflight,
                        stop=stop,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if stop.is_set():
                    break
                logger.warning("ARI: переподключение через 3 с после ошибки: {}", e)
                await asyncio.sleep(3.0)
    finally:
        await rest.aclose()


async def _consume_ari_ws(
    ws: Any,
    *,
    settings: Settings,
    redis: Redis,
    rest: AriRestClient,
    port_pool: _RtpPortPool,
    index: dict[str, _ActiveLeg],
    inflight: set[str],
    stop: asyncio.Event,
) -> None:
    stasis_app = settings.asterisk_stasis_app or "voice_ai_app"
    while not stop.is_set():
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        except websockets.ConnectionClosed:
            logger.warning("ARI: WebSocket закрыт")
            break
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        et = event.get("type")
        if et == "StasisStart":
            asyncio.create_task(
                _run_stasis_inbound_call(
                    event=event,
                    settings=settings,
                    redis=redis,
                    rest=rest,
                    port_pool=port_pool,
                    stasis_app=stasis_app,
                    index=index,
                    inflight=inflight,
                ),
                name=f"ari-stasis-{event.get('channel', {}).get('id', '?')}",
            )
        elif et == "ChannelDestroyed":
            ch = event.get("channel") or {}
            cid = str(ch.get("id") or "")
            if cid:
                await _on_channel_destroyed(cid, index)
