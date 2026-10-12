from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from auth.models import RefreshToken
from core.crud import CRUDBase
from core.errors import BadRequestError, ConflictError
from core.security import hash_password
from users.models import User
from users.schemas import UserCreate, UserUpdate


class UserService(CRUDBase[User, UserCreate, UserUpdate]):
    """Reglas propias de usuarios sobre el CRUD genérico."""

    def _email_taken(self, db: Session, email: str, exclude_id: int | None = None) -> bool:
        stmt = select(func.count()).select_from(User).where(User.email == email)
        if exclude_id is not None:
            stmt = stmt.where(User.id != exclude_id)
        return (db.scalar(stmt) or 0) > 0

    def _other_active_admins(self, db: Session, exclude_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == "admin", User.is_active.is_(True), User.id != exclude_id)
        )
        return db.scalar(stmt) or 0

    def before_create(self, db: Session, values: dict[str, Any], actor: Any) -> dict[str, Any]:
        values["email"] = values["email"].strip().lower()
        if self._email_taken(db, values["email"]):
            raise ConflictError("Ya existe un usuario con ese correo")
        values["hashed_password"] = hash_password(values.pop("password"))
        return values

    def before_update(self, db: Session, obj: User, values: dict[str, Any], actor: Any) -> dict[str, Any]:
        if "email" in values:
            values["email"] = values["email"].strip().lower()
            if values["email"] != obj.email and self._email_taken(db, values["email"], exclude_id=obj.id):
                raise ConflictError("Ya existe un usuario con ese correo")

        is_self = actor is not None and actor.id == obj.id
        loses_admin = obj.role == "admin" and (
            values.get("role", obj.role) != "admin" or values.get("is_active", obj.is_active) is False
        )
        if is_self and values.get("is_active") is False:
            raise BadRequestError("No podés desactivar tu propia cuenta")
        if is_self and "role" in values and values["role"] != obj.role:
            raise BadRequestError("No podés cambiar tu propio rol")
        if loses_admin and self._other_active_admins(db, obj.id) == 0:
            raise BadRequestError("Debe existir al menos un administrador activo")

        revoke_sessions = False
        if "password" in values:
            values["hashed_password"] = hash_password(values.pop("password"))
            revoke_sessions = True
        if values.get("is_active") is False:
            revoke_sessions = True
        if revoke_sessions:  # cambiar la clave o desactivar cierra todas las sesiones
            db.execute(
                delete(RefreshToken).where(RefreshToken.user_id == obj.id),
                execution_options={"synchronize_session": False},
            )
        return values

    def before_delete(self, db: Session, obj: User, actor: Any) -> None:
        if actor is not None and actor.id == obj.id:
            raise BadRequestError("No podés eliminar tu propia cuenta")
        if obj.role == "admin" and obj.is_active and self._other_active_admins(db, obj.id) == 0:
            raise BadRequestError("Debe existir al menos un administrador activo")


users_service = UserService(
    User,
    searchable=("email", "full_name"),
    filterable=("role", "is_active"),
    sortable=("id", "email", "full_name", "role", "is_active", "created_at"),
    default_sort="-id",
    label="Usuario",
)
