"""Contraseñas (Argon2id), JWT de acceso y tokens de refresco opacos."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from core.config import settings

# Argon2id con los parámetros por defecto de argon2-cffi (superan el mínimo recomendado por OWASP).
_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("contraseña-ficticia-para-igualar-tiempos")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_dummy(password: str) -> None:
    """Gasta el mismo tiempo que una verificación real (evita enumerar usuarios por tiempo de respuesta)."""
    verify_password(_DUMMY_HASH, password)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(*, user_id: int, role: str) -> tuple[str, int]:
    """Devuelve (token, segundos_de_vida)."""
    now = datetime.now(timezone.utc)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict:
    """Lanza jwt.PyJWTError si el token es inválido, está vencido o no es de acceso."""
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """Devuelve (token_en_claro, hash_para_guardar). En la BD solo se guarda el hash."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)
