# Digital Platform — Template base

Plantilla para arrancar cualquier proyecto interno con lo común ya resuelto: **login con JWT, CRUD genérico,
tabla con filtros, formulario base, layout (sidebar + navbar) y manejo de errores**.

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12+ · FastAPI · SQLAlchemy 2 · PostgreSQL |
| Frontend | Next.js 16 (App Router) · TypeScript · Tailwind CSS 4 · shadcn/ui |
| Base de datos | Migraciones SQL numeradas + ejecutor propio (`database/migrate.py`) |

## Estructura

```
digital-platform-template/
├── backend/
│   ├── main.py            ← arranque de FastAPI y registro de routers
│   ├── core/              ← config, db, seguridad, errores, CRUD genérico
│   ├── auth/              ← login / refresh / logout / usuario actual (JWT)
│   ├── users/             ← CRUD de usuarios (ejemplo de entidad sobre el CRUD genérico)
│   ├── scripts/           ← create_admin
│   └── tests/
├── frontend/
│   ├── app/               ← login/ y dashboard/ (rutas)
│   ├── components/
│   │   ├── ui/            ← shadcn (botones, inputs, tabla, diálogos…)
│   │   ├── layout/        ← sidebar, navbar, footer, guards
│   │   ├── forms/         ← FormField y ResourceForm reutilizables
│   │   ├── tables/        ← DataTable + TableToolbar (filtros)
│   │   ├── crud/          ← ResourcePage (pantalla CRUD completa)
│   │   └── feedback/      ← errores y spinners
│   ├── config/            ← branding.ts y navigation.ts (lo que se cambia por proyecto)
│   ├── hooks/  lib/       ← cliente API, auth, utilidades
└── database/
    ├── migrate.py
    └── migrations/        ← 001_init.sql
```

## Qué incluye

| Módulo | Dónde está |
|---|---|
| Auth JWT (login/logout) | `backend/auth/` · `frontend/lib/auth.tsx`, `lib/api.ts`, `app/login/` |
| CRUD genérico | `backend/core/crud.py` + `crud_router.py` · `frontend/components/crud/resource-page.tsx` |
| Tabla con filtros | `frontend/components/tables/` · `hooks/use-resource-list.ts` |
| Formulario base (alta/edición) | `frontend/components/forms/` |
| Sidebar + Navbar | `frontend/components/layout/` |
| Manejo de errores | `backend/core/errors.py` · `frontend/lib/errors.ts`, toasts (sonner), `error.tsx`, `error-state.tsx` |

## Puesta en marcha (PowerShell)

### 1. Base de datos
Crear una base vacía (por ejemplo `digital_platform`) en PostgreSQL y luego:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # completar DATABASE_URL y JWT_SECRET

