"""API del Builder con un conector falso: corre en SQLite y sin servidores externos."""
import pytest
from sqlalchemy import text

import builder.connectors as connectors
from builder.connectors import ConnectionParams, DiscoveredTable, ProbeResult
from builder.errors import DatabaseUnreachableError
from builder.models import BuilderProject, BuilderResource, BuilderResourceEndpoint
from core import crypto
from core.config import settings
from core.crypto import decrypt_secret
from core.database import SessionLocal, engine

TABLES = [
    DiscoveredTable("public", "clientes", ("id",)),
    DiscoveredTable("public", "transportistas", ("id",)),
    DiscoveredTable("public", "bitacora", ()),  # sin clave primaria
    DiscoveredTable("public", "users", ("id",)),  # sensible
    DiscoveredTable("ventas", "detalle", ("pedido_id", "linea")),  # clave compuesta
    DiscoveredTable("public", "builder_projects", ("id",)),  # interna: debe ocultarse
    DiscoveredTable("public", "schema_migrations", ("filename",)),  # interna
]

CONN = {"host": "192.168.50.11", "port": 6002, "username": "postgres", "password": "p@ss:w/rd#1%", "ssl_mode": "prefer"}


class FakeConnector:
    engine_code = "postgresql"
    default_port = 5432

    def __init__(self):
        self.calls: list[tuple[str, ConnectionParams]] = []
        self.tables = list(TABLES)
        self.error: DatabaseUnreachableError | None = None

    def probe(self, params):
        self.calls.append(("probe", params))
        if self.error:
            raise self.error
        return ProbeResult("16.2", ["digital_platform", "ventas_api"])

    def list_tables(self, params):
        self.calls.append(("list_tables", params))
        if self.error:
            raise self.error
        return list(self.tables)


@pytest.fixture
def fake(monkeypatch):
    connector = FakeConnector()
    monkeypatch.setitem(connectors.CONNECTORS, "postgresql", connector)
    return connector


def new_project(client, headers, name="abmprueba", tables=("clientes", "transportistas"), **extra):
    body = {**CONN, "name": name, "database_name": "digital_platform",
            "tables": [{"schema_name": "public", "table_name": t} for t in tables], **extra}
    return client.post("/api/builder/projects", json=body, headers=headers)


