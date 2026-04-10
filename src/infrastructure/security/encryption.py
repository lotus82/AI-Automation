"""Симметричное шифрование полей интеграций (Fernet)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class SymmetricEncryption:
    """Обёртка над ``cryptography.fernet.Fernet`` для строковых секретов."""

    def __init__(self, secret_key_b64: str) -> None:
        """``secret_key_b64`` — URL-safe base64-ключ Fernet (44 символа, 32 байта после декодирования)."""
        key = secret_key_b64.strip().encode("ascii")
        self._fernet = Fernet(key)

    def encrypt(self, plain_text: str) -> str:
        """Возвращает ASCII-текст (base64), пригодный для JSONB."""
        token = self._fernet.encrypt(plain_text.encode("utf-8"))
        return token.decode("ascii")

    def decrypt(self, cipher_text: str) -> str:
        """Расшифровывает значение, сохранённое ``encrypt``."""
        try:
            raw = self._fernet.decrypt(cipher_text.strip().encode("ascii"))
        except InvalidToken as exc:
            msg = "Fernet decrypt failed: invalid token or wrong key"
            raise ValueError(msg) from exc
        return raw.decode("utf-8")
