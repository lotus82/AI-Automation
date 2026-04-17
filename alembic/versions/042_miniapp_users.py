"""Mini Apps: ИНН организации и таблица пользователей Mini App (мессенджер MAX)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "042_miniapp_users"
down_revision = "041_chat_messages_org"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Уникальный ИНН у организации — используется как публичный роут /inn/<inn>
    op.add_column(
        "organizations",
        sa.Column("inn", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_organizations_inn",
        "organizations",
        ["inn"],
        unique=True,
    )

    # 2) Пользователи Mini App — идентифицируются chat_id мессенджера в рамках организации
    op.create_table(
        "mini_app_users",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id",
            "chat_id",
            name="uq_mini_app_users_org_chat",
        ),
    )
    op.create_index(
        "ix_mini_app_users_organization_id",
        "mini_app_users",
        ["organization_id"],
    )
    op.create_index(
        "ix_mini_app_users_chat_id",
        "mini_app_users",
        ["chat_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mini_app_users_chat_id", table_name="mini_app_users")
    op.drop_index("ix_mini_app_users_organization_id", table_name="mini_app_users")
    op.drop_table("mini_app_users")
    op.drop_index("ix_organizations_inn", table_name="organizations")
    op.drop_column("organizations", "inn")
