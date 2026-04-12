import { useCallback, useEffect, useId, useRef, useState } from "react";
import protobuf from "protobufjs";
import api from "../../api/client.js";

const TARGET_INPUT_HZ = 16000;
const DEFAULT_OUTPUT_HZ = 24000;
const SPEAKING_RESET_MS = 400;
const FRAMES_PROTO_URL = "/static/proto/frames.proto";

function nowLine() {
  return new Date().toISOString().replace("T", " ").slice(0, 19);
}

function downsampleToInt16(inputFloat32, inputRate, outputRate) {
  let i;
  if (inputRate === outputRate) {
    const same = new Int16Array(inputFloat32.length);
    for (i = 0; i < inputFloat32.length; i++) {
      const x = Math.max(-1, Math.min(1, inputFloat32[i]));
      same[i] = x < 0 ? x * 0x8000 : x * 0x7fff;
    }
    return same;
  }
  const ratio = inputRate / outputRate;
  const outLen = Math.max(1, Math.floor(inputFloat32.length / ratio));
  const out = new Int16Array(outLen);
  for (i = 0; i < outLen; i++) {
    const srcPos = i * ratio;
    const i0 = Math.floor(srcPos);
    const frac = srcPos - i0;
    const s0 = inputFloat32[i0] || 0;
    const s1 = inputFloat32[i0 + 1] !== undefined ? inputFloat32[i0 + 1] : s0;
    const s = s0 * (1 - frac) + s1 * frac;
    const c = Math.max(-1, Math.min(1, s));
    out[i] = c < 0 ? c * 0x8000 : c * 0x7fff;
  }
  return out;
}

const STATUS_LABELS = {
  disconnected: "Отключено",
  connected: "Подключено",
  listening: "Слушаем",
  speaking: "Говорит агент",
  error: "Ошибка",
};

function statusBadgeClass(state) {
  const base =
    "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium";
  const map = {
    disconnected: "border-slate-600 bg-slate-800/80 text-slate-300",
    connected: "border-sky-500/40 bg-sky-500/10 text-sky-200",
    listening: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
    speaking: "border-violet-500/40 bg-violet-500/10 text-violet-200",
    error: "border-red-500/40 bg-red-500/10 text-red-200",
  };
  return `${base} ${map[state] || map.disconnected}`;
}

function statusDotClass(state) {
  const map = {
    disconnected: "bg-slate-500",
    connected: "bg-sky-400",
    listening: "animate-pulse bg-emerald-400",
    speaking: "bg-violet-400",
    error: "bg-red-400",
  };
  return `h-2 w-2 rounded-full ${map[state] || map.disconnected}`;
}

