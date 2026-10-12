from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Connection, create_engine, event, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.pool import NullPool

from builder.connectors.base import ConnectionParams, Connector, DiscoveredTable, ProbeResult
from builder.errors import DatabaseUnreachableError
from core.config import settings

_SYSTEM_SCHEMA = "information_schema"


def _translate(exc: Exception) -> DatabaseUnreachableError:
    """Convierte un error del driver en un mensaje claro, sin exponer datos de conexión."""
    original = getattr(exc, "orig", exc)
    raw = str(original).strip()
    reason = raw.splitlines()[0][:300] if raw else ""
    low = raw.lower()

    if "password authentication failed" in low or "authentication failed" in low or "no password supplied" in low:
        kind, message = "auth", "Usuario o contraseña incorrectos."
    elif "no pg_hba.conf entry" in low:
        kind, message = "network", "El servidor rechazó la conexión: pg_hba.conf no permite este origen o usuario."
    elif "database" in low and "does not exist" in low:
        kind, message = "database", "La base de datos indicada no existe."
    elif "permission denied for database" in low or "not allowed to connect" in low:
        kind, message = "database", "El usuario no tiene permiso para conectarse a esa base de datos."
    elif "timeout" in low or "timed out" in low:
        kind, message = "network", "Tiempo de espera agotado: el servidor no respondió."
    elif "ssl" in low:
        kind, message = "ssl", "Problema con SSL. Probá con otro modo de SSL."
    elif any(s in low for s in ("connection refused", "could not translate host", "name or service not known",
                                "no route to host", "network is unreachable", "connection failed", "could not connect")):
        kind, message = "network", "No se pudo conectar. Revisá el servidor y el puerto."
    else:
        kind, message = "other", "No se pudo completar la operación con la base de datos."
    return DatabaseUnreachableError(message, details={"kind": kind, "reason": reason})


class PostgresConnector(Connector):
    engine_code = "postgresql"
    default_port = 5432

    def _engine(self, params: ConnectionParams, database: str):
        url = URL.create(
            "postgresql+psycopg",
            username=params.username,
            password=params.password or None,
            host=params.host,
            port=params.port,
            database=database,
            query={"sslmode": params.ssl_mode},
        )
        engine = create_engine(
            url,
            poolclass=NullPool,  # una conexión por operación; no queda nada abierto
            connect_args={"connect_timeout": settings.builder_connect_timeout, "application_name": "digital-platform-builder"},
        )
        timeout_ms = int(settings.builder_query_timeout_seconds) * 1000

        @event.listens_for(engine, "connect")
        def _session_limits(dbapi_connection, _record):  # noqa: ANN001
            # SET por sesión (no por opciones de arranque) para que funcione también detrás de PgBouncer.
            previous = dbapi_connection.autocommit
            dbapi_connection.autocommit = True
            try:
                with dbapi_connection.cursor() as cur:
                    cur.execute("SET default_transaction_read_only = on")
                    cur.execute(f"SET statement_timeout = {timeout_ms}")
            finally:
                dbapi_connection.autocommit = previous

        return engine

    @contextmanager
    def _connect(self, params: ConnectionParams, database: str) -> Iterator[Connection]:
        engine = self._engine(params, database)
        try:
            with engine.connect() as conn:
                yield conn
        except (DBAPIError, SQLAlchemyError) as exc:
            raise _translate(exc) from None
        finally:
            engine.dispose()

    def probe(self, params: ConnectionParams) -> ProbeResult:
        with self._connect(params, params.database or "postgres") as conn:
            version = conn.execute(text("SHOW server_version")).scalar_one()
            rows = conn.execute(
                text(
                    "SELECT datname FROM pg_database "
                    "WHERE NOT datistemplate AND datallowconn AND has_database_privilege(datname, 'CONNECT') "
                    "ORDER BY datname"
                )
            ).scalars()
            return ProbeResult(server_version=str(version), databases=list(rows))

    def list_tables(self, params: ConnectionParams) -> list[DiscoveredTable]:
        if not params.database:
            raise DatabaseUnreachableError("Indicá la base de datos.", details={"kind": "database", "reason": ""})
        with self._connect(params, params.database) as conn:
            inspector = inspect(conn)
            tables: list[DiscoveredTable] = []
            for schema in inspector.get_schema_names():
                if schema == _SYSTEM_SCHEMA or schema.startswith("pg_"):
                    continue
                names = inspector.get_table_names(schema=schema)
                if not names:
                    continue
                pks = inspector.get_multi_pk_constraint(schema=schema)  # una sola consulta por esquema
                for name in names:
                    columns = (pks.get((schema, name)) or {}).get("constrained_columns") or []
                    tables.append(DiscoveredTable(schema, name, tuple(columns)))
            return sorted(tables, key=lambda t: (t.schema_name, t.table_name))
