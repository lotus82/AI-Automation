"""Настройки группового чата MAX: имя бота, id чата, дополнительный промпт.

Revision ID: 014_max_group_chat
Revises: 013_knowledge_desc

# TODO (рус.): Сейчас поддерживается один идентификатор группы (**MAX_GROUP_CHAT_ID**) и один дополнительный промпт.
#       В будущем можно вынести конфигурацию в отдельную таблицу **GroupChatConfig** (несколько групп с разными промптами и опционально разными @username).
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "014_max_group_chat"
down_revision = "013_knowledge_desc"
branch_labels = None
depends_on = None

_DEFAULT_GROUP_PROMPT = (
    "Ты находишься в групповом чате отдела продаж. "
    "Помогай менеджерам быстро находить спецификации по оборудованию."
)


def upgrade() -> None:
    conn = op.get_bind()
    ins = sa_text(
        """
        INSERT INTO system_settings (key, value, description)
        VALUES (:key, :value, :description)
        ON CONFLICT (key) DO NOTHING
        """
    )
    rows = [
        (
            "MAX_BOT_USERNAME",
            "@id6451417302_bot",
            "Упоминание бота MAX в группе (подстрока в тексте); без неё ответ в группе не формируется.",
        ),
        (
            "MAX_GROUP_CHAT_ID",
            "",
            "Числовой chat_id группы MAX, для которой подмешивается MAX_GROUP_ADDITIONAL_PROMPT (пусто — промпт группы не используется).",
        ),
        (
            "MAX_GROUP_ADDITIONAL_PROMPT",
            _DEFAULT_GROUP_PROMPT,
            "Дополнительный системный контекст для указанной группы (к session_id = MAX_GROUP_CHAT_ID).",
        ),
    ]
    for key, value, description in rows:
        conn.execute(ins, {"key": key, "value": value, "description": description})


def downgrade() -> None:
    op.execute(
        sa_text(
            "DELETE FROM system_settings WHERE key IN "
            "('MAX_BOT_USERNAME', 'MAX_GROUP_CHAT_ID', 'MAX_GROUP_ADDITIONAL_PROMPT')"
        )
    )
