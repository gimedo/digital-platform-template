import jwt

from core.config import settings
from tests.conftest import PASSWORD


def test_login_ok_devuelve_token_usuario_y_cookie_httponly(client, make_user, login):
    make_user()
    r = login()
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == settings.access_token_minutes * 60
    assert body["user"]["email"] == "admin@example.com"
    assert "hashed_password" not in body["user"] and "password" not in body["user"]
    set_cookie = r.headers["set-cookie"].lower()
    assert "refresh_token=" in set_cookie and "httponly" in set_cookie and "path=/api/auth" in set_cookie


def test_login_error_es_generico(client, make_user, login):
    make_user()
    make_user(email="inactivo@example.com", is_active=False)
    mensajes = {
        login(password="incorrecta-123456").json()["error"]["message"],
        login(email="noexiste@example.com").json()["error"]["message"],
        login(email="inactivo@example.com").json()["error"]["message"],
    }
    assert mensajes == {"Credenciales inválidas"}


def test_login_bloquea_tras_intentos_fallidos(client, make_user, login):
    make_user()
    for _ in range(settings.login_max_attempts):
        assert login(password="incorrecta-123456").status_code == 401
    r = login()  # aun con la clave correcta queda bloqueado
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_me_requiere_token_valido(client, admin_headers):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer basura"}).status_code == 401
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200 and r.json()["role"] == "admin"


def test_token_vencido_o_con_firma_ajena_es_rechazado(client, make_user):
    user = make_user()
    ajeno = jwt.encode({"sub": str(user.id), "type": "access", "iat": 1, "exp": 2}, "otra-clave" * 5, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {ajeno}"}).status_code == 401
    vencido = jwt.encode({"sub": str(user.id), "type": "access", "iat": 1, "exp": 2}, settings.jwt_secret, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401


def test_refresh_rota_el_token(client, make_user, login):
    make_user()
    login()
    primero = client.cookies.get("refresh_token", path="/api/auth")
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    segundo = client.cookies.get("refresh_token", path="/api/auth")
    assert primero and segundo and primero != segundo


def test_reutilizar_un_refresh_viejo_cierra_todas_las_sesiones(client, make_user, login, monkeypatch):
    monkeypatch.setattr(settings, "refresh_reuse_grace_seconds", 0)
    make_user()
    login()
    viejo = client.cookies.get("refresh_token", path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 200
    # un atacante (o un cliente desfasado) vuelve a presentar el token ya rotado
    client.cookies.clear()
    client.cookies.set("refresh_token", viejo, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401
    # el token nuevo también quedó revocado
    client.cookies.clear()
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revoca_el_refresh(client, make_user, login):
    make_user()
    login()
    token = client.cookies.get("refresh_token", path="/api/auth")
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("refresh_token", token, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_fallido_limpia_la_cookie(client):
    client.cookies.set("refresh_token", "no-existe", path="/api/auth")
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401
    assert "refresh_token=" in r.headers["set-cookie"] and "max-age=0" in r.headers["set-cookie"].lower()


def test_usuario_desactivado_pierde_acceso_inmediato(client, make_user, login, admin_headers):
    otro = make_user(email="otro@example.com", role="user")
    token = login(email="otro@example.com").json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    r = client.patch(f"/api/users/{otro.id}", json={"is_active": False}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
