"""Таблица system_settings и сиды по умолчанию (динамическая конфигурация).

Revision ID: 005_system_settings
Revises: 004_sip_dialer
Create Date: 2026-04-02

# TODO: В продакшене хранить секреты (API-ключи) в зашифрованном виде at rest
#       (например, Fernet из библиотеки cryptography + ключ из KMS/Vault), а не в открытом TEXT.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text as sa_text

revision = "005_system_settings"
down_revision = "004_sip_dialer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=512), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    conn = op.get_bind()
    rows = [
        (
            "LLM_PROVIDER",
            "deepseek",
            "Провайдер LLM: deepseek или openai (регистр не важен).",
        ),
        ("DEEPSEEK_API_KEY", "", "API-ключ DeepSeek (OpenAI-совместимый endpoint)."),
        (
            "OPENAI_API_KEY",
            "",
            "API-ключ OpenAI (чат и эмбеддинги RAG при использовании OpenAI).",
        ),
        ("TELEGRAM_BOT_TOKEN", "", "Токен Telegram-бота (зарезервировано для будущих интеграций)."),
        (
            "DEFAULT_CONSULTANT_PROMPT",
            "Ты профессиональный менеджер по продаже промышленных станков и оборудования. "
            "Клиенты — российские компании. Отвечай вежливо, по делу, опираясь на фрагменты базы знаний, "
            "если они переданы в запросе. Если в базе нет данных — скажи об этом честно. "
            "Отвечай на языке клиента (по-русски для русских сообщений).",
            "Системный промпт ИИ-консультанта (текст и голос).",
        ),
        (
            "ANALYST_QA_PROMPT",
            "Ты строгий менеджер отдела контроля качества (ОКК) в B2B-продажах промышленного оборудования. "
            "Проанализируй полный текст диалога между клиентом и ИИ-консультантом. "
            'Верни СТРОГО один JSON-объект без пояснений вокруг: {"score": <целое от 1 до 10>, '
            '"recommendations": "<2–5 предложений на русском: что улучшить ассистенту>"}. '
            "Критерии: вежливость, точность по фактам, уместность RAG, работа с возражениями, призыв к шагу. "
            "Если диалог пустой или слишком короткий — поставь низкий балл и объясни почему.",
            "Системный промпт для задачи ОКК (анализ после диалога).",
        ),
    ]
    ins = sa_text(
        """
        INSERT INTO system_settings (key, value, description)
        VALUES (:key, :value, :description)
        ON CONFLICT (key) DO NOTHING
        """
    )
    for key, value, description in rows:
        conn.execute(
            ins,
            {"key": key, "value": value, "description": description},
        )


def downgrade() -> None:
    op.drop_table("system_settings")
