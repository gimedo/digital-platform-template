"""Conector PostgreSQL contra un servidor real.

Se ejecuta solo si TEST_DATABASE_URL apunta a PostgreSQL (ver conftest.py). Crea esquemas temporales
`bld_test_*` en esa base y los borra al terminar.
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from builder.connectors import ConnectionParams
from builder.connectors.postgres import PostgresConnector
from builder.errors import DatabaseUnreachableError
from core.config import settings
from tests.conftest import TEST_DB

pytestmark = pytest.mark.skipif(
    not TEST_DB or not make_url(TEST_DB).get_backend_name().startswith("postgres"),
    reason="Definí TEST_DATABASE_URL (PostgreSQL) para probar el conector contra un servidor real.",
)

SCHEMA_A, SCHEMA_B = "bld_test_a", "bld_test_b"


@pytest.fixture(scope="module")
def target():
    url = make_url(TEST_DB)
    eng = create_engine(TEST_DB)
    with eng.begin() as conn:
        for s in (SCHEMA_A, SCHEMA_B):
            conn.execute(text(f'DROP SCHEMA IF EXISTS {s} CASCADE'))
            conn.execute(text(f'CREATE SCHEMA {s}'))
        conn.execute(text(f"CREATE TABLE {SCHEMA_A}.clientes (id serial PRIMARY KEY, nombre text)"))
        conn.execute(text(f"CREATE TABLE {SCHEMA_A}.bitacora (msg text)"))  # sin PK
        conn.execute(text(f"CREATE TABLE {SCHEMA_A}.detalle (pedido_id int, linea int, PRIMARY KEY (pedido_id, linea))"))
        conn.execute(text(f"CREATE VIEW {SCHEMA_A}.v_clientes AS SELECT * FROM {SCHEMA_A}.clientes"))
        conn.execute(text(f"CREATE TABLE {SCHEMA_B}.ciudades (codigo text PRIMARY KEY)"))
        conn.execute(text(f"CREATE TABLE {SCHEMA_B}.\"Pedidos Raros\" (id int PRIMARY KEY)"))
    params = ConnectionParams(
        host=url.host, port=url.port or 5432, username=url.username, password=url.password or "",
        ssl_mode="prefer", database=url.database,
    )
    yield params
    with eng.begin() as conn:
        for s in (SCHEMA_A, SCHEMA_B):
            conn.execute(text(f"DROP SCHEMA IF EXISTS {s} CASCADE"))
    eng.dispose()


connector = PostgresConnector()


def test_probe_devuelve_version_y_la_base_actual(target):
    result = connector.probe(target)
    assert result.server_version and result.server_version[0].isdigit()
    assert target.database in result.databases
    assert not any(d.startswith("template") for d in result.databases)  # sin plantillas


def test_probe_sin_indicar_base_usa_postgres_para_listar(target):
    result = connector.probe(target.with_database(None))
    assert target.database in result.databases


def test_lista_tablas_con_clave_primaria_en_varios_esquemas(target):
    mine = {t.key: t for t in connector.list_tables(target) if t.schema_name.startswith("bld_test_")}
    assert set(mine) == {
        (SCHEMA_A, "clientes"), (SCHEMA_A, "bitacora"), (SCHEMA_A, "detalle"),
        (SCHEMA_B, "ciudades"), (SCHEMA_B, "Pedidos Raros"),
    }  # la vista v_clientes no aparece
    assert mine[(SCHEMA_A, "clientes")].primary_key == ("id",)
    assert mine[(SCHEMA_A, "bitacora")].primary_key == ()
    assert set(mine[(SCHEMA_A, "detalle")].primary_key) == {"pedido_id", "linea"}
    assert mine[(SCHEMA_B, "Pedidos Raros")].primary_key == ("id",)  # nombres con mayúsculas/espacios


def test_no_lista_esquemas_del_sistema_y_viene_ordenado(target):
    tables = connector.list_tables(target)
    schemas = {t.schema_name for t in tables}
    assert "information_schema" not in schemas and not any(s.startswith("pg_") for s in schemas)
    assert [t.key for t in tables] == sorted(t.key for t in tables)


def test_la_sesion_es_de_solo_lectura_y_con_limite_de_tiempo(target):
    with connector._connect(target, target.database) as conn:
        assert conn.execute(text("SHOW default_transaction_read_only")).scalar() == "on"
        assert conn.execute(text("SHOW statement_timeout")).scalar() == f"{settings.builder_query_timeout_seconds}s"
        assert conn.execute(text("SHOW application_name")).scalar() == "digital-platform-builder"
    # escribir está prohibido aunque el usuario de la conexión tenga permisos para hacerlo
    with pytest.raises(DatabaseUnreachableError) as exc:
        with connector._connect(target, target.database) as conn:
            conn.execute(text("CREATE TABLE bld_test_no_debe_existir (x int)"))
    assert "read-only" in exc.value.details["reason"].lower()


def test_el_timeout_de_consulta_corta_las_consultas_lentas(target, monkeypatch):
    monkeypatch.setattr(settings, "builder_query_timeout_seconds", 1)
    with pytest.raises(DatabaseUnreachableError):
        with connector._connect(target, target.database) as conn:
            conn.execute(text("SELECT pg_sleep(5)"))


def test_contrasena_incorrecta(target):
    bad = ConnectionParams(**{**target.__dict__, "password": "incorrecta"})
    with pytest.raises(DatabaseUnreachableError) as exc:
        connector.probe(bad)
    assert exc.value.details["kind"] == "auth" and "incorrectos" in exc.value.message
    assert "incorrecta" not in exc.value.message and "incorrecta" not in str(exc.value.details)


def test_base_inexistente(target):
    with pytest.raises(DatabaseUnreachableError) as exc:
        connector.list_tables(target.with_database("base_que_no_existe_xyz"))
    assert exc.value.details["kind"] == "database"


def test_servidor_inalcanzable(target, monkeypatch):
    monkeypatch.setattr(settings, "builder_connect_timeout", 2)
    dead = ConnectionParams(**{**target.__dict__, "host": "127.0.0.1", "port": 1})  # puerto cerrado
    with pytest.raises(DatabaseUnreachableError) as exc:
        connector.probe(dead)
    assert exc.value.details["kind"] == "network"


def test_sin_base_indicada_al_listar_tablas(target):
    with pytest.raises(DatabaseUnreachableError):
        connector.list_tables(target.with_database(None))


# ---------------- de punta a punta: API real + conector real ----------------
def test_flujo_completo_con_el_conector_real(client, admin_headers, target):
    conn = {"host": target.host, "port": target.port, "username": target.username, "password": target.password,
            "ssl_mode": "prefer"}
    r = client.post("/api/builder/connections/test", json=conn, headers=admin_headers)
    assert r.status_code == 200 and target.database in r.json()["databases"]

    r = client.post("/api/builder/connections/tables", json={**conn, "database": target.database}, headers=admin_headers)
    names = {(t["schema_name"], t["table_name"]) for t in r.json()["tables"]}
    assert (SCHEMA_A, "clientes") in names
    assert not any(n[1].startswith("builder_") or n[1] == "schema_migrations" for n in names)  # internas ocultas
    assert any(t["sensitive"] for t in r.json()["tables"] if t["table_name"] == "users")

    body = {**conn, "name": "e2e", "database_name": target.database,
            "tables": [{"schema_name": SCHEMA_A, "table_name": "clientes"}, {"schema_name": SCHEMA_A, "table_name": "bitacora"}]}
    r = client.post("/api/builder/projects", json=body, headers=admin_headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.post(f"/api/builder/projects/{pid}/test", headers=admin_headers).status_code == 200

    avail = client.get(f"/api/builder/projects/{pid}/available-tables", headers=admin_headers).json()["tables"]
    assert (SCHEMA_A, "clientes") not in {(t["schema_name"], t["table_name"]) for t in avail}
    assert (SCHEMA_A, "detalle") in {(t["schema_name"], t["table_name"]) for t in avail}

    # contraseña incorrecta al crear: no se crea nada
    bad = {**body, "name": "mal", "password": "incorrecta"}
    r = client.post("/api/builder/projects", json=bad, headers=admin_headers)
    assert r.status_code == 502 and r.json()["error"]["details"]["kind"] == "auth"
    assert len(client.get("/api/builder/projects", headers=admin_headers).json()) == 1
