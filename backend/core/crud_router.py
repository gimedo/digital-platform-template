"""Fábrica de routers CRUD: una entidad = una llamada, sin escribir endpoints a mano."""
from typing import Any, Callable, Generic, Sequence, TypeVar

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.config import settings
from core.crud import CRUDBase
from core.database import get_db

T = TypeVar("T")

ALL_OPERATIONS = frozenset({"list", "read", "create", "update", "delete"})
_RESERVED_QUERY_PARAMS = {"search", "limit", "offset", "order_by"}


class Page(BaseModel, Generic[T]):
    total: int
    limit: int
    offset: int
    items: list[T]


def _no_actor() -> None:
    return None


def build_crud_router(
    *,
    crud: CRUDBase,
    read_schema: type[BaseModel],
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    prefix: str,
    tags: Sequence[str] | None = None,
    operations: frozenset[str] | set[str] = ALL_OPERATIONS,
    read_dependency: Callable[..., Any] | None = None,
    write_dependency: Callable[..., Any] | None = None,
) -> APIRouter:
    """Genera GET (lista y detalle), POST, PATCH y DELETE para una entidad.

    - `operations`: qué endpoints existen. Un endpoint no incluido NO se registra
      (ej.: operations={"list","read","create","update"} => no hay DELETE).
    - `read_dependency` / `write_dependency`: dependencias de seguridad; su resultado
      se pasa como `actor` a los ganchos del CRUD.
    """
    router = APIRouter(prefix=prefix, tags=list(tags or []))
    read_dep = read_dependency or _no_actor
    write_dep = write_dependency or _no_actor

    filter_params = [
        {"name": name, "in": "query", "required": False, "schema": {"type": "string"},
         "description": f"Filtro por igualdad sobre '{name}'"}
        for name in crud.filterable
    ]

    if "list" in operations:

        @router.get(
            "",
            response_model=Page[read_schema],  # type: ignore[valid-type]
            summary=f"Listar {crud.label}",
            openapi_extra={"parameters": filter_params} if filter_params else None,
        )
        def list_items(
            request: Request,
            search: str | None = Query(None, max_length=100, description="Búsqueda de texto"),
            limit: int = Query(20, ge=1, description="Cantidad por página"),
            offset: int = Query(0, ge=0),
            order_by: str | None = Query(None, description="Ej.: -created_at,email"),
            db: Session = Depends(get_db),
            actor: Any = Depends(read_dep),
        ):
            limit = min(limit, settings.max_page_size)
            filters = {k: v for k, v in request.query_params.items() if k not in _RESERVED_QUERY_PARAMS}
            items, total = crud.get_multi(
                db, search=search, filters=filters, order_by=order_by, limit=limit, offset=offset
            )
            return {"total": total, "limit": limit, "offset": offset, "items": items}

    if "read" in operations:

        @router.get("/{item_id}", response_model=read_schema, summary=f"Obtener {crud.label}")
        def read_item(item_id: int, db: Session = Depends(get_db), actor: Any = Depends(read_dep)):
            return crud.get_or_404(db, item_id)

    if "create" in operations:

        @router.post("", response_model=read_schema, status_code=201, summary=f"Crear {crud.label}")
        def create_item(payload: create_schema, db: Session = Depends(get_db), actor: Any = Depends(write_dep)):  # type: ignore[valid-type]
            return crud.create(db, payload, actor=actor)

    if "update" in operations:

        @router.patch("/{item_id}", response_model=read_schema, summary=f"Modificar {crud.label}")
        def update_item(
            item_id: int,
            payload: update_schema,  # type: ignore[valid-type]
            db: Session = Depends(get_db),
            actor: Any = Depends(write_dep),
        ):
            obj = crud.get_or_404(db, item_id)
            return crud.update(db, obj, payload, actor=actor)

    if "delete" in operations:

        @router.delete("/{item_id}", status_code=204, summary=f"Eliminar {crud.label}")
        def delete_item(item_id: int, db: Session = Depends(get_db), actor: Any = Depends(write_dep)):
            obj = crud.get_or_404(db, item_id)
            crud.remove(db, obj, actor=actor)
            return Response(status_code=204)

    return router
