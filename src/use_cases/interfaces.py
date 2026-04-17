"""Порты: репозитории и внешние сервисы (сценарии зависят только от абстракций)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.domain.entities import (
    CallAnalytics,
    CallRecord,
    ChatMessage,
    ChatSessionSummary,
    DialerQueueItem,
    DialerQueueStatus,
    KnowledgeItem,
    Lead,
    Schedule,
    ScheduledEvent,
    SystemSetting,
    TrainingScenario,
    TrainingSession,
)


@dataclass(frozen=True, slots=True)
class LLMToolCall:
    """Вызов инструмента, запрошенный моделью (OpenAI tool_calls)."""

    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class ISettingsRepository(ABC):
    """Порт динамических настроек (PostgreSQL + кэш Redis)."""

    @abstractmethod
    async def get_value(self, key: str) -> str | None:
        """Возвращает значение по ключу или None, если строки нет в БД."""

    @abstractmethod
    async def list_all(self) -> list[SystemSetting]:
        """Все настройки (для панели администрирования)."""

    @abstractmethod
    async def upsert_values(self, updates: dict[str, str]) -> None:
        """Обновляет значения существующих ключей; сбрасывает кэш Redis для них."""


class ILLMService(ABC):
    """Порт языковой модели для генерации ответа консультанта."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        context: list[str],
        *,
        history: list[dict] | None = None,
        system_prompt: str | None = None,
        client_timezone_id: str | None = None,
    ) -> str:
        """Формирует ответ с учётом RAG-контекста и опциональной истории (role/content).

        Если задан system_prompt — подставляется вместо персоны консультанта по умолчанию.
        ``client_timezone_id`` — IANA TZ с клиента (иначе пояс приложения).
        """

    @abstractmethod
    async def generate_sales_response_with_tools(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
    ) -> tuple[str | None, list[LLMToolCall]]:
        """Один шаг чата: текст ассистента (может быть пустым) и запрошенные вызовы инструментов."""

    @abstractmethod
    async def analyze_conversation_quality(self, transcript_text: str) -> tuple[int, str]:
        """ОКК: оценка диалога по шкале 1–10 и краткие рекомендации на русском."""

    @abstractmethod
    async def analyze_training_performance(
        self,
        transcript_text: str,
        *,
        scenario_title: str,
        objections_to_raise: str,
    ) -> tuple[int, str]:
        """Тренер продаж: оценка менеджера (реплики user) и отработка возражений сценария."""


class ICRMService(ABC):
    """Порт внешней CRM (Bitrix24 и др.): создание лида по контактам из диалога."""

    @abstractmethod
    async def create_lead(self, phone: str, name: str, description: str) -> str:
        """Создаёт лид; возвращает строковый идентификатор в CRM."""