cd ..
python database/migrate.py    # aplica las migraciones pendientes (usa backend/.env)
```

Generar el secreto JWT: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

### 2. Backend
```powershell
cd backend
python -m scripts.create_admin                 # crea el primer administrador
uvicorn main:app --reload --port 8000
```
Verificar: <http://127.0.0.1:8000/api/health> y la documentación en <http://127.0.0.1:8000/api/docs>.

### 3. Frontend (otra terminal)
```powershell
cd frontend
npm install
copy .env.example .env.local    # BACKEND_URL=http://127.0.0.1:8000
npm run dev
```
Abrir <http://localhost:3000> e ingresar con el administrador creado.

> Next.js reenvía `/api/*` al backend (ver `next.config.ts`). El navegador solo habla con un origen, así la
> cookie de sesión es de primera parte y **no hace falta configurar CORS**.

## Cómo agregar una entidad nueva

**Backend** — modelo, esquemas y una llamada al router genérico:

```python
# backend/products/service.py
products = CRUDBase(
    Product,
    searchable=("name", "sku"),               # búsqueda de texto
    filterable=("is_active", "category"),     # filtros por igualdad (?is_active=true)
    sortable=("id", "name", "created_at"),    # ?order_by=-created_at
    label="Producto",
)

# backend/products/router.py
router = build_crud_router(
    crud=products, read_schema=ProductRead, create_schema=ProductCreate, update_schema=ProductUpdate,
    prefix="/products", tags=["products"],
    read_dependency=get_current_user, write_dependency=require_admin,
    operations={"list", "read", "create", "update"},   # sin "delete" => el endpoint DELETE no existe
)
```
Luego: crear su migración en `database/migrations/002_products.sql`, importar el modelo y hacer
`api.include_router(products_router)` en `backend/main.py`.
Las reglas de negocio se agregan sobrescribiendo `before_create`, `before_update` y `before_delete`
(ver `users/service.py`).

**Frontend** — una configuración declarativa (columnas, campos, filtros), sin escribir la pantalla:

```tsx
// app/dashboard/products/page.tsx  ("use client")
<ResourcePage config={productsConfig} />
```
y un ítem en `config/navigation.ts`. Ejemplo completo: `app/dashboard/users/page.tsx`.

## Decisiones de seguridad

- **Contraseñas** con Argon2id. Mensaje de error de login idéntico para usuario inexistente, clave incorrecta e inactivo, y tiempo de respuesta igualado.
- **Access token** JWT de 15 minutos, **solo en memoria** del navegador (no `localStorage`).
- **Refresh token** opaco en cookie `httpOnly`, `SameSite=Lax`, limitada a `/api/auth`; en la base se guarda solo su hash SHA-256.
  Se **rota en cada uso**; reutilizar un token ya rotado cierra todas las sesiones del usuario.
- **Logout real**: revoca el refresh token en el servidor. Cambiar la contraseña o desactivar un usuario cierra sus sesiones.
- **Límite de intentos** de login (5 en 5 minutos por IP + correo) con `429` y `Retry-After`.
- **CRUD genérico**: solo se puede buscar, filtrar y ordenar por columnas declaradas (lista blanca); valores siempre parametrizados; el `PATCH`/`POST` rechaza campos desconocidos.
- Respuestas de error uniformes `{"error": {"code", "message", "details"}}`; los `422` nunca devuelven el valor enviado; los `500` no filtran detalles.
- Se impide eliminarse o desactivarse a uno mismo y dejar el sistema sin administrador activo.
- En `ENVIRONMENT=production` se exige `COOKIE_SECURE=true` y se desactiva la documentación `/api/docs`.

## Pruebas

```powershell
cd backend
pip install -r requirements-dev.txt
pytest                                   # SQLite en memoria (rápido)

$env:TEST_DATABASE_URL = "postgresql+psycopg://usuario:clave@localhost:5432/digital_platform_test"
pytest                                   # contra PostgreSQL real (con las migraciones ya aplicadas)
```

## Alcance y límites conocidos

- Autorización simple por rol (`admin` / `user`). **No incluye** matriz de permisos `recurso.accion` ni gestión de roles; es el siguiente paso natural sobre `auth/deps.py` (`require_roles`).
- El límite de intentos de login es **en memoria** (un solo proceso). Con varios workers/servidores conviene Redis o un límite en NGINX.
- Detrás de un proxy, ejecutar uvicorn con `--proxy-headers` y `--forwarded-allow-ips` del proxy para que se vea la IP real del cliente.
- Para mantener el estado de la base entre equipos se usan migraciones SQL; no hay Alembic ni autogeneración.
- Las páginas con configuración que contiene funciones (como `users/page.tsx`) son componentes de cliente (`"use client"`).

## Publicarlo como template en Git

```powershell
git init -b main
git add .
git commit -m "feat: template base (FastAPI + Next.js + shadcn/ui)"
git remote add origin https://github.com/<usuario>/digital-platform-template.git
git push -u origin main
```
En GitHub: *Settings → General → Template repository* y luego **Use this template** para cada proyecto nuevo.
Las mejoras al template se traen a los proyectos con `git merge` desde el repositorio plantilla.
