"""Casos de uso del API Builder: proyectos (conexión + base) y su inventario de tablas."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from builder.connectors import ConnectionParams, DiscoveredTable, ProbeResult, get_connector
from builder.models import BuilderProject, BuilderResource, BuilderResourceEndpoint
from builder.netguard import ensure_host_allowed
from builder.rules import METHODS, NEEDS_PRIMARY_KEY, default_endpoints, is_internal_table, is_sensitive_table
from builder.schemas import (ConnectionInput, DiscoveredTableRead, EndpointState, EndpointsUpdate, ProjectCreate,
                             ProjectRead, ProjectUpdate, ResourceRead, TableRef)
from core.crypto import decrypt_secret, encrypt_secret
from core.errors import BadRequestError, ConflictError, NotFoundError
from users.models import User

ENGINE = "postgresql"  # único motor del MVP; el contrato de conectores permite sumar otros


# ---------------------------------------------------------------- conexión y descubrimiento
def probe_connection(data: ConnectionInput) -> ProbeResult:
    host = ensure_host_allowed(data.host)
    params = ConnectionParams(host, data.port, data.username, data.password, data.ssl_mode, data.database)
    return get_connector(ENGINE).probe(params)


def _visible(tables: list[DiscoveredTable]) -> list[DiscoveredTable]:
    return [t for t in tables if not is_internal_table(t.table_name)]


def discover_tables(data: ConnectionInput) -> list[DiscoveredTable]:
    host = ensure_host_allowed(data.host)
    params = ConnectionParams(host, data.port, data.username, data.password, data.ssl_mode, data.database)
    return _visible(get_connector(ENGINE).list_tables(params))


def _params(project: BuilderProject) -> ConnectionParams:
    return ConnectionParams(
        host=project.host,
        port=project.port,
        username=project.username,
        password=decrypt_secret(project.encrypted_password),
        ssl_mode=project.ssl_mode,
        database=project.database_name,
    )


def _live_tables(project: BuilderProject) -> list[DiscoveredTable]:
    ensure_host_allowed(project.host)  # la lista de hosts permitidos puede haber cambiado desde que se creó
    return _visible(get_connector(project.engine).list_tables(_params(project)))


# ---------------------------------------------------------------- serialización
def table_read(t: DiscoveredTable) -> DiscoveredTableRead:
    return DiscoveredTableRead(
        schema_name=t.schema_name,
        table_name=t.table_name,
        primary_key=list(t.primary_key),
        has_primary_key=bool(t.primary_key),
        sensitive=is_sensitive_table(t.table_name),
    )


def resource_read(resource: BuilderResource) -> ResourceRead:
    by_method = {e.method: e for e in resource.endpoints}
    return ResourceRead(
        id=resource.id,
        schema_name=resource.schema_name,
        table_name=resource.table_name,
        primary_key=list(resource.primary_key or []),
        has_primary_key=bool(resource.primary_key),
        sensitive=resource.is_sensitive,
        status=resource.status,
        endpoints=[
            EndpointState(method=m, selected=by_method[m].selected, generated=by_method[m].generated)
            for m in METHODS
            if m in by_method
        ],
    )


def project_read(project: BuilderProject) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        engine=project.engine,
        host=project.host,
        port=project.port,
        database_name=project.database_name,
        username=project.username,
        ssl_mode=project.ssl_mode,
        tables_total=len(project.resources),
        generated_total=sum(1 for r in project.resources if r.status == "PUBLISHED"),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


# ---------------------------------------------------------------- proyectos
def list_projects(db: Session) -> list[BuilderProject]:
    stmt = select(BuilderProject).options(selectinload(BuilderProject.resources)).order_by(func.lower(BuilderProject.name))
    return list(db.scalars(stmt).all())


def get_project(db: Session, project_id: int) -> BuilderProject:
    project = db.get(BuilderProject, project_id)
    if project is None:
        raise NotFoundError("Proyecto no encontrado")
    return project


def _ensure_name_free(db: Session, name: str, exclude_id: int | None = None) -> None:
    stmt = select(func.count()).select_from(BuilderProject).where(func.lower(BuilderProject.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(BuilderProject.id != exclude_id)
    if (db.scalar(stmt) or 0) > 0:
        raise ConflictError("Ya existe un proyecto con ese nombre")


def _new_resource(table: DiscoveredTable) -> BuilderResource:
    resource = BuilderResource(
        schema_name=table.schema_name,
        table_name=table.table_name,
        primary_key=list(table.primary_key),
        is_sensitive=is_sensitive_table(table.table_name),
        status="NOT_GENERATED",
    )
    resource.endpoints = [
        BuilderResourceEndpoint(method=m, selected=selected, generated=False)
        for m, selected in default_endpoints(bool(table.primary_key)).items()
    ]
    return resource


def _resolve(refs: list[TableRef], live: list[DiscoveredTable], database: str) -> list[DiscoveredTable]:
    by_key = {t.key: t for t in live}
    resolved: dict[tuple[str, str], DiscoveredTable] = {}
    for ref in refs:
        key = (ref.schema_name, ref.table_name)
        table = by_key.get(key)
        if table is None:
            raise BadRequestError(f"La tabla {ref.schema_name}.{ref.table_name} no está disponible en la base {database}.")
        resolved[key] = table  # los duplicados del pedido se unifican
    return list(resolved.values())


def create_project(db: Session, data: ProjectCreate, actor: User) -> BuilderProject:
    host = ensure_host_allowed(data.host)
    _ensure_name_free(db, data.name)
    encrypted = encrypt_secret(data.password)  # falla antes de conectar si falta ENCRYPTION_KEY

    params = ConnectionParams(host, data.port, data.username, data.password, data.ssl_mode, data.database_name)
    live = _visible(get_connector(ENGINE).list_tables(params))  # valida conexión, base y permisos
    chosen = _resolve(data.tables, live, data.database_name)

    project = BuilderProject(
        name=data.name,
        engine=ENGINE,
        host=host,
        port=data.port,
        database_name=data.database_name,
        username=data.username,
        encrypted_password=encrypted,
        ssl_mode=data.ssl_mode,
        created_by=actor.id,
    )
    project.resources = [_new_resource(t) for t in chosen]
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project: BuilderProject, data: ProjectUpdate) -> BuilderProject:
    values = data.model_dump(exclude_unset=True)
    if "name" in values:
        _ensure_name_free(db, values["name"], exclude_id=project.id)
        project.name = values["name"]
    if "host" in values:
        project.host = ensure_host_allowed(values["host"])
    for field in ("port", "username", "ssl_mode"):
        if field in values:
            setattr(project, field, values[field])
    if values.get("password"):  # None o vacío = conservar la contraseña guardada
        project.encrypted_password = encrypt_secret(values["password"])
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: BuilderProject) -> None:
    db.delete(project)  # borra solo la configuración; la base de datos conectada no se toca
    db.commit()


def test_project(project: BuilderProject) -> ProbeResult:
    ensure_host_allowed(project.host)
    return get_connector(project.engine).probe(_params(project))


# ---------------------------------------------------------------- inventario
def get_resource(db: Session, project: BuilderProject, resource_id: int) -> BuilderResource:
    resource = db.get(BuilderResource, resource_id)
    if resource is None or resource.project_id != project.id:
        raise NotFoundError("Tabla no encontrada en el proyecto")
    return resource


def available_tables(project: BuilderProject) -> list[DiscoveredTable]:
    taken = {(r.schema_name, r.table_name) for r in project.resources}
    return [t for t in _live_tables(project) if t.key not in taken]


def add_resources(db: Session, project: BuilderProject, refs: list[TableRef]) -> list[BuilderResource]:
    chosen = _resolve(refs, _live_tables(project), project.database_name)
    taken = {(r.schema_name, r.table_name) for r in project.resources}
    added = [_new_resource(t) for t in chosen if t.key not in taken]  # lo que ya está, se ignora
    project.resources.extend(added)
    db.commit()
    for resource in added:
        db.refresh(resource)
    return added


def remove_resource(db: Session, project: BuilderProject, resource: BuilderResource) -> None:
    if resource.status != "NOT_GENERATED" or any(e.generated for e in resource.endpoints):
        raise ConflictError("La API de esta tabla ya fue generada: deshabilitala antes de quitarla del inventario.")
    project.resources.remove(resource)  # delete-orphan
    db.commit()


def set_endpoints(db: Session, resource: BuilderResource, data: EndpointsUpdate) -> BuilderResource:
    changes = {m: getattr(data, m) for m in data.model_fields_set}
    by_method = {e.method: e for e in resource.endpoints}
    for method, selected in changes.items():
        endpoint = by_method.get(method)
        if endpoint is None:
            raise BadRequestError(f"Endpoint desconocido: {method}")
        if endpoint.generated:
            raise ConflictError(f"El endpoint {method} ya fue generado y no se puede modificar desde acá.")
        if selected and method in NEEDS_PRIMARY_KEY and not resource.primary_key:
            raise BadRequestError(f"{method} requiere que la tabla tenga clave primaria.")
        endpoint.selected = selected
    db.commit()
    db.refresh(resource)
    return resource
