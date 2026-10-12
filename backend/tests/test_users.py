from tests.conftest import PASSWORD


def test_solo_admin_gestiona_usuarios(client, make_user, login):
    make_user(email="comun@example.com", role="user")
    token = login(email="comun@example.com").json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/users", headers=h).status_code == 403
    assert client.post("/api/users", json={}, headers=h).status_code == 403
    assert client.get("/api/users").status_code == 401


def test_crud_completo(client, admin_headers):
    r = client.post(
        "/api/users",
        json={"email": "Nuevo@Example.com", "full_name": "Nuevo", "password": PASSWORD, "role": "user"},
        headers=admin_headers,
    )
    assert r.status_code == 201
    u = r.json()
    assert u["email"] == "nuevo@example.com"  # normalizado
    assert "password" not in u and "hashed_password" not in u

    assert client.get(f"/api/users/{u['id']}", headers=admin_headers).json()["full_name"] == "Nuevo"

    r = client.patch(f"/api/users/{u['id']}", json={"full_name": "Renombrado"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["full_name"] == "Renombrado"

    assert client.delete(f"/api/users/{u['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/users/{u['id']}", headers=admin_headers).status_code == 404


def test_cambiar_password_permite_login_con_la_nueva(client, make_user, login, admin_headers):
    u = make_user(email="cambia@example.com", role="user")
    nueva = "Otra-clave-segura-9"
    assert client.patch(f"/api/users/{u.id}", json={"password": nueva}, headers=admin_headers).status_code == 200
    assert login(email="cambia@example.com").status_code == 401
    assert login(email="cambia@example.com", password=nueva).status_code == 200


def test_correo_duplicado_da_409(client, admin_headers):
    body = {"email": "dup@example.com", "full_name": "Dup", "password": PASSWORD}
    assert client.post("/api/users", json=body, headers=admin_headers).status_code == 201
    r = client.post("/api/users", json=body, headers=admin_headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


def test_validacion_422_no_devuelve_el_valor_enviado(client, admin_headers):
    r = client.post(
        "/api/users",
        json={"email": "no-es-correo", "full_name": "X", "password": "corta", "rol_inventado": "x"},
        headers=admin_headers,
    )
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    campos = {d["field"] for d in err["details"]}
    assert {"email", "password", "rol_inventado"} <= campos
    assert "corta" not in r.text  # la contraseña enviada no se refleja


def test_update_rechaza_nulos_explicitos(client, make_user, admin_headers):
    u = make_user(email="x@example.com", role="user")
    r = client.patch(f"/api/users/{u.id}", json={"email": None}, headers=admin_headers)
    assert r.status_code == 422


def test_no_puede_eliminarse_ni_desactivarse_a_si_mismo(client, make_user, login):
    admin = make_user(email="a1@example.com")
    make_user(email="a2@example.com")  # hay otro admin: no aplica la regla del último admin
    h = {"Authorization": f"Bearer {login(email='a1@example.com').json()['access_token']}"}
    assert client.delete(f"/api/users/{admin.id}", headers=h).status_code == 400
    assert client.patch(f"/api/users/{admin.id}", json={"is_active": False}, headers=h).status_code == 400
    assert client.patch(f"/api/users/{admin.id}", json={"role": "user"}, headers=h).status_code == 400


def test_no_se_puede_dejar_el_sistema_sin_administrador(make_user):
    """La regla protege también a scripts/servicios que llaman al CRUD sin pasar por la API."""
    import pytest

    from core.database import SessionLocal
    from core.errors import BadRequestError
    from users.service import users_service

    unico = make_user(email="unico@example.com", role="admin")
    with SessionLocal() as db:
        with pytest.raises(BadRequestError):
            users_service.remove(db, db.get(type(unico), unico.id))
        with pytest.raises(BadRequestError):
            users_service.update(db, db.get(type(unico), unico.id), {"role": "user"})
        # con un segundo administrador activo sí se puede
        make_user(email="segundo@example.com", role="admin")
        users_service.update(db, db.get(type(unico), unico.id), {"role": "user"})


def test_listado_busqueda_filtro_orden_y_paginacion(client, make_user, admin_headers):
    for i in range(5):
        make_user(email=f"user{i}@example.com", role="user", full_name=f"Persona {i}", is_active=(i != 4))
    r = client.get("/api/users?limit=2&offset=0&order_by=email", headers=admin_headers)
    body = r.json()
    assert body["total"] == 6 and body["limit"] == 2 and len(body["items"]) == 2
    assert [i["email"] for i in body["items"]] == ["admin@example.com", "user0@example.com"]

    assert client.get("/api/users?search=persona 3", headers=admin_headers).json()["total"] == 1
    assert client.get("/api/users?is_active=false", headers=admin_headers).json()["total"] == 1
    assert client.get("/api/users?role=admin", headers=admin_headers).json()["total"] == 1
    assert client.get("/api/users?search=%25", headers=admin_headers).json()["total"] == 0  # % se escapa
    assert client.get("/api/users?limit=100000", headers=admin_headers).json()["limit"] == 100


def test_filtros_y_orden_fuera_de_la_lista_blanca_dan_400(client, admin_headers):
    for q in ("hashed_password=abc", "id=1", "order_by=hashed_password", "is_active=quizas"):
        r = client.get(f"/api/users?{q}", headers=admin_headers)
        assert r.status_code == 400, q
        assert r.json()["error"]["code"] == "bad_request"


def test_intento_de_inyeccion_sql_no_rompe_nada(client, admin_headers):
    r = client.get("/api/users", params={"search": "'; DROP TABLE users; --"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/api/users", headers=admin_headers).json()["total"] == 1
    assert client.get("/api/users", params={"order_by": "id; DROP TABLE users"}, headers=admin_headers).status_code == 400


def test_404_y_405_usan_el_formato_uniforme(client, admin_headers):
    r = client.get("/api/users/99999", headers=admin_headers)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.get("/api/ruta-inexistente")
    assert r.status_code == 404 and "error" in r.json()
