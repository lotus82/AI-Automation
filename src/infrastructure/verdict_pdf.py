"""PDF с текстом вердикта ИИ по опроснику (UTF-8, кириллица через DejaVu Sans)."""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from fpdf import FPDF

# Образ web (Debian bookworm): пакет fonts-dejavu-core. Локально на Windows — Arial.
_WIN_ROOT = os.environ.get("SystemRoot") or os.environ.get("windir") or r"C:\Windows"
_UNICODE_SANS_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
    Path(_WIN_ROOT) / "Fonts" / "arial.ttf",
)


def _resolve_unicode_sans_font() -> Path:
    override = (os.environ.get("DEJAVU_SANS_FONT") or "").strip()
    if override:
        p = Path(override)
        if p.is_file():
            return p
    for p in _UNICODE_SANS_CANDIDATES:
        if p.is_file():
            return p
    msg = (
        "Не найден TTF-шрифт с кириллицей для PDF. В Docker: fonts-dejavu-core (см. Dockerfile). "
        "Локально: задайте DEJAVU_SANS_FONT=/путь/к/DejaVuSans.ttf"
    )
    raise RuntimeError(msg)


def _ascii_filename_slug(title: str, max_len: int = 48) -> str:
    raw = (title or "oprosnik").strip()
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw).strip("._-") or "oprosnik"
    return raw[:max_len]


def build_questionnaire_verdict_pdf(
    *,
    title: str,
    analysis: str,
    generated_at: datetime | None = None,
    tz: ZoneInfo | None = None,
) -> tuple[bytes, str]:
    """Возвращает (pdf_bytes, suggested_ascii_filename_without_ext)."""
    font_path = _resolve_unicode_sans_font()
    body = (analysis or "").strip() or "—"
    doc_title = (title or "Опросник").strip()
    when = generated_at or datetime.now(tz or ZoneInfo("UTC"))
    if tz is not None:
        when = when.astimezone(tz)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(left=18, top=18, right=18)
    pdf.add_page()
    pdf.add_font("ReportSans", "", str(font_path))
    pdf.set_font("ReportSans", size=16)
    pdf.multi_cell(0, 9, doc_title)
    pdf.ln(4)
    pdf.set_font("ReportSans", size=9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, f"Сформировано: {when.strftime('%Y-%m-%d %H:%M')}")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)
    pdf.set_font("ReportSans", size=12)
    pdf.set_text_color(13, 148, 136)
    pdf.multi_cell(0, 6, "Вердикт ИИ")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    pdf.set_font("ReportSans", size=11)
    pdf.multi_cell(0, 5.5, body)

    buf = BytesIO()
    pdf.output(buf)
    name = f"verdikt-ii_{_ascii_filename_slug(doc_title)}"
    return buf.getvalue(), name
