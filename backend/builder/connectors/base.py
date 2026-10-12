from abc import ABC, abstractmethod
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ConnectionParams:
    host: str
    port: int
    username: str
    password: str
    ssl_mode: str = "prefer"
    database: str | None = None

    def with_database(self, database: str | None) -> "ConnectionParams":
        return replace(self, database=database)


@dataclass(frozen=True)
class DiscoveredTable:
    schema_name: str
    table_name: str
    primary_key: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str]:
        return (self.schema_name, self.table_name)


@dataclass(frozen=True)
class ProbeResult:
    server_version: str
    databases: list[str]


class Connector(ABC):
    """Contrato de un motor de base de datos. Para sumar otro motor: implementar esta clase y registrarla."""

    engine_code: str
    default_port: int

    @abstractmethod
    def probe(self, params: ConnectionParams) -> ProbeResult:
        """Verifica la conexión y devuelve versión y bases disponibles."""

    @abstractmethod
    def list_tables(self, params: ConnectionParams) -> list[DiscoveredTable]:
        """Tablas (no vistas) de la base indicada en params.database, con su clave primaria."""
