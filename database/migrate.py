"""Aplica en orden los scripts de database/migrations/*.sql que falten.

    python database/migrate.py            # aplica pendientes
    python database/migrate.py --status   # solo muestra el estado

Lee la conexión de variables de entorno o de backend/.env:
  - DATABASE_URL, o
  - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD  (la contraseña se codifica sola)
Cada script se ejecuta en una transacción; si falla, no queda a medias.
Se guarda el checksum: si un script ya aplicado se modifica, se avisa.
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "migrations"
ENV_FILE = ROOT.parent / "backend" / ".env"


def database_url() -> URL:
    file_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    env = {**file_values, **os.environ}  # las variables de entorno pisan al archivo

    if env.get("DATABASE_URL"):
        return make_url(env["DATABASE_URL"])

    missing = [k for k in ("DB_HOST", "DB_NAME", "DB_USER") if not env.get(k)]
    if missing:
        donde = f"archivo encontrado: {ENV_FILE}" if ENV_FILE.exists() else f"NO existe el archivo {ENV_FILE}"
        sys.exit(
            "No se pudo armar la conexión a la base de datos.\n"
            f"  Faltan: {', '.join(missing)}  (o definí DATABASE_URL)\n"
            f"  {donde}"
        )
    return URL.create(
        "postgresql+psycopg",
        username=env["DB_USER"],
        password=env.get("DB_PASSWORD") or None,
        host=env["DB_HOST"],
        port=int(env.get("DB_PORT") or 5432),
        database=env["DB_NAME"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="solo mostrar estado")
    args = parser.parse_args()

    url = database_url()
    print(f"Base de datos: {url.render_as_string(hide_password=True)}")
    engine = create_engine(url)
    files = sorted(MIGRATIONS.glob("*.sql"))

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    " filename varchar(255) PRIMARY KEY,"
                    " checksum varchar(64) NOT NULL,"
                    " applied_at timestamptz NOT NULL DEFAULT now())"
                )
            )
            applied = {r[0]: r[1] for r in conn.execute(text("SELECT filename, checksum FROM schema_migrations"))}
    except SQLAlchemyError as exc:
        sys.exit(f"No se pudo conectar o preparar la base de datos:\n  {str(exc.orig if hasattr(exc, 'orig') else exc).strip()}")

    pending = []
    for f in files:
        checksum = hashlib.sha256(f.read_bytes()).hexdigest()
        if f.name in applied:
            note = "" if applied[f.name] == checksum else "  [ADVERTENCIA: el archivo cambió después de aplicarse]"
            print(f"  aplicada   {f.name}{note}")
        else:
            print(f"  pendiente  {f.name}")
            pending.append((f, checksum))

    if args.status or not pending:
        if not pending:
            print("Base de datos al día.")
        return 0

    for f, checksum in pending:
        print(f"Aplicando {f.name} ...")
        with engine.begin() as conn:  # una transacción por archivo
            conn.exec_driver_sql(f.read_text(encoding="utf-8"))
            conn.execute(
                text("INSERT INTO schema_migrations (filename, checksum) VALUES (:f, :c)"),
                {"f": f.name, "c": checksum},
            )
    print("Migraciones aplicadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
