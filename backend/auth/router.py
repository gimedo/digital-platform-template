from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from auth.rate_limit import login_limiter
from auth.schemas import LoginRequest, TokenResponse
from auth.service import authenticate, issue_refresh_token, revoke_refresh_token, rotate_refresh_token
from core.config import settings
from core.database import get_db
from core.errors import UnauthorizedError, error_body
from core.security import create_access_token
from users.models import User
from users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api/auth"  # la cookie solo viaja a los endpoints de auth


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path=COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


def _token_response(user: User) -> TokenResponse:
    access, expires_in = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=access, expires_in=expires_in, user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesión")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "desconocida"
    key = f"{client_ip}|{payload.email.strip().lower()}"
    login_limiter.check(key)

    user = authenticate(db, payload.email, payload.password)
    if user is None:
        login_limiter.register_failure(key)
        # Mismo mensaje para "usuario inexistente", "clave incorrecta" y "usuario inactivo".
        raise UnauthorizedError("Credenciales inválidas")

    login_limiter.reset(key)
    _set_refresh_cookie(response, issue_refresh_token(db, user))
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse, summary="Renovar el token de acceso")
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
):
    if not refresh_token:
        raise UnauthorizedError("Sin sesión")
    try:
        user, new_token = rotate_refresh_token(db, refresh_token)
    except UnauthorizedError as exc:
        # Respuesta propia: las cookies del `response` inyectado no viajan en una excepción.
        failure = JSONResponse(
            status_code=401,
            content=error_body(exc.code, exc.message),
            headers={"WWW-Authenticate": "Bearer"},
        )
        _clear_refresh_cookie(failure)
        return failure
    _set_refresh_cookie(response, new_token)
    return _token_response(user)


@router.post("/logout", status_code=204, summary="Cerrar sesión")
def logout(db: Session = Depends(get_db), refresh_token: str | None = Cookie(default=None)):
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    response = Response(status_code=204)
    _clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserRead, summary="Usuario autenticado")
def me(user: User = Depends(get_current_user)):
    return user
