from datetime import datetime

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, false, func, true)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class BuilderProject(Base):
    """Un proyecto = una conexión a una base de datos + su inventario de tablas/APIs."""

    __tablename__ = "builder_projects"
    __table_args__ = (
        CheckConstraint("engine IN ('postgresql')", name="ck_builder_projects_engine"),
        CheckConstraint("ssl_mode IN ('disable', 'prefer', 'require')", name="ck_builder_projects_ssl_mode"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="ck_builder_projects_port"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    engine: Mapped[str] = mapped_column(String(20), default="postgresql", server_default="postgresql")
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=5432, server_default="5432")
    database_name: Mapped[str] = mapped_column(String(128))
    username: Mapped[str] = mapped_column(String(128))
    encrypted_password: Mapped[str] = mapped_column(Text)
    ssl_mode: Mapped[str] = mapped_column(String(20), default="prefer", server_default="prefer")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    resources: Mapped[list["BuilderResource"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="BuilderResource.schema_name, BuilderResource.table_name",
    )


# Nombre de proyecto único sin distinguir mayúsculas.
Index("uq_builder_projects_name", func.lower(BuilderProject.name), unique=True)


class BuilderResource(Base):
    """Una tabla del inventario de un proyecto."""

    __tablename__ = "builder_resources"
    __table_args__ = (
        UniqueConstraint("project_id", "schema_name", "table_name", name="uq_builder_resources_table"),
        CheckConstraint("status IN ('NOT_GENERATED', 'PUBLISHED', 'DISABLED', 'ERROR')", name="ck_builder_resources_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("builder_projects.id", ondelete="CASCADE"), index=True)
    schema_name: Mapped[str] = mapped_column(String(128))
    table_name: Mapped[str] = mapped_column(String(128))
    primary_key: Mapped[list] = mapped_column(JSON, default=list)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    status: Mapped[str] = mapped_column(String(20), default="NOT_GENERATED", server_default="NOT_GENERATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped[BuilderProject] = relationship(back_populates="resources")
    endpoints: Mapped[list["BuilderResourceEndpoint"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class BuilderResourceEndpoint(Base):
    """Estado de cada endpoint (GET/POST/PUT/DELETE) de una tabla: elegido y/o ya generado."""

    __tablename__ = "builder_resource_endpoints"
    __table_args__ = (CheckConstraint("method IN ('GET', 'POST', 'PUT', 'DELETE')", name="ck_builder_endpoints_method"),)

    resource_id: Mapped[int] = mapped_column(ForeignKey("builder_resources.id", ondelete="CASCADE"), primary_key=True)
    method: Mapped[str] = mapped_column(String(10), primary_key=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    generated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    resource: Mapped[BuilderResource] = relationship(back_populates="endpoints")
