from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from auth.deps import require_admin
from builder import service
from builder.schemas import (ConnectionInput, DiscoverRequest, EndpointsUpdate, ProbeResponse, ProjectCreate,
                             ProjectRead, ProjectTestResponse, ProjectUpdate, ResourceRead, ResourcesAdd,
                             TablesResponse)
from core.database import get_db
from users.models import User

# Todo el Builder es solo para administradores: puede abrir conexiones hacia otros servidores.
router = APIRouter(prefix="/builder", tags=["builder"], dependencies=[Depends(require_admin)])


# ----- asistente "Nuevo proyecto": la contraseña viaja en el cuerpo (POST), nunca en la URL
@router.post("/connections/test", response_model=ProbeResponse, summary="Probar conexión y listar bases")
def test_connection(payload: ConnectionInput):
    result = service.probe_connection(payload)
    return ProbeResponse(server_version=result.server_version, databases=result.databases)


@router.post("/connections/tables", response_model=TablesResponse, summary="Listar tablas de una base")
def list_connection_tables(payload: DiscoverRequest):
    return TablesResponse(tables=[service.table_read(t) for t in service.discover_tables(payload)])


# ----- proyectos
@router.get("/projects", response_model=list[ProjectRead], summary="Listar proyectos")
def list_projects(db: Session = Depends(get_db)):
    return [service.project_read(p) for p in service.list_projects(db)]


@router.post("/projects", response_model=ProjectRead, status_code=201, summary="Crear proyecto")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    return service.project_read(service.create_project(db, payload, actor))


@router.get("/projects/{project_id}", response_model=ProjectRead, summary="Obtener proyecto")
def get_project(project_id: int, db: Session = Depends(get_db)):
    return service.project_read(service.get_project(db, project_id))


@router.patch("/projects/{project_id}", response_model=ProjectRead, summary="Editar la conexión del proyecto")
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = service.get_project(db, project_id)
    return service.project_read(service.update_project(db, project, payload))


@router.delete("/projects/{project_id}", status_code=204, summary="Eliminar proyecto (solo su configuración)")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    service.delete_project(db, service.get_project(db, project_id))
    return Response(status_code=204)


@router.post("/projects/{project_id}/test", response_model=ProjectTestResponse, summary="Probar la conexión guardada")
def test_project(project_id: int, db: Session = Depends(get_db)):
    result = service.test_project(service.get_project(db, project_id))
    return ProjectTestResponse(server_version=result.server_version)


# ----- inventario
@router.get("/projects/{project_id}/resources", response_model=list[ResourceRead], summary="Inventario de tablas")
def list_resources(project_id: int, db: Session = Depends(get_db)):
    return [service.resource_read(r) for r in service.get_project(db, project_id).resources]


@router.get("/projects/{project_id}/available-tables", response_model=TablesResponse,
            summary="Tablas de la base que aún no están en el inventario")
def available_tables(project_id: int, db: Session = Depends(get_db)):
    project = service.get_project(db, project_id)
    return TablesResponse(tables=[service.table_read(t) for t in service.available_tables(project)])


@router.post("/projects/{project_id}/resources", response_model=list[ResourceRead], status_code=201,
             summary="Agregar tablas al inventario")
def add_resources(project_id: int, payload: ResourcesAdd, db: Session = Depends(get_db)):
    project = service.get_project(db, project_id)
    return [service.resource_read(r) for r in service.add_resources(db, project, payload.tables)]


@router.delete("/projects/{project_id}/resources/{resource_id}", status_code=204, summary="Quitar tabla del inventario")
def remove_resource(project_id: int, resource_id: int, db: Session = Depends(get_db)):
    project = service.get_project(db, project_id)
    service.remove_resource(db, project, service.get_resource(db, project, resource_id))
    return Response(status_code=204)


@router.patch("/projects/{project_id}/resources/{resource_id}/endpoints", response_model=ResourceRead,
              summary="Elegir los endpoints de una tabla")
def update_endpoints(project_id: int, resource_id: int, payload: EndpointsUpdate, db: Session = Depends(get_db)):
    project = service.get_project(db, project_id)
    resource = service.get_resource(db, project, resource_id)
    return service.resource_read(service.set_endpoints(db, resource, payload))
