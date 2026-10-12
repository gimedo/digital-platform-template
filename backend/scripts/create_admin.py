"""Crea el primer administrador.

    python -m scripts.create_admin
    python -m scripts.create_admin --email admin@empresa.com --name "Administrador"
"""
import argparse
import getpass
import sys

from pydantic import ValidationError

import auth.models  # noqa: F401
import users.models  # noqa: F401
from core.database import SessionLocal
from core.errors import AppError
from users.schemas import UserCreate
from users.service import users_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Crear un usuario administrador")
    parser.add_argument("--email")
    parser.add_argument("--name")
    args = parser.parse_args()

    email = args.email or input("Correo: ").strip()
    name = args.name or input("Nombre completo: ").strip()
    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if password != getpass.getpass("Repetir contraseña: "):
        print("Las contraseñas no coinciden.")
        return 1

    try:
        data = UserCreate(email=email, full_name=name, password=password, role="admin")
    except ValidationError as exc:
        for err in exc.errors():
            print(f"- {'.'.join(str(p) for p in err['loc'])}: {err['msg']}")
        return 1

    with SessionLocal() as db:
        try:
            user = users_service.create(db, data)
        except AppError as exc:
            print(f"Error: {exc.message}")
            return 1
    print(f"Administrador creado: {user.email} (id {user.id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