/** Тест голоса: WebSocket /voice/stream, Pipecat Protobuf (встраивается в «Интеграции» → «Телефония»). */
export function VoiceTelephonyTestPanel() {
  const idBase = useId();

  const [voiceStatus, setVoiceStatus] = useState("disconnected");
  const [mode, setMode] = useState("consultant");
  const [scenarioId, setScenarioId] = useState("");
  const [managerName, setManagerName] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [scenarios, setScenarios] = useState([]);
  const [scenariosError, setScenariosError] = useState(false);
  const [inCall, setInCall] = useState(false);
  const [starting, setStarting] = useState(false);
  const [transcriptLines, setTranscriptLines] = useState([]);
  const [logLines, setLogLines] = useState([]);

  const logIdRef = useRef(0);
  const transcriptIdRef = useRef(0);

  const wsRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const playbackContextRef = useRef(null);
  const processorRef = useRef(null);
  const sourceNodeRef = useRef(null);
  const frameTypeRef = useRef(null);
  const protoRootRef = useRef(null);
  const protoLoadPromiseRef = useRef(null);
  const nextPlayTimeRef = useRef(0);
  const speakingTimerRef = useRef(null);

  const transcriptEndRef = useRef(null);
  const logEndRef = useRef(null);

  const appendLog = useCallback((msg, level = "info") => {
    const id = ++logIdRef.current;
    setLogLines((prev) => [...prev, { id, ts: nowLine(), msg, level }]);
  }, []);

  const appendUserTranscript = useCallback((text) => {
    const t = String(text || "").trim();
    if (!t) return;
    const id = ++transcriptIdRef.current;
    setTranscriptLines((prev) => [...prev, { id, text: t }]);
  }, []);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcriptLines]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logLines]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/scenarios");
        if (cancelled) return;
        const list = Array.isArray(data) ? data : [];
        setScenarios(list);
        setScenariosError(false);
        if (list.length && !scenarioId) {
          setScenarioId(String(list[0].id));
        }
      } catch {
        if (!cancelled) {
          setScenarios([]);
          setScenariosError(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const ensureProtobuf = useCallback(async () => {
    if (frameTypeRef.current) return;
    if (!protoLoadPromiseRef.current) {
      protoLoadPromiseRef.current = protobuf.load(FRAMES_PROTO_URL).then((root) => {
        protoRootRef.current = root;
        frameTypeRef.current = root.lookupType("pipecat.Frame");
        appendLog("Схема Protobuf загружена", "info");
      });
    }
    await protoLoadPromiseRef.current;
  }, [appendLog]);

  const markSpeaking = useCallback(() => {
    setVoiceStatus("speaking");
    if (speakingTimerRef.current) clearTimeout(speakingTimerRef.current);
    speakingTimerRef.current = setTimeout(() => {
      speakingTimerRef.current = null;
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        setVoiceStatus("listening");
      }
    }, SPEAKING_RESET_MS);
  }, []);

  const playPcmChunk = useCallback(
    (audioBytes, sampleRate) => {
      const playbackContext = playbackContextRef.current;
      if (!playbackContext || !audioBytes || audioBytes.length < 2) return;
      const rate = sampleRate || DEFAULT_OUTPUT_HZ;
      const u8 = audioBytes instanceof Uint8Array ? audioBytes : new Uint8Array(audioBytes);
      const len = Math.floor(u8.byteLength / 2);
      if (len === 0) return;
      const samples = new Int16Array(len);
      for (let j = 0; j < len; j++) {
        samples[j] = u8[j * 2] | (u8[j * 2 + 1] << 8);
      }
      const buffer = playbackContext.createBuffer(1, samples.length, rate);
      const ch = buffer.getChannelData(0);
      for (let j = 0; j < samples.length; j++) {
        ch[j] = samples[j] / 32768;
      }
      const src = playbackContext.createBufferSource();
      src.buffer = buffer;
      src.connect(playbackContext.destination);
      let t = playbackContext.currentTime;
      if (nextPlayTimeRef.current < t) nextPlayTimeRef.current = t;
      try {
        src.start(nextPlayTimeRef.current);
        nextPlayTimeRef.current += buffer.duration;
      } catch (e) {
        appendLog(`Не удалось запустить воспроизведение: ${e.message}`, "warn");
      }
      markSpeaking();
    },
    [appendLog, markSpeaking]
  );

  const handleBinaryFrame = useCallback(
    (arrayBuffer) => {
      const FrameType = frameTypeRef.current;
      if (!FrameType) return;
      try {
        const uint8 = new Uint8Array(arrayBuffer);
        const decoded = FrameType.decode(uint8);
        if (decoded.audio) {
          const a = decoded.audio;
          playPcmChunk(a.audio, a.sampleRate);
          return;
        }
        if (decoded.transcription && decoded.transcription.text) {
          appendUserTranscript(String(decoded.transcription.text).trim());
          return;
        }
        if (decoded.text && decoded.text.text) {
          appendLog(`Текст (кадр): ${decoded.text.text}`, "info");
        }
      } catch (e) {
        appendLog(`Ошибка разбора Protobuf: ${e.message}`, "err");
      }
    },
    [appendLog, appendUserTranscript, playPcmChunk]
  );

  const cleanupAudioNoWs = useCallback(() => {
    if (speakingTimerRef.current) {
      clearTimeout(speakingTimerRef.current);
      speakingTimerRef.current = null;
    }
    nextPlayTimeRef.current = 0;
    if (processorRef.current) {
      try {
        processorRef.current.disconnect();
      } catch {
        /* ignore */
      }
      processorRef.current = null;
    }
    if (sourceNodeRef.current) {
      try {
        sourceNodeRef.current.disconnect();
      } catch {
        /* ignore */
      }
      sourceNodeRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (playbackContextRef.current) {
      playbackContextRef.current.close().catch(() => {});
      playbackContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
  }, []);

  const cleanupAfterSocketClosed = useCallback(() => {
    cleanupAudioNoWs();
    wsRef.current = null;
    setInCall(false);
    setVoiceStatus("disconnected");
  }, [cleanupAudioNoWs]);

  const endCall = useCallback(() => {
    cleanupAudioNoWs();
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {
        /* ignore */
      }
      wsRef.current = null;
    }
    setInCall(false);
    setStarting(false);
    setVoiceStatus("disconnected");
    setTranscriptLines([]);
    appendLog("Звонок завершён, микрофон и сокет освобождены", "info");
  }, [appendLog, cleanupAudioNoWs]);

  /** Без setState — только при размонтировании страницы (избегаем предупреждений React). */
  useEffect(() => {
    return () => {
      if (speakingTimerRef.current) {
        clearTimeout(speakingTimerRef.current);
        speakingTimerRef.current = null;
      }
      nextPlayTimeRef.current = 0;
      if (processorRef.current) {
        try {
          processorRef.current.disconnect();
        } catch {
          /* ignore */
        }
        processorRef.current = null;
      }
      if (sourceNodeRef.current) {
        try {
          sourceNodeRef.current.disconnect();
        } catch {
          /* ignore */
        }
        sourceNodeRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
      if (playbackContextRef.current) {
        playbackContextRef.current.close().catch(() => {});
        playbackContextRef.current = null;
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
      }
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          /* ignore */
        }
        wsRef.current = null;
      }
    };
  }, []);

  const bootLoggedRef = useRef(false);

  const buildWsUrl = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const params = new URLSearchParams();
    const sid = sessionId.trim();
    if (sid) params.set("session_id", sid);
    params.set("mode", mode);
    if (mode === "trainer") {
      if (scenarioId) params.set("scenario_id", scenarioId);
    }
    const mgr = managerName.trim();
    if (mgr) params.set("manager_name", mgr);
    const qs = params.toString();
    return `${proto}//${host}/voice/stream${qs ? `?${qs}` : ""}`;
  }, [sessionId, mode, scenarioId, managerName]);

  const startAudioPipeline = useCallback(() => {
    const mediaStream = mediaStreamRef.current;
    const ws = wsRef.current;
    if (!mediaStream || !ws || ws.readyState !== WebSocket.OPEN) return;

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const audioContext = new AudioCtx();
    audioContextRef.current = audioContext;
    const inRate = audioContext.sampleRate;

    const sourceNode = audioContext.createMediaStreamSource(mediaStream);
    sourceNodeRef.current = sourceNode;
    const bufferSize = 4096;
    const processor = audioContext.createScriptProcessor(bufferSize, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (ev) => {
      const socket = wsRef.current;
      const Ft = frameTypeRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN || !Ft) return;
      const input = ev.inputBuffer.getChannelData(0);
      const copy = new Float32Array(input.length);
      copy.set(input);
      const pcm16 = downsampleToInt16(copy, inRate, TARGET_INPUT_HZ);
      try {
        const audioInner = {
          id: 0,
          name: "",
          audio: new Uint8Array(pcm16.buffer, pcm16.byteOffset, pcm16.byteLength),
          sampleRate: TARGET_INPUT_HZ,
          numChannels: 1,
        };
        const payload = { audio: audioInner };
        const err = Ft.verify(payload);
        if (err) throw new Error(err);
        const message = Ft.create(payload);
        socket.send(Ft.encode(message).finish());
      } catch (e) {
        appendLog(`Ошибка кодирования кадра: ${e.message}`, "err");
      }
    };

    const mute = audioContext.createGain();
    mute.gain.value = 0;
    sourceNode.connect(processor);
    processor.connect(mute);
    mute.connect(audioContext.destination);

    const playbackContext = new AudioCtx();
    playbackContextRef.current = playbackContext;
    nextPlayTimeRef.current = playbackContext.currentTime;

    setVoiceStatus("listening");
    appendLog(`Аудио: ввод ${inRate} Гц, отправка ${TARGET_INPUT_HZ} Гц PCM`, "info");
  }, [appendLog]);

  const startCall = useCallback(async () => {
    setStarting(true);
    setTranscriptLines([]);
    setVoiceStatus("connected");
    appendLog("Запрос доступа к микрофону…", "info");

    if (mode === "trainer" && !scenarioId) {
      appendLog("В режиме тренажёра выберите сценарий из списка.", "err");
      setVoiceStatus("error");
      setStarting(false);
      return;
    }

    try {
      await ensureProtobuf();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const url = buildWsUrl();
      appendLog(`Подключение к ${url}`, "info");
      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        setVoiceStatus("connected");
        appendLog("WebSocket открыт", "info");
        setInCall(true);
        setStarting(false);
        startAudioPipeline();
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          handleBinaryFrame(event.data);
        } else {
          appendLog(`Текстовое сообщение: ${String(event.data)}`, "info");
        }
      };

      ws.onerror = () => {
        appendLog("Ошибка WebSocket", "err");
        setVoiceStatus("error");
      };

      ws.onclose = (ev) => {
        appendLog(
          `WebSocket закрыт (код ${ev.code}${ev.reason ? `, ${ev.reason}` : ""})`,
          "warn"
        );
        setStarting(false);
        setInCall(false);
        cleanupAfterSocketClosed();
      };
    } catch (e) {
      appendLog(`Не удалось начать звонок: ${e?.message || e}`, "err");
      setVoiceStatus("error");
      setStarting(false);
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
      }
    }
  }, [
    mode,
    scenarioId,
    appendLog,
    ensureProtobuf,
    buildWsUrl,
    startAudioPipeline,
    handleBinaryFrame,
    cleanupAfterSocketClosed,
  ]);

  useEffect(() => {
    if (bootLoggedRef.current) return;
    bootLoggedRef.current = true;
    appendLog("Готов к тесту. Нажмите «Начать звонок» (нужны localhost или HTTPS).", "info");
  }, [appendLog]);

  const showScenario = mode === "trainer";
  const trainerScenarioInvalid = mode === "trainer" && !scenarioId;

  return (
    <div className="w-full min-w-0 space-y-6">
      <div>
        <h2 className="flex items-center gap-2 text-xl font-semibold text-white">
          <span className="text-emerald-400" aria-hidden>
            ●
          </span>
          Тест голосового агента
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          Подключение к <code className="rounded bg-slate-800 px-1.5 py-0.5 text-emerald-300">/voice/stream</code> через
          Nginx (тот же хост): Pipecat Protobuf, микрофон → PCM 16 kHz → WebSocket, воспроизведение ответа (PCM с
          сервера, обычно 24 kHz). Нужны ключи Deepgram и TTS (см. README). В режиме{" "}
          <strong className="text-slate-300">Тренажёр</strong> ИИ играет роль клиента по выбранному сценарию; после
          звонка оценку ставит тренер (LLM).
        </p>
      </div>

      <div
        className="rounded-2xl border border-slate-700/80 bg-slate-900/50 p-5 shadow-lg backdrop-blur-sm"
        id={`${idBase}-voice-tester`}
      >
        <div className="mb-4">
          <div className={statusBadgeClass(voiceStatus)} data-state={voiceStatus}>
            <span className={statusDotClass(voiceStatus)} aria-hidden />
            <span>{STATUS_LABELS[voiceStatus] || voiceStatus}</span>
          </div>
        </div>

        <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:flex-wrap">
          <div className="min-w-[200px] flex-1">
            <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor={`${idBase}-mode`}>
              Режим
            </label>
            <select
              id={`${idBase}-mode`}
              className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              disabled={inCall || starting}
              aria-label="Режим работы агента"
            >
              <option value="consultant">Консультант (ИИ — продавец)</option>
              <option value="trainer">Тренажёр (ИИ — клиент)</option>
            </select>
          </div>

          {showScenario && (
            <div className="min-w-[200px] flex-1">
              <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor={`${idBase}-scenario`}>
                Сценарий
              </label>
              <select
                id={`${idBase}-scenario`}
                className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
                value={scenarioId}
                onChange={(e) => setScenarioId(e.target.value)}
                disabled={inCall || starting}
                aria-label="Сценарий тренажёра"
              >
                {scenariosError && <option value="">— Ошибка загрузки /api/scenarios —</option>}
                {!scenariosError && scenarios.length === 0 && (
                  <option value="">— Нет сценариев — создайте в «ИИ-тренер» → «Сценарии»</option>
                )}
                {!scenariosError &&
                  scenarios.map((s) => (
                    <option key={String(s.id)} value={String(s.id)}>
                      {s.title}
                    </option>
                  ))}
              </select>
            </div>
          )}
        </div>

        <div className="mb-4">
          <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor={`${idBase}-manager`}>
            Имя менеджера (для отчёта тренера, опционально)
          </label>
          <input
            id={`${idBase}-manager`}
            type="text"
            name="manager_name"
            placeholder="Например, Иванов А."
            autoComplete="name"
            className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
            value={managerName}
            onChange={(e) => setManagerName(e.target.value)}
            disabled={inCall || starting}
          />
        </div>

        <div className="mb-6">
          <label className="mb-1 block text-xs font-medium text-slate-400" htmlFor={`${idBase}-session`}>
            Идентификатор сессии (опционально, UUID)
          </label>
          <input
            id={`${idBase}-session`}
            type="text"
            name="session_id"
            placeholder="Оставьте пустым — сервер создаст новый"
            autoComplete="off"
            className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            disabled={inCall || starting}
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => void startCall()}
            disabled={inCall || starting || trainerScenarioInvalid}
          >
            Начать звонок (микрофон)
          </button>
          <button
            type="button"
            className="rounded-lg bg-red-600/90 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40"
            onClick={endCall}
            disabled={!inCall && !starting}
          >
            Завершить звонок
          </button>
        </div>

        <h3 className="mt-8 text-lg font-semibold text-slate-200">Транскрипция разговора</h3>
        <p className="mt-1 text-xs text-slate-500">
          Фразы появляются после того, как распознавание речи отдаёт финальный текст (не побуквенно).
        </p>
        <div
          className="mt-3 max-h-64 overflow-y-auto rounded-xl border border-slate-700/80 bg-slate-950/60 p-3 text-sm"
          role="log"
          aria-live="polite"
          aria-relevant="additions"
        >
          {transcriptLines.length === 0 && (
            <p className="text-center text-slate-600 italic">Пока нет распознанных фраз…</p>
          )}
          {transcriptLines.map((line) => (
            <div key={line.id} className="mb-3 flex gap-3 border-b border-slate-800/80 pb-3 last:mb-0 last:border-0 last:pb-0">
              <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-emerald-500/90">Вы</span>
              <div className="text-slate-200">{line.text}</div>
            </div>
          ))}
          <span ref={transcriptEndRef} />
        </div>

        <h3 className="mt-8 text-lg font-semibold text-slate-200">Журнал</h3>
        <div
          className="mt-3 max-h-52 overflow-y-auto rounded-xl border border-slate-700/80 bg-slate-950/80 p-3 font-mono text-xs"
          aria-live="polite"
        >
          {logLines.map((line) => (
            <p
              key={line.id}
              className={
                line.level === "err"
                  ? "text-red-400"
                  : line.level === "warn"
                    ? "text-amber-400"
                    : "text-slate-400"
              }
            >
              [{line.ts}] {line.msg}
            </p>
          ))}
          <span ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
