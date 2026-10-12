from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Digital Platform"
    environment: str = "development"  # development | production

    # Base de datos: usar DATABASE_URL *o* las variables DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD.
    # Si están las dos, manda DATABASE_URL.
    database_url: str | None = None
    db_host: str | None = None
    db_port: int = 5432
    db_name: str | None = None
    db_user: str | None = None
    db_password: str = ""

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    refresh_reuse_grace_seconds: int = 10

    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cors_origins: str = ""

    login_max_attempts: int = 5
    login_window_seconds: int = 300

    max_page_size: int = 100

    # --- API Builder ---
    # Clave para cifrar las contraseñas de las conexiones guardadas (mínimo 32 caracteres).
    # Si cambia, hay que volver a ingresar las contraseñas de los proyectos.
    encryption_key: str | None = None
    # Servidores a los que el Builder puede conectarse. Vacío = cualquiera.
    # Acepta IP, rangos CIDR, nombres y comodines: 192.168.50.0/24,db.interno,*.miempresa.com
    builder_allowed_hosts: str = ""
    builder_connect_timeout: int = 5
    builder_query_timeout_seconds: int = 15

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> URL:
        """URL de conexión. Con DB_* la contraseña se codifica sola (acepta @ : / # etc.)."""
        if self.database_url:
            return make_url(self.database_url)
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @field_validator("encryption_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _validate_database(self) -> "Settings":
        if not self.database_url:
            missing = [
                name
                for name, value in (("DB_HOST", self.db_host), ("DB_NAME", self.db_name), ("DB_USER", self.db_user))
                if not value
            ]
            if missing:
                raise ValueError(
                    "Falta configurar la base de datos: definí DATABASE_URL o, en su lugar, "
                    f"estas variables: {', '.join(missing)} (y DB_PORT / DB_PASSWORD)."
                )
        return self

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        if self.jwt_secret.startswith("CAMBIAR_POR"):
            raise ValueError("Configurá JWT_SECRET en backend/.env con un valor aleatorio propio.")
        if self.encryption_key is not None:
            if self.encryption_key.startswith("CAMBIAR_POR") or len(self.encryption_key) < 32:
                raise ValueError("ENCRYPTION_KEY debe ser un valor aleatorio propio de al menos 32 caracteres.")
        return self

    @model_validator(mode="after")
    def _production_requires_secure_cookie(self) -> "Settings":
        if self.is_production and not self.cookie_secure:
            raise ValueError("En producción COOKIE_SECURE debe ser true (HTTPS).")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
