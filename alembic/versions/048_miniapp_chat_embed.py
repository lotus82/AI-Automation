"""portal_users.miniapp_chat_id; site_pages.embed_module (встраиваемые модули Mini App)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# VARCHAR(32) в alembic_version — идентификатор ревизии не длиннее 32 символов.
revision = "048_miniapp_chat_embed"
down_revision = "047_site_page_booking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_users",
        sa.Column("miniapp_chat_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "site_pages",
        sa.Column("embed_module", sa.String(64), nullable=True),
    )
    op.create_index("ix_portal_users_miniapp_chat_id", "portal_users", ["miniapp_chat_id"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_portal_users_org_miniapp_chat
        ON portal_users (organization_id, miniapp_chat_id)
        WHERE miniapp_chat_id IS NOT NULL AND btrim(miniapp_chat_id) <> '';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_portal_users_org_miniapp_chat")
    op.drop_index("ix_portal_users_miniapp_chat_id", table_name="portal_users")
    op.drop_column("site_pages", "embed_module")
    op.drop_column("portal_users", "miniapp_chat_id")