# ---------------------------------------------------------------- seguridad
ENDPOINTS = [
    ("post", "/api/builder/connections/test", CONN),
    ("post", "/api/builder/connections/tables", {**CONN, "database": "x"}),
    ("get", "/api/builder/projects", None),
    ("post", "/api/builder/projects", {}),
    ("get", "/api/builder/projects/1", None),
    ("patch", "/api/builder/projects/1", {"name": "x"}),
    ("delete", "/api/builder/projects/1", None),
    ("post", "/api/builder/projects/1/test", None),
    ("get", "/api/builder/projects/1/resources", None),
    ("get", "/api/builder/projects/1/available-tables", None),
    ("post", "/api/builder/projects/1/resources", {"tables": []}),
    ("delete", "/api/builder/projects/1/resources/1", None),
    ("patch", "/api/builder/projects/1/resources/1/endpoints", {"GET": True}),
]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_todo_el_builder_exige_administrador(client, make_user, login, fake, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401  # sin token

    make_user(email="comun@example.com", role="user")
    token = login(email="comun@example.com").json()["access_token"]
    r = getattr(client, method)(path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
    assert r.status_code == 403  # usuario común
    assert fake.calls == []  # y jamás llegó a abrirse una conexión


# ---------------------------------------------------------------- asistente
def test_probar_conexion_lista_las_bases(client, admin_headers, fake):
    r = client.post("/api/builder/connections/test", json=CONN, headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == {"server_version": "16.2", "databases": ["digital_platform", "ventas_api"]}
    _, params = fake.calls[0]
    assert (params.host, params.port, params.password, params.database) == ("192.168.50.11", 6002, "p@ss:w/rd#1%", None)


def test_error_de_conexion_devuelve_502_con_motivo_sin_secretos(client, admin_headers, fake):
    fake.error = DatabaseUnreachableError("Usuario o contraseña incorrectos.", details={"kind": "auth", "reason": "FATAL"})
    r = client.post("/api/builder/connections/test", json=CONN, headers=admin_headers)
    assert r.status_code == 502
    err = r.json()["error"]
    assert err["code"] == "database_unreachable" and err["details"]["kind"] == "auth"
    assert "p@ss" not in r.text


def test_descubrir_tablas_marca_sensibles_y_oculta_las_internas(client, admin_headers, fake):
    r = client.post("/api/builder/connections/tables", json={**CONN, "database": "digital_platform"}, headers=admin_headers)
    assert r.status_code == 200
    tables = {(t["schema_name"], t["table_name"]): t for t in r.json()["tables"]}
    assert ("public", "builder_projects") not in tables and ("public", "schema_migrations") not in tables
    assert tables[("public", "users")]["sensitive"] is True
    assert tables[("public", "clientes")]["sensitive"] is False
    assert tables[("public", "bitacora")]["has_primary_key"] is False
    assert tables[("ventas", "detalle")]["primary_key"] == ["pedido_id", "linea"]


def test_servidor_invalido_se_rechaza_antes_de_conectar(client, admin_headers, fake):
    for host in ("/var/run/postgresql", "a,b", "host name"):
        r = client.post("/api/builder/connections/test", json={**CONN, "host": host}, headers=admin_headers)
        assert r.status_code == 400, host
    assert fake.calls == []


def test_lista_de_hosts_permitidos_se_aplica(client, admin_headers, fake, monkeypatch):
    monkeypatch.setattr(settings, "builder_allowed_hosts", "10.0.0.0/8")
    r = client.post("/api/builder/connections/test", json=CONN, headers=admin_headers)  # 192.168.50.11 no está
    assert r.status_code == 400 and "BUILDER_ALLOWED_HOSTS" in r.json()["error"]["message"]
    assert fake.calls == []


# ---------------------------------------------------------------- proyectos
def test_crear_proyecto_guarda_la_contrasena_cifrada_y_no_la_devuelve(client, admin_headers, fake):
    r = new_project(client, admin_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "abmprueba" and body["tables_total"] == 2 and body["generated_total"] == 0
    assert body["host"] == "192.168.50.11" and body["port"] == 6002 and body["database_name"] == "digital_platform"
    assert "password" not in body and "encrypted_password" not in body and "p@ss" not in r.text

    with SessionLocal() as db:
        project = db.get(BuilderProject, body["id"])
        assert "p@ss" not in project.encrypted_password
        assert decrypt_secret(project.encrypted_password) == "p@ss:w/rd#1%"
        assert project.created_by is not None
    # se verificó contra la base real al crear
    assert fake.calls[-1][0] == "list_tables" and fake.calls[-1][1].database == "digital_platform"


def test_inventario_inicial_con_endpoints_por_defecto(client, admin_headers, fake):
    pid = new_project(client, admin_headers, tables=("clientes", "bitacora", "users")).json()["id"]
    inv = {r["table_name"]: r for r in client.get(f"/api/builder/projects/{pid}/resources", headers=admin_headers).json()}

    clientes = inv["clientes"]
    assert clientes["status"] == "NOT_GENERATED" and clientes["has_primary_key"] and clientes["primary_key"] == ["id"]
    assert [(e["method"], e["selected"], e["generated"]) for e in clientes["endpoints"]] == [
        ("GET", True, False), ("POST", True, False), ("PUT", True, False), ("DELETE", True, False)]

    bitacora = {e["method"]: e["selected"] for e in inv["bitacora"]["endpoints"]}
    assert bitacora == {"GET": True, "POST": True, "PUT": False, "DELETE": False}  # sin PK
    assert inv["users"]["sensitive"] is True and inv["clientes"]["sensitive"] is False


def test_crear_proyecto_valida(client, admin_headers, fake):
    assert new_project(client, admin_headers).status_code == 201
    dup = new_project(client, admin_headers, name="ABMPrueba")  # mismo nombre, otras mayúsculas
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "conflict"

    r = new_project(client, admin_headers, name="otro", tables=("no_existe",))
    assert r.status_code == 400 and "public.no_existe" in r.json()["error"]["message"]
    r = new_project(client, admin_headers, name="otro2", tables=("builder_projects",))  # interna: no existe para el usuario
    assert r.status_code == 400
    assert new_project(client, admin_headers, name="vacio", tables=()).status_code == 201  # sin tablas, se agregan luego
    assert new_project(client, admin_headers, name="x", port=70000).status_code == 422
    assert new_project(client, admin_headers, name="y", ssl_mode="raro").status_code == 422


def test_sin_encryption_key_no_se_crea_ni_se_conecta(client, admin_headers, fake, monkeypatch):
    monkeypatch.setattr(settings, "encryption_key", None)
    r = new_project(client, admin_headers)
    assert r.status_code == 503 and r.json()["error"]["code"] == "encryption_not_configured"
    assert fake.calls == []


def test_listado_con_conteos(client, admin_headers, fake):
    new_project(client, admin_headers, name="Zeta", tables=("clientes",))
    new_project(client, admin_headers, name="alfa", tables=("clientes", "transportistas", "bitacora"))
    rows = client.get("/api/builder/projects", headers=admin_headers).json()
    assert [(p["name"], p["tables_total"]) for p in rows] == [("alfa", 3), ("Zeta", 1)]  # orden sin distinguir mayúsculas


def test_editar_proyecto_y_contrasena(client, admin_headers, fake):
    pid = new_project(client, admin_headers).json()["id"]
    other = new_project(client, admin_headers, name="otro").json()["id"]

    r = client.patch(f"/api/builder/projects/{pid}", json={"name": "Renombrado", "port": 6003, "password": ""}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["name"] == "Renombrado" and r.json()["port"] == 6003
    with SessionLocal() as db:
        assert decrypt_secret(db.get(BuilderProject, pid).encrypted_password) == "p@ss:w/rd#1%"  # vacío = conserva

    client.patch(f"/api/builder/projects/{pid}", json={"password": "nueva-clave"}, headers=admin_headers)
    with SessionLocal() as db:
        assert decrypt_secret(db.get(BuilderProject, pid).encrypted_password) == "nueva-clave"

    assert client.patch(f"/api/builder/projects/{pid}", json={"name": "OTRO"}, headers=admin_headers).status_code == 409
    assert client.patch(f"/api/builder/projects/{pid}", json={"database_name": "x"}, headers=admin_headers).status_code == 422
    assert client.patch(f"/api/builder/projects/{pid}", json={"host": "a b"}, headers=admin_headers).status_code == 400
    assert client.patch(f"/api/builder/projects/{pid}", json={"name": "x"}, headers=admin_headers).status_code == 200
    assert other != pid


def test_probar_conexion_guardada_usa_la_contrasena_descifrada(client, admin_headers, fake):
    pid = new_project(client, admin_headers).json()["id"]
    r = client.post(f"/api/builder/projects/{pid}/test", headers=admin_headers)
    assert r.status_code == 200 and r.json() == {"server_version": "16.2"}
    assert fake.calls[-1][0] == "probe" and fake.calls[-1][1].password == "p@ss:w/rd#1%"
    assert fake.calls[-1][1].database == "digital_platform"


def test_si_cambia_la_clave_de_cifrado_el_error_indica_que_hacer(client, admin_headers, fake, monkeypatch):
    pid = new_project(client, admin_headers).json()["id"]
    monkeypatch.setattr(settings, "encryption_key", "otra-clave-completamente-distinta-" + "z" * 20)
    r = client.post(f"/api/builder/projects/{pid}/test", headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "credentials_unreadable"
    # y al reingresar la contraseña (con la clave nueva) vuelve a funcionar
    assert client.patch(f"/api/builder/projects/{pid}", json={"password": "p@ss:w/rd#1%"}, headers=admin_headers).status_code == 200
    assert client.post(f"/api/builder/projects/{pid}/test", headers=admin_headers).status_code == 200


def test_eliminar_proyecto_borra_su_configuracion_en_cascada(client, admin_headers, fake):
    pid = new_project(client, admin_headers).json()["id"]
    assert client.delete(f"/api/builder/projects/{pid}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/builder/projects/{pid}", headers=admin_headers).status_code == 404
    with engine.connect() as conn:
        for table in ("builder_projects", "builder_resources", "builder_resource_endpoints"):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table


# ---------------------------------------------------------------- inventario
def test_tablas_disponibles_y_agregar(client, admin_headers, fake):
    pid = new_project(client, admin_headers, tables=("clientes",)).json()["id"]
    avail = client.get(f"/api/builder/projects/{pid}/available-tables", headers=admin_headers).json()["tables"]
    names = {(t["schema_name"], t["table_name"]) for t in avail}
    assert ("public", "clientes") not in names and ("public", "transportistas") in names
    assert ("public", "builder_projects") not in names

    body = {"tables": [{"schema_name": "public", "table_name": "transportistas"},
                       {"schema_name": "public", "table_name": "clientes"}]}  # clientes ya está: se ignora
    r = client.post(f"/api/builder/projects/{pid}/resources", json=body, headers=admin_headers)
    assert r.status_code == 201 and [x["table_name"] for x in r.json()] == ["transportistas"]
    assert len(client.get(f"/api/builder/projects/{pid}/resources", headers=admin_headers).json()) == 2

    bad = {"tables": [{"schema_name": "public", "table_name": "no_existe"}]}
    assert client.post(f"/api/builder/projects/{pid}/resources", json=bad, headers=admin_headers).status_code == 400
    assert client.post(f"/api/builder/projects/{pid}/resources", json={"tables": []}, headers=admin_headers).status_code == 422


def test_elegir_endpoints(client, admin_headers, fake):
    pid = new_project(client, admin_headers, tables=("clientes", "bitacora")).json()["id"]
    inv = {r["table_name"]: r["id"] for r in client.get(f"/api/builder/projects/{pid}/resources", headers=admin_headers).json()}

    url = f"/api/builder/projects/{pid}/resources/{inv['clientes']}/endpoints"
    r = client.patch(url, json={"DELETE": False, "PUT": False}, headers=admin_headers)
    assert r.status_code == 200
    assert {e["method"]: e["selected"] for e in r.json()["endpoints"]} == {"GET": True, "POST": True, "PUT": False, "DELETE": False}
    r = client.patch(url, json={"DELETE": True}, headers=admin_headers)  # se puede volver a marcar
    assert {e["method"]: e["selected"] for e in r.json()["endpoints"]}["DELETE"] is True

    url_pk = f"/api/builder/projects/{pid}/resources/{inv['bitacora']}/endpoints"
    assert client.patch(url_pk, json={"PUT": True}, headers=admin_headers).status_code == 400  # sin clave primaria
    assert client.patch(url_pk, json={"POST": False}, headers=admin_headers).status_code == 200
    assert client.patch(url, json={}, headers=admin_headers).status_code == 422
    assert client.patch(url, json={"PATCH": True}, headers=admin_headers).status_code == 422
    assert client.patch(url, json={"GET": None}, headers=admin_headers).status_code == 422


def test_un_endpoint_generado_no_se_puede_modificar_ni_quitar(client, admin_headers, fake):
    pid = new_project(client, admin_headers, tables=("clientes",)).json()["id"]
    rid = client.get(f"/api/builder/projects/{pid}/resources", headers=admin_headers).json()[0]["id"]
    with SessionLocal() as db:  # simula lo que hará el motor de la fase 2
        db.get(BuilderResourceEndpoint, (rid, "GET")).generated = True
        db.get(BuilderResource, rid).status = "PUBLISHED"
        db.commit()

    r = client.patch(f"/api/builder/projects/{pid}/resources/{rid}/endpoints", json={"GET": False}, headers=admin_headers)
    assert r.status_code == 409
    assert client.delete(f"/api/builder/projects/{pid}/resources/{rid}", headers=admin_headers).status_code == 409
    assert client.get("/api/builder/projects", headers=admin_headers).json()[0]["generated_total"] == 1


def test_quitar_tabla_del_inventario(client, admin_headers, fake):
    pid = new_project(client, admin_headers).json()["id"]
    other = new_project(client, admin_headers, name="otro", tables=("clientes",)).json()["id"]
    inv = client.get(f"/api/builder/projects/{pid}/resources", headers=admin_headers).json()
    foreign = client.get(f"/api/builder/projects/{other}/resources", headers=admin_headers).json()[0]["id"]

    assert client.delete(f"/api/builder/projects/{pid}/resources/{inv[0]['id']}", headers=admin_headers).status_code == 204
    assert len(client.get(f"/api/builder/projects/{pid}/resources", headers=admin_headers).json()) == 1
    # una tabla de otro proyecto no se puede tocar desde este
    assert client.delete(f"/api/builder/projects/{pid}/resources/{foreign}", headers=admin_headers).status_code == 404
    url = f"/api/builder/projects/{pid}/resources/{foreign}/endpoints"
    assert client.patch(url, json={"GET": False}, headers=admin_headers).status_code == 404
    with engine.connect() as conn:  # los endpoints de la tabla quitada también se borraron
        assert conn.execute(text("SELECT count(*) FROM builder_resource_endpoints")).scalar() == 4 + 4


def test_proyecto_inexistente(client, admin_headers, fake):
    for path in ("/api/builder/projects/999", "/api/builder/projects/999/resources"):
        assert client.get(path, headers=admin_headers).status_code == 404
