from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from auth.models import RefreshToken
from core.config import settings
from core.errors import UnauthorizedError
from core.security import (
    hash_password,
    hash_token,
    new_refresh_token,
    password_needs_rehash,
    verify_dummy,
    verify_password,
)
from users.models import User


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Devuelve el usuario si las credenciales son válidas; None en cualquier otro caso."""
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        verify_dummy(password)
        return None
    if not verify_password(user.hashed_password, password) or not user.is_active:
        return None
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
        db.commit()
    return user


def issue_refresh_token(db: Session, user: User) -> str:
    raw, digest = new_refresh_token()
    now = datetime.now(timezone.utc)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=digest,
            expires_at=now + timedelta(days=settings.refresh_token_days),
        )
    )
    db.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < now),
        execution_options={"synchronize_session": False},
    )  # limpieza oportuna
    db.commit()
    return raw


def revoke_all_for_user(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    db.commit()


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[User, str]:
    """Valida el token de refresco, lo revoca y emite uno nuevo (rotación)."""
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if token is None:
        raise UnauthorizedError("Sesión inválida")

    now = datetime.now(timezone.utc)
    if token.revoked_at is not None:
        revoked_at = token.revoked_at if token.revoked_at.tzinfo else token.revoked_at.replace(tzinfo=timezone.utc)
        if (now - revoked_at).total_seconds() > settings.refresh_reuse_grace_seconds:
            # Reutilización de un token ya rotado: posible robo -> se cierran todas las sesiones.
            revoke_all_for_user(db, token.user_id)
        raise UnauthorizedError("Sesión inválida")

    expires_at = token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise UnauthorizedError("Sesión vencida")

    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Sesión inválida")

    token.revoked_at = now
    db.commit()
    return user, issue_refresh_token(db, user)


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if token is not None and token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        db.commit()
