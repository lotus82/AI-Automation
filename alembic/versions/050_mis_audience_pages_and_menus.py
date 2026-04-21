"""МИС: site_pages.mis_audience + отдельные меню врача/пациента на sites."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "050_mis_audience_pages_and_menus"
down_revision = "049_sites_site_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "site_pages",
        sa.Column("mis_audience", sa.String(16), nullable=True),
    )
    op.execute(
        """
        ALTER TABLE site_pages
        ADD CONSTRAINT ck_site_pages_mis_audience
        CHECK (mis_audience IS NULL OR mis_audience IN ('doctor','patient'))
        """
    )

    op.add_column(
        "sites",
        sa.Column(
            "mis_menu_items_doctor",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "sites",
        sa.Column(
            "mis_menu_items_patient",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # Заполнение audience по типу страницы
    op.execute(
        """
        UPDATE site_pages
        SET mis_audience = 'doctor'
        WHERE page_kind IN ('mis_patients', 'mis_doctor_card')
        """
    )
    op.execute(
        """
        UPDATE site_pages
        SET mis_audience = 'patient'
        WHERE page_kind IN (
            'mis_patient_card', 'mis_patient_profile', 'mis_patient_diary', 'mis_patient_tips'
        )
        """
    )

    # Копируем общее меню в оба столбца для существующих МИС-сайтов
    op.execute(
        """
        UPDATE sites
        SET
            mis_menu_items_doctor = COALESCE(menu_items, '[]'::jsonb),
            mis_menu_items_patient = COALESCE(menu_items, '[]'::jsonb)
        WHERE site_kind = 'mis'
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE site_pages DROP CONSTRAINT IF EXISTS ck_site_pages_mis_audience")
    op.drop_column("site_pages", "mis_audience")
    op.drop_column("sites", "mis_menu_items_patient")
    op.drop_column("sites", "mis_menu_items_doctor")
