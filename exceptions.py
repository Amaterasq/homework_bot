class ApiError(Exception):
    """API вернул результат, не равный 200."""

    pass


class ResponseError(Exception):
    """API вернул результат с ошибкой."""

    pass
