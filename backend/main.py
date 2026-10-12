import logging

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

# Los modelos se importan para registrarse en Base.metadata.
import auth.models  # noqa: F401
import builder.models  # noqa: F401
import users.models  # noqa: F401
from auth.router import router as auth_router
from builder.router import router as builder_router
from core.config import settings
from core.database import get_db
from core.errors import register_exception_handlers
from users.router import router as users_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)

register_exception_handlers(app)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

api = APIRouter(prefix="/api")


@api.get("/health", tags=["system"], summary="Estado del servicio")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unreachable"})
    return {"status": "ok", "database": "connected"}


api.include_router(auth_router)
api.include_router(users_router)
api.include_router(builder_router)
# Para agregar un módulo nuevo: api.include_router(<mi_modulo>_router)

app.include_router(api)
