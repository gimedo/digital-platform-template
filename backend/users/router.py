from auth.deps import require_admin
from core.crud_router import build_crud_router
from users.schemas import UserCreate, UserRead, UserUpdate
from users.service import users_service

# CRUD completo de usuarios, solo para administradores.
router = build_crud_router(
    crud=users_service,
    read_schema=UserRead,
    create_schema=UserCreate,
    update_schema=UserUpdate,
    prefix="/users",
    tags=["users"],
    read_dependency=require_admin,
    write_dependency=require_admin,
)
