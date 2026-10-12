from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from users.constants import Role


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)


class UserCreate(_Input):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=12, max_length=128)
    role: Role = Role.USER
    is_active: bool = True


class UserUpdate(_Input):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    role: Role | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> "UserUpdate":
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"'{name}' no puede ser nulo")
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime
