"""Cifrado simétrico (Fernet) para secretos guardados en la base, como las contraseñas de las conexiones.

La clave sale de ENCRYPTION_KEY (backend/.env). Se deriva con HKDF, así que puede ser cualquier texto
aleatorio largo; no hace falta que tenga un formato especial.
"""
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from core.config import settings
from core.errors import AppError


class EncryptionNotConfiguredError(AppError):
    status_code = 503
    code = "encryption_not_configured"


class UnreadableSecretError(AppError):
    status_code = 409
    code = "credentials_unreadable"


def _fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        raise EncryptionNotConfiguredError(
            "Falta ENCRYPTION_KEY en backend/.env. Generá una con: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))" y reiniciá el backend.'
        )
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"digital-platform/stored-secrets").derive(
        key.encode("utf-8")
    )
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise UnreadableSecretError(
            "No se pudo leer la contraseña guardada (¿cambió ENCRYPTION_KEY?). "
            "Editá la conexión y volvé a ingresar la contraseña."
        ) from None
