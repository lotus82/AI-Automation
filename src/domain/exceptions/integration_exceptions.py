"""Ошибки сценариев вызова внешних API по конфигурации Integration."""


class IntegrationNotFoundError(LookupError):
    """Интеграция с указанным id не найдена в хранилище."""

    def __init__(self, integration_id: str, message: str | None = None) -> None:
        self.integration_id = integration_id
        super().__init__(message or f"Integration not found: {integration_id}")


class ActionNotFoundError(LookupError):
    """Действие с указанным именем отсутствует в конфигурации интеграции."""

    def __init__(self, action_name: str, message: str | None = None) -> None:
        self.action_name = action_name
        super().__init__(message or f"Integration action not found: {action_name}")


class IntegrationCallError(RuntimeError):
    """Сетевой или HTTP-сбой при вызове внешнего API, либо невалидный ответ."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
        self.url = url
