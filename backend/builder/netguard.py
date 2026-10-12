"""Validación del servidor al que el Builder se conecta (evita usar el backend como puente de red)."""
import ipaddress
import re

from builder.errors import DatabaseUnreachableError  # noqa: F401  (reexport para quien lo necesite)
from core.config import settings
from core.errors import BadRequestError

_HOSTNAME = re.compile(r"^[A-Za-z0-9_]([A-Za-z0-9_.-]*[A-Za-z0-9_])?$")


def _parse_ip(value: str):
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def normalize_host(host: str) -> str:
    """Acepta solo un nombre de host o una IP. Rechaza rutas, listas y cualquier carácter raro."""
    value = (host or "").strip()
    if not value or len(value) > 255:
        raise BadRequestError("Indicá el servidor (nombre o IP).")
    if _parse_ip(value) is not None:
        return value
    # '/' sería un socket unix y ',' una lista de servidores en libpq: ninguno es válido acá.
    if not _HOSTNAME.match(value):
        raise BadRequestError("El servidor debe ser un nombre de host o una dirección IP válidos.")
    return value


def _allowed_entries() -> list[str]:
    return [e.strip().lower() for e in settings.builder_allowed_hosts.split(",") if e.strip()]


def ensure_host_allowed(host: str) -> str:
    value = normalize_host(host)
    entries = _allowed_entries()
    if not entries:
        return value  # sin lista: cualquier servidor (herramienta interna solo para administradores)

    ip = _parse_ip(value)
    lowered = value.lower()
    for entry in entries:
        if ip is not None:
            try:
                if ip in ipaddress.ip_network(entry, strict=False):
                    return value
            except ValueError:
                pass
        elif entry.startswith("*."):
            if lowered.endswith(entry[1:]) and lowered != entry[2:]:
                return value
        elif lowered == entry:
            return value
    raise BadRequestError("Ese servidor no está en la lista de hosts permitidos (BUILDER_ALLOWED_HOSTS).")
