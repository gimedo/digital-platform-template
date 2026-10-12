from builder.connectors.base import ConnectionParams, Connector, DiscoveredTable, ProbeResult
from builder.connectors.postgres import PostgresConnector
from core.errors import BadRequestError

# Registro de motores. Para sumar MySQL, SQL Server, etc.: implementar Connector y agregarlo acá.
CONNECTORS: dict[str, Connector] = {"postgresql": PostgresConnector()}


def get_connector(engine: str) -> Connector:
    try:
        return CONNECTORS[engine]
    except KeyError:
        raise BadRequestError(f"Motor de base de datos no soportado: {engine}") from None


__all__ = ["CONNECTORS", "ConnectionParams", "Connector", "DiscoveredTable", "ProbeResult", "get_connector"]
