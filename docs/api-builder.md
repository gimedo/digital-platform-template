# API Builder — Fase 1

Un **proyecto** es una conexión a una base de datos más su **inventario de tablas**. Para cada tabla se elige
qué endpoints (GET, POST, PUT, DELETE) se van a desarrollar. En esta fase se arma y guarda el inventario;
la generación de las APIs llega en la fase 2.

## Puesta en marcha

1. En `backend/.env` agregar `ENCRYPTION_KEY` (mínimo 32 caracteres; generar con
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
2. `pip install -r requirements.txt` (suma `cryptography`).
3. `python database/migrate.py` (aplica `002_builder.sql`).
4. Reiniciar el backend. En el menú aparece **API Builder** (solo administradores).

## Cómo se usa

- **Nuevo proyecto**: nombre + datos del servidor → *Probar conexión* → elegir base → elegir tablas.
- Al elegir un proyecto se ve su inventario y se verifica la conexión.
- Cada endpoint es una casilla: **gris** = sin marcar, **color claro** = marcado (se generará),
  **color pleno** = ya generado (fase 2).
- **Agregar tablas** muestra las tablas de la base que todavía no están en el inventario.
- Eliminar un proyecto borra solo su configuración; la base conectada no se toca.

## Reglas

- Por defecto cada tabla se agrega con los 4 endpoints marcados. Sin clave primaria no se ofrecen PUT ni DELETE.
- Las tablas con nombres como `users`, `usuarios`, `password`, `token`, `credenciales`, `sesiones` se marcan
  **Sensibles**. Se pueden agregar al inventario, pero la fase 2 no las publicará sin confirmación explícita.
- Las tablas de la propia plataforma (`builder_*`, `schema_migrations`) nunca se listan.
- Solo tablas (no vistas) de PostgreSQL. La interfaz de conectores (`builder/connectors/base.py`) permite sumar otros motores.

## Seguridad

- Todos los endpoints `/api/builder/*` exigen rol administrador.
- La contraseña de cada conexión se guarda **cifrada** (Fernet, clave derivada de `ENCRYPTION_KEY`) y nunca
  se devuelve por la API ni aparece en mensajes de error.
- El servidor debe ser un nombre de host o una IP; se rechazan rutas, listas y caracteres especiales.
  `BUILDER_ALLOWED_HOSTS` permite limitar a qué servidores puede conectarse el Builder.
- Cada conexión a la base de destino es de **solo lectura** (`default_transaction_read_only = on`), con tiempo
  máximo de consulta y de conexión, y se cierra al terminar (sin pool).
- La introspección usa el inspector de SQLAlchemy: ninguna consulta se arma concatenando texto del usuario.

## Pruebas

```powershell
cd backend
pytest                                     # SQLite en memoria; no toca tu base
```

Para probar también el conector contra un PostgreSQL real (con las migraciones aplicadas):

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://usuario:clave@servidor:5432/digital_platform_test"
pytest
```

> **Importante:** `TEST_DATABASE_URL` debe apuntar a una base **exclusiva para pruebas**. Cada prueba vacía las
> tablas `users`, `refresh_tokens` y `builder_*` de esa base, y las del conector crean y borran esquemas `bld_test_*`.
