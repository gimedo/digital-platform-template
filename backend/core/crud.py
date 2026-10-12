"""CRUD genérico reutilizable para cualquier entidad.

Uso típico:

    class ProductService(CRUDBase[Product, ProductCreate, ProductUpdate]):
        pass

    products = ProductService(
        Product,
        searchable=("name", "sku"),
        filterable=("category_id", "is_active"),
        sortable=("id", "name", "created_at"),
    )

Seguridad: solo se puede buscar, filtrar y ordenar por las columnas declaradas
explícitamente (lista blanca). Los valores siempre viajan parametrizados.
"""
from typing import Any, Generic, Sequence, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from core.database import Base
from core.errors import BadRequestError, NotFoundError

ModelT = TypeVar("ModelT", bound=Base)
CreateT = TypeVar("CreateT", bound=BaseModel)
UpdateT = TypeVar("UpdateT", bound=BaseModel)


class CRUDBase(Generic[ModelT, CreateT, UpdateT]):
    def __init__(
        self,
        model: type[ModelT],
        *,
        searchable: Sequence[str] = (),
        filterable: Sequence[str] = (),
        sortable: Sequence[str] = ("id",),
        default_sort: str = "-id",
        label: str = "Registro",
    ):
        self.model = model
        self.searchable = tuple(searchable)
        self.filterable = tuple(filterable)
        self.sortable = tuple(sortable)
        self.default_sort = default_sort
        self.label = label
        self._pk = model.__mapper__.primary_key[0]

    # ---------- Ganchos (se sobrescriben en cada entidad) ----------
    def before_create(self, db: Session, values: dict[str, Any], actor: Any) -> dict[str, Any]:
        return values

    def before_update(self, db: Session, obj: ModelT, values: dict[str, Any], actor: Any) -> dict[str, Any]:
        return values

    def before_delete(self, db: Session, obj: ModelT, actor: Any) -> None:
        return None

    # ---------- Lectura ----------
    def get(self, db: Session, obj_id: Any) -> ModelT | None:
        return db.get(self.model, obj_id)

    def get_or_404(self, db: Session, obj_id: Any) -> ModelT:
        obj = self.get(db, obj_id)
        if obj is None:
            raise NotFoundError(f"{self.label} no encontrado")
        return obj

    def get_multi(
        self,
        db: Session,
        *,
        search: str | None = None,
        filters: dict[str, str] | None = None,
        order_by: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ModelT], int]:
        stmt: Select = select(self.model)
        stmt = self._apply_filters(stmt, filters or {})
        stmt = self._apply_search(stmt, search)
        total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        stmt = self._apply_order(stmt, order_by)
        items = list(db.scalars(stmt.limit(limit).offset(offset)).all())
        return items, total

    # ---------- Escritura ----------
    def create(self, db: Session, data: CreateT | dict[str, Any], *, actor: Any = None) -> ModelT:
        values = data.model_dump() if isinstance(data, BaseModel) else dict(data)
        values = self.before_create(db, values, actor)
        obj = self.model(**values)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, obj: ModelT, data: UpdateT | dict[str, Any], *, actor: Any = None) -> ModelT:
        values = data.model_dump(exclude_unset=True) if isinstance(data, BaseModel) else dict(data)
        values = self.before_update(db, obj, values, actor)
        columns = set(self.model.__table__.columns.keys())
        for key, value in values.items():
            if key not in columns:
                raise BadRequestError(f"Campo no editable: {key}")
            setattr(obj, key, value)
        db.commit()
        db.refresh(obj)
        return obj

    def remove(self, db: Session, obj: ModelT, *, actor: Any = None) -> None:
        self.before_delete(db, obj, actor)
        db.delete(obj)
        db.commit()

    # ---------- Internos ----------
    def _column(self, name: str):
        return getattr(self.model, name)

    def _apply_search(self, stmt: Select, search: str | None) -> Select:
        term = (search or "").strip()
        if not term or not self.searchable:
            return stmt
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions = [self._column(c).ilike(f"%{escaped}%", escape="\\") for c in self.searchable]
        return stmt.where(or_(*conditions))

    def _apply_filters(self, stmt: Select, filters: dict[str, str]) -> Select:
        for name, raw in filters.items():
            if name not in self.filterable:
                raise BadRequestError(f"Filtro no permitido: {name}")
            col = self._column(name)
            stmt = stmt.where(col == self._coerce(name, col, raw))
        return stmt

    def _coerce(self, name: str, col: Any, raw: str) -> Any:
        try:
            py_type = col.type.python_type
        except NotImplementedError:
            py_type = str
        try:
            if py_type is bool:
                low = raw.strip().lower()
                if low in ("true", "1"):
                    return True
                if low in ("false", "0"):
                    return False
                raise ValueError
            if py_type is int:
                return int(raw)
            if py_type is float:
                return float(raw)
        except ValueError:
            raise BadRequestError(f"Valor inválido para el filtro '{name}'") from None
        return raw

    def _apply_order(self, stmt: Select, order_by: str | None) -> Select:
        tokens = [t.strip() for t in (order_by or self.default_sort).split(",") if t.strip()]
        clauses = []
        for token in tokens:
            descending = token.startswith("-")
            name = token.lstrip("+-")
            if name not in self.sortable:
                raise BadRequestError(f"Orden no permitido: {name}")
            col = self._column(name)
            clauses.append(col.desc() if descending else col.asc())
        clauses.append(self._pk.asc())  # desempate: paginación estable
        return stmt.order_by(*clauses)
