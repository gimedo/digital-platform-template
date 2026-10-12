"""Demuestra cómo se agrega una entidad nueva con CRUDBase + build_crud_router."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.crud import CRUDBase
from core.crud_router import build_crud_router
from core.database import Base, engine
from core.errors import register_exception_handlers


class Item(Base):
    __tablename__ = "test_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(30))
    qty: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)
    category: str
    qty: int = 0
    active: bool = True


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    qty: int | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    qty: int
    active: bool


@pytest.fixture
def items_client():
    Item.__table__.create(engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(Item.__table__.delete())
    crud = CRUDBase[Item, ItemCreate, ItemUpdate](
        Item,
        searchable=("name",),
        filterable=("category", "qty", "active"),
        sortable=("id", "name", "qty"),
        label="Ítem",
    )
    app = FastAPI()
    register_exception_handlers(app)
    # Sin DELETE: "CRUD sin eliminar"
    app.include_router(
        build_crud_router(
            crud=crud, read_schema=ItemRead, create_schema=ItemCreate, update_schema=ItemUpdate,
            prefix="/items", operations={"list", "read", "create", "update"},
        )
    )
    yield TestClient(app)
    Item.__table__.drop(engine, checkfirst=True)


def test_crud_generico_sin_delete(items_client):
    c = items_client
    for n, cat, q in [("Tornillo", "ferreteria", 10), ("Tuerca", "ferreteria", 5), ("Lapiz", "libreria", 7)]:
        assert c.post("/items", json={"name": n, "category": cat, "qty": q}).status_code == 201

    page = c.get("/items?category=ferreteria&order_by=-qty").json()
    assert page["total"] == 2 and [i["name"] for i in page["items"]] == ["Tornillo", "Tuerca"]
    assert c.get("/items?qty=7").json()["items"][0]["name"] == "Lapiz"      # coerción a int
    assert c.get("/items?search=tu").json()["total"] == 1                   # solo "Tuerca"
    assert c.get("/items?qty=abc").status_code == 400
    assert c.get("/items?color=rojo").status_code == 400

    item = c.get("/items").json()["items"][0]
    assert c.patch(f"/items/{item['id']}", json={"qty": 99}).json()["qty"] == 99
    assert c.post("/items", json={"name": "X", "category": "y", "campo_extra": 1}).status_code == 422

    # el endpoint DELETE no existe
    assert c.delete(f"/items/{item['id']}").status_code == 405


def test_openapi_documenta_los_filtros_y_omite_delete(items_client):
    spec = items_client.get("/openapi.json").json()
    params = {p["name"] for p in spec["paths"]["/items"]["get"]["parameters"]}
    assert {"category", "qty", "active", "search", "limit", "offset", "order_by"} <= params
    assert "delete" not in spec["paths"]["/items/{item_id}"]
