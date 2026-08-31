class ODataError(Exception):
    """Базовое исключение OData."""


class ODataConnectionError(ODataError):
    """Ошибка подключения к 1С."""


class ODataAuthError(ODataError):
    """Ошибка авторизации."""


class ODataNotFoundError(ODataError):
    """Сущность не найдена."""


class ODataValidationError(ODataError):
    """Ошибка валидации данных."""
