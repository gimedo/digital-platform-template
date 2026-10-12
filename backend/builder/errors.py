from core.errors import AppError


class DatabaseUnreachableError(AppError):
    """No se pudo operar con la base de datos de destino (credenciales, red, permisos...)."""

    status_code = 502
    code = "database_unreachable"
