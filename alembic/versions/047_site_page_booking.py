"""site_pages: тип страницы «запись» и привязка к сотруднику (portal_users)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "047_site_page_booking"
down_revision = "046_booking_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "site_pages",
        sa.Column("page_kind", sa.String(32), nullable=False, server_default=sa.text("'content'")),
    )
    op.add_column(
        "site_pages",
        sa.Column("booking_staff_user_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_site_pages_booking_staff_user",
        "site_pages",
        "portal_users",
        ["booking_staff_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_site_pages_booking_staff_user_id",
        "site_pages",
        ["booking_staff_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_site_pages_booking_staff_user_id", table_name="site_pages")
    op.drop_constraint("fk_site_pages_booking_staff_user", "site_pages", type_="foreignkey")
    op.drop_column("site_pages", "booking_staff_user_id")
    op.drop_column("site_pages", "page_kind")