class ISearchService(ABC):
    """Порт веб-поиска для инструмента LLM (сниппеты, без скрейпинга магазинов)."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 3) -> str:
        """Возвращает отформатированную строку с результатами или сообщение об ошибке."""


class IMaxVoiceSynthesizer(ABC):
    """Синтез речи для голосовых вложений MAX (SaluteSpeech и др.), без Pipecat-потока."""

    @abstractmethod
    async def synthesize_to_file(self, text: str) -> bytes:
        """Возвращает готовый аудиофайл (например WAV) целиком в памяти; пустые байты при отказе."""


class ITelephonyService(ABC):
    """Порт телефонии (SIP / мост к Pipecat). Без тяжёлых кодеков на CPU приложения."""

    @abstractmethod
    async def make_outbound_call(self, phone: str) -> str:
        """Инициирует исходящий вызов; возвращает внешний идентификатор вызова у провайдера/PBX."""

    @abstractmethod
    async def handle_inbound_call(self, call_id: str) -> str:
        """Регистрирует входящий вызов от АТС; возвращает session_id для Redis и пайплайна."""


class ICallRecordRepository(ABC):
    """Порт сохранения записей сессий и выборки для дашборда."""

    @abstractmethod
    async def save(self, record: CallRecord) -> CallRecord:
        """Сохраняет запись звонка/чата; возвращает сущность с id из БД."""

    @abstractmethod
    async def get_by_id(self, call_id: UUID) -> CallRecord | None:
        """Возвращает запись по id или None."""

    @abstractmethod
    async def update_audio_filename(self, call_id: UUID, filename: str | None) -> None:
        """Обновляет имя файла записи разговора (basename) или сбрасывает в None."""

    @abstractmethod
    async def save_analytics(self, row: CallAnalytics) -> CallAnalytics:
        """Сохраняет аналитику ОКК, привязанную к call_record_id."""

    @abstractmethod
    async def list_recent_with_analytics(
        self,
        *,
        limit: int = 100,
    ) -> list[tuple[CallRecord, CallAnalytics | None]]:
        """Последние записи с опциональной аналитикой (для таблицы в панели)."""

    @abstractmethod
    async def delete_by_id(self, call_id: UUID) -> bool:
        """Удаляет запись звонка и связанную аналитику (CASCADE); ``True`` если строка была."""


class IChatMemoryRepository(ABC):
    """Порт памяти диалога: Redis (кэш с TTL) + PostgreSQL (долговременная копия)."""

    @abstractmethod
    async def get_history(self, session_id: str, *, limit: int | None = None) -> list[dict]:
        """Сообщения с ключами role, content; опционально не более ``limit`` последних (для LLM)."""

    @abstractmethod
    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        user_display: str | None = None,
    ) -> None:
        """Сохраняет реплику; ``user_display`` — подпись пользователя из канала (MAX и т.д.), только для user."""


class IChatMonitoringPublisher(ABC):
    """Порт рассылки событий мониторинга чатов (WebSocket-дашборд)."""

    @abstractmethod
    async def publish_new_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        user_info: str | None = None,
        organization_id: UUID | None = None,
    ) -> None:
        """Событие новой реплики; ошибки доставки не должны ломать основной сценарий."""


class IChatSessionQueryRepository(ABC):
    """Порт выборок по сохранённым чатам для панели мониторинга."""

    @abstractmethod
    async def list_session_summaries(
        self,
        *,
        organization_id: UUID | None,
        limit: int = 200,
    ) -> list[ChatSessionSummary]:
        """Уникальные ``session_id`` с превью последнего сообщения в области организации.

        ``organization_id`` — только эта организация; ``None`` — только строки без организации (legacy).
        """

    @abstractmethod
    async def list_messages_chronological(
        self,
        session_id: str,
        *,
        organization_id: UUID | None,
    ) -> list[ChatMessage]:
        """Полная история сессии по времени в области организации."""

    @abstractmethod
    async def count_messages_in_session(self, session_id: str) -> int:
        """Число всех сохранённых сообщений сессии (любая организация)."""


class NullChatMonitoringPublisher(IChatMonitoringPublisher):
    """Заглушка для воркеров и тестов без WebSocket."""

    async def publish_new_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        user_info: str | None = None,
        organization_id: UUID | None = None,
    ) -> None:
        return None


class IEmbeddingService(ABC):
    """Порт сервиса векторизации текста (эмбеддинги для RAG)."""

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """Возвращает вектор фиксированной размерности для запроса."""


class ILeadRepository(ABC):
    """Порт доступа к персистентности лидов."""

    @abstractmethod
    async def save(self, lead: Lead) -> Lead:
        """Сохраняет новый лид; возвращает сущность с заполненными id и created_at."""


class ITrainingScenarioRepository(ABC):
    """Порт сценариев тренажёра."""

    @abstractmethod
    async def list_recent(self, *, limit: int = 100) -> list[TrainingScenario]:
        """Последние сценарии (новые сверху)."""

    @abstractmethod
    async def get_by_id(self, scenario_id: UUID) -> TrainingScenario | None:
        """Возвращает сценарий по UUID или None."""

    @abstractmethod
    async def save(self, scenario: TrainingScenario) -> TrainingScenario:
        """Создаёт сценарий; возвращает сущность с id из БД."""


class ITrainingSessionRepository(ABC):
    """Порт результатов тренировочных звонков."""

    @abstractmethod
    async def save(self, row: TrainingSession) -> TrainingSession:
        """Сохраняет оценку тренера; возвращает сущность с id из БД."""


class IDialerQueueRepository(ABC):
    """Порт очереди автообзвона."""

    @abstractmethod
    async def list_pending(self, *, limit: int = 50) -> list[DialerQueueItem]:
        """Записи со статусом pending по возрастанию scheduled_at."""

    @abstractmethod
    async def add_phones(self, phones: list[str]) -> int:
        """Пакетно добавляет номера (pending); возвращает число вставленных строк."""

    @abstractmethod
    async def set_status(self, item_id: UUID, status: DialerQueueStatus) -> None:
        """Обновляет статус строки очереди."""


class IProactiveDeliveryMessenger(ABC):
    """Порт исходящей доставки текста в чат MAX (без знания HTTP-деталей)."""

    @abstractmethod
    async def send_plain_text(self, chat_id: str, text: str) -> None:
        """Отправляет готовый текст в указанный числовой ``chat_id`` (строка)."""


class IScheduleRepository(ABC):
    """Порт расписаний и событий (фаза 18 — проактивные сообщения)."""

    @abstractmethod
    async def list_schedules(self, *, active_only: bool = False) -> list[Schedule]:
        """Список расписаний; при ``active_only`` — только с ``is_active``."""

    @abstractmethod
    async def get_by_id(self, schedule_id: UUID) -> Schedule | None:
        """Расписание по id или None."""

    @abstractmethod
    async def create(self, schedule: Schedule) -> Schedule:
        """Создаёт расписание (``id`` должен быть None); возвращает сущность с id."""

    @abstractmethod
    async def update(self, schedule: Schedule) -> Schedule | None:
        """Обновляет строку по ``schedule.id``; ``None`` если расписание не найдено."""

    @abstractmethod
    async def delete(self, schedule_id: UUID) -> bool:
        """Удаляет расписание и события (CASCADE); ``True`` если строка была."""

    @abstractmethod
    async def update_last_run_at(self, schedule_id: UUID, when: datetime) -> None:
        """Обновляет ``last_run_at`` (тип INTERVAL и после любой успешной отправки при необходимости)."""

    @abstractmethod
    async def list_pending_events(self, schedule_id: UUID) -> list[ScheduledEvent]:
        """События с ``is_processed=False`` (ежегодные и разовые до обработки)."""

    @abstractmethod
    async def add_events_bulk(self, schedule_id: UUID, events: list[ScheduledEvent]) -> int:
        """Пакетная вставка событий; ``schedule_id`` подставляется в каждую строку; возвращает число вставок."""

    @abstractmethod
    async def mark_event_processed(self, event_id: UUID) -> None:
        """Помечает событие обработанным (разовые DATABASE / REMINDER)."""

    @abstractmethod
    async def update_event_last_triggered(self, event_id: UUID, when: datetime) -> None:
        """Фиксирует время последнего срабатывания (ежегодные DATABASE)."""


class IKnowledgeRepository(ABC):
    """Порт доступа к элементам базы знаний (в т.ч. с вектором)."""

    @abstractmethod
    async def save(self, item: KnowledgeItem) -> KnowledgeItem:
        """Сохраняет элемент знаний; возвращает сущность с id из БД."""

    @abstractmethod
    async def search_similar(
        self,
        embedding: list[float],
        limit: int = 3,
    ) -> list[KnowledgeItem]:
        """Ищет наиболее близкие по вектору записи (pgvector)."""

    @abstractmethod
    async def list_recent(self, *, limit: int = 500) -> list[KnowledgeItem]:
        """Список элементов для админки (новые сверху)."""

    @abstractmethod
    async def delete_by_id(self, item_id: UUID) -> bool:
        """Удаляет запись; ``True`` если строка была удалена."""


class IVoiceTransport(ABC):
    """Порт транспорта голосового потока (вход/выход аудио и служебные кадры).

    Реализация живёт в инфраструктуре (Pipecat); тип процессоров намеренно Any,
    чтобы слой use_cases не импортировал pipecat.
    """

    @property
    @abstractmethod
    def pipecat_transport(self) -> Any:
        """Нативный Pipecat BaseTransport (события **on_client_disconnected** и т.д.)."""

    @abstractmethod
    def input_processor(self) -> Any:
        """Процессор входа: аудио и сообщения от клиента."""

    @abstractmethod
    def output_processor(self) -> Any:
        """Процессор выхода: синтезированное аудио и ответы клиенту."""
