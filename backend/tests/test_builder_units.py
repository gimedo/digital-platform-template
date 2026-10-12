"""Reglas puras del Builder: sin base de datos ni red."""
import pytest

from builder import netguard
from builder.rules import default_endpoints, is_internal_table, is_sensitive_table
from builder.schemas import ConnectionInput, ProjectUpdate
from core import crypto
from core.config import settings
from core.errors import BadRequestError


# ---------------- tablas sensibles / internas ----------------
@pytest.mark.parametrize(
    "name",
    ["users", "usuarios", "app_users", "refresh_tokens", "UserSessions", "api_keys_apikey", "credenciales_acceso",
     "password_resets", "oauth_clients", "login-attempts"],
)
def test_detecta_tablas_sensibles(name):
    assert is_sensitive_table(name)


@pytest.mark.parametrize("name", ["clientes", "transportistas", "authors", "pedidos", "accounting", "userinfo_x"])
def test_no_marca_como_sensibles_tablas_comunes(name):
    assert not is_sensitive_table(name)


def test_tablas_internas_de_la_plataforma():
    assert is_internal_table("builder_projects") and is_internal_table("Builder_Resources")
    assert is_internal_table("schema_migrations")
    assert not is_internal_table("clientes") and not is_internal_table("my_builder_notes")


def test_endpoints_por_defecto_segun_clave_primaria():
    assert default_endpoints(True) == {"GET": True, "POST": True, "PUT": True, "DELETE": True}
    assert default_endpoints(False) == {"GET": True, "POST": True, "PUT": False, "DELETE": False}


# ---------------- validación del servidor ----------------
@pytest.mark.parametrize("host", ["localhost", "192.168.50.11", "db-1.interno.local", "mi_servicio", "::1", "2001:db8::1"])
def test_hosts_validos(host):
    assert netguard.normalize_host(host) == host


@pytest.mark.parametrize(
    "host", ["", "   ", "/var/run/postgresql", "a,b", "host name", "db;drop", "-oProxyCommand=x", "host?x=1", "a" * 300, "user@host"]
)
def test_hosts_invalidos(host):
    with pytest.raises(BadRequestError):
        netguard.normalize_host(host)


def test_lista_de_hosts_permitidos(monkeypatch):
    monkeypatch.setattr(settings, "builder_allowed_hosts", "192.168.50.0/24, db.interno ,*.miempresa.com, 10.0.0.5")
    for ok in ("192.168.50.11", "10.0.0.5", "DB.interno", "pg.miempresa.com", "a.b.miempresa.com"):
        assert netguard.ensure_host_allowed(ok) == ok
    for bad in ("192.168.51.11", "10.0.0.6", "otro.interno", "miempresa.com", "evil-miempresa.com", "127.0.0.1"):
        with pytest.raises(BadRequestError):
            netguard.ensure_host_allowed(bad)


def test_sin_lista_se_permite_cualquier_host_valido(monkeypatch):
    monkeypatch.setattr(settings, "builder_allowed_hosts", "")
    assert netguard.ensure_host_allowed("cualquiera.example.com") == "cualquiera.example.com"


# ---------------- cifrado ----------------
def test_cifrado_ida_y_vuelta_y_no_deja_el_texto_plano():
    token = crypto.encrypt_secret("p@ss:w/rd#1%")
    assert "p@ss" not in token and token != crypto.encrypt_secret("p@ss:w/rd#1%")  # distinto cada vez (IV)
    assert crypto.decrypt_secret(token) == "p@ss:w/rd#1%"
    assert crypto.decrypt_secret(crypto.encrypt_secret("")) == ""


def test_cifrado_con_otra_clave_no_se_puede_leer(monkeypatch):
    token = crypto.encrypt_secret("secreta")
    monkeypatch.setattr(settings, "encryption_key", "otra-clave-completamente-distinta-" + "z" * 20)
    with pytest.raises(crypto.UnreadableSecretError):
        crypto.decrypt_secret(token)


def test_sin_clave_configurada_el_error_es_claro(monkeypatch):
    monkeypatch.setattr(settings, "encryption_key", None)
    with pytest.raises(crypto.EncryptionNotConfiguredError) as exc:
        crypto.encrypt_secret("x")
    assert "ENCRYPTION_KEY" in exc.value.message


# ---------------- esquemas ----------------
def test_la_contrasena_no_se_recorta():
    data = ConnectionInput(host=" db ", username=" u ", password="  con espacios  ")
    assert data.password == "  con espacios  " and data.host == "db" and data.username == "u"


def test_esquemas_rechazan_campos_desconocidos_y_nulos():
    with pytest.raises(ValueError):
        ConnectionInput(host="h", username="u", extra_field=1)
    with pytest.raises(ValueError):
        ProjectUpdate(database_name="otra")  # la base no se cambia
    with pytest.raises(ValueError):
        ProjectUpdate(name=None)
    assert ProjectUpdate(password=None).password is None  # None = no cambiar la contraseña
