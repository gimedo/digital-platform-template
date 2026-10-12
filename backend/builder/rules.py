"""Reglas de negocio puras del Builder (sin base de datos ni red)."""
import re

METHODS = ("GET", "POST", "PUT", "DELETE")
# Estos métodos operan sobre un registro puntual: necesitan clave primaria.
NEEDS_PRIMARY_KEY = frozenset({"PUT", "DELETE"})

RESOURCE_STATUSES = ("NOT_GENERATED", "PUBLISHED", "DISABLED", "ERROR")

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SPLIT = re.compile(r"[^a-z0-9]+")

# Palabras que delatan tablas de credenciales o sesiones: nunca se publican sin confirmación explícita.
_SENSITIVE_WORDS = frozenset(
    {
        "user", "users", "usuario", "usuarios",
        "password", "passwords", "passwd", "pwd", "clave", "claves",
        "token", "tokens",
        "credential", "credentials", "credencial", "credenciales",
        "secret", "secrets", "secreto", "secretos",
        "session", "sessions", "sesion", "sesiones",
        "apikey", "apikeys", "oauth", "auth", "login", "logins",
    }
)


def is_sensitive_table(name: str) -> bool:
    words = _SPLIT.split(_CAMEL.sub("_", name).lower())
    return any(w in _SENSITIVE_WORDS for w in words if w)


def is_internal_table(name: str) -> bool:
    """Tablas de la propia plataforma: contienen contraseñas cifradas y configuración; jamás se exponen."""
    lowered = name.lower()
    return lowered.startswith("builder_") or lowered == "schema_migrations"


def default_endpoints(has_primary_key: bool) -> dict[str, bool]:
    """Por defecto todo disponible; sin clave primaria no se ofrecen PUT ni DELETE."""
    return {m: (has_primary_key or m not in NEEDS_PRIMARY_KEY) for m in METHODS}
