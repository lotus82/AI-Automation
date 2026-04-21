"""Декодирование байтов .txt: UTF-8 (в т.ч. с BOM), типичные кириллические ANSI-кодировки Windows."""


def decode_txt_bytes(raw: bytes) -> str:
    """
    Сохраняет кириллицу и прочие символы без «ромбиков» (U+FFFD).

    Раньше использовался ``utf-8`` с ``errors="replace"``: при файле в cp1251
    невалидные последовательности заменялись на ``�``.
    """
    if not raw:
        return ""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if len(raw) >= 2 and raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for enc in ("cp1251", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")
