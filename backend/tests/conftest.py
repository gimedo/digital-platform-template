"""Pruebas de integración.

Por defecto usan SQLite en memoria (rápido, sin instalar nada). Para probar contra
PostgreSQL real, con las migraciones ya aplicadas:

    $env:TEST_DATABASE_URL = "postgresql+psycopg://usuario:clave@localhost:5432/digital_platform_test"
    pytest

Con TEST_DATABASE_URL también se ejecutan las pruebas del conector contra un servidor real
(crean y borran un esquema temporal `bld_test_*`; no tocan tus datos).
"""
import os

os.environ.setdefault("JWT_SECRET", "clave-de-pruebas-" + "x" * 32)
# Valores fijos para que el .env del desarrollador no altere las pruebas.
os.environ["ENCRYPTION_KEY"] = "clave-de-cifrado-de-pruebas-" + "y" * 32
os.environ["BUILDER_ALLOWED_HOSTS"] = ""
TEST_DB = os.environ.get("TEST_DATABASE_URL")
os.environ["DATABASE_URL"] = TEST_DB or "sqlite+pysqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import auth.models  # noqa: E402,F401
import builder.models  # noqa: E402,F401
import users.models  # noqa: E402,F401
from auth.rate_limit import login_limiter  # noqa: E402
from core.database import Base, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from users.schemas import UserCreate  # noqa: E402
from users.service import users_service  # noqa: E402

PASSWORD = "Clave-segura-123"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if not TEST_DB:
        Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean():
    login_limiter.clear()
    with engine.begin() as conn:
        # Primero lo que depende de users.
        for table in ("builder_resource_endpoints", "builder_resources", "builder_projects", "refresh_tokens", "users"):
            conn.execute(text(f"DELETE FROM {table}"))
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user():
    def _make(email="admin@example.com", role="admin", password=PASSWORD, full_name="Usuario Prueba", is_active=True):
        with SessionLocal() as db:
            return users_service.create(
                db,
                UserCreate(email=email, full_name=full_name, password=password, role=role, is_active=is_active),
            )

    return _make


@pytest.fixture
def login(client):
    def _login(email="admin@example.com", password=PASSWORD):
        return client.post("/api/auth/login", json={"email": email, "password": password})

    return _login


@pytest.fixture
def admin_headers(make_user, login):
    make_user()
    token = login().json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
