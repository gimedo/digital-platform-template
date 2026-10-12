from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SslMode = Literal["disable", "prefer", "require"]


class _In(BaseModel):
    # Sin str_strip_whitespace global: la contraseña no debe recortarse.
    model_config = ConfigDict(extra="forbid")


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ConnectionInput(_In):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(5432, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field("", max_length=256)
    ssl_mode: SslMode = "prefer"
    database: str | None = Field(None, max_length=128)

    _strip_text = field_validator("host", "username", "database", mode="before")(_strip)


class DiscoverRequest(ConnectionInput):
    database: str = Field(min_length=1, max_length=128)


class TableRef(_In):
    schema_name: str = Field(min_length=1, max_length=128)
    table_name: str = Field(min_length=1, max_length=128)


class ProjectCreate(_In):
    name: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(5432, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field("", max_length=256)
    ssl_mode: SslMode = "prefer"
    database_name: str = Field(min_length=1, max_length=128)
    tables: list[TableRef] = Field(default_factory=list, max_length=1000)

    _strip_text = field_validator("name", "host", "username", "database_name", mode="before")(_strip)


class ProjectUpdate(_In):
    """La base de datos no se cambia: para otra base se crea otro proyecto."""

    name: str | None = Field(None, min_length=1, max_length=80)
    host: str | None = Field(None, min_length=1, max_length=255)
    port: int | None = Field(None, ge=1, le=65535)
    username: str | None = Field(None, min_length=1, max_length=128)
    password: str | None = Field(None, max_length=256)  # vacío o ausente = no cambiar
    ssl_mode: SslMode | None = None

    _strip_text = field_validator("name", "host", "username", mode="before")(_strip)

    @model_validator(mode="after")
    def _no_nulls_except_password(self) -> "ProjectUpdate":
        for field in self.model_fields_set - {"password"}:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' no puede ser nulo")
        return self


class ResourcesAdd(_In):
    tables: list[TableRef] = Field(min_length=1, max_length=1000)


class EndpointsUpdate(_In):
    GET: bool | None = None
    POST: bool | None = None
    PUT: bool | None = None
    DELETE: bool | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "EndpointsUpdate":
        if not self.model_fields_set:
            raise ValueError("Indicá al menos un endpoint")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' no puede ser nulo")
        return self


# ---------------- respuestas ----------------
class ProbeResponse(BaseModel):
    server_version: str
    databases: list[str]


class DiscoveredTableRead(BaseModel):
    schema_name: str
    table_name: str
    primary_key: list[str]
    has_primary_key: bool
    sensitive: bool


class TablesResponse(BaseModel):
    tables: list[DiscoveredTableRead]


class EndpointState(BaseModel):
    method: str
    selected: bool
    generated: bool


class ResourceRead(BaseModel):
    id: int
    schema_name: str
    table_name: str
    primary_key: list[str]
    has_primary_key: bool
    sensitive: bool
    status: str
    endpoints: list[EndpointState]


class ProjectRead(BaseModel):
    id: int
    name: str
    engine: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_mode: str
    tables_total: int
    generated_total: int
    created_at: datetime
    updated_at: datetime


class ProjectTestResponse(BaseModel):
    server_version: str
