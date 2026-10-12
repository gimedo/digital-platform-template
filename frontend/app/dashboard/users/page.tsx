"use client";

// Esta página es "use client" porque su configuración contiene funciones (celdas de la tabla),
// que no pueden pasarse desde un componente de servidor.

import { ResourcePage, type ResourceConfig } from "@/components/crud/resource-page";
import { RoleGuard } from "@/components/layout/role-guard";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import type { User } from "@/lib/types";

const roleOptions = [
  { value: "user", label: "Usuario" },
  { value: "admin", label: "Administrador" },
];

// Ejemplo de cómo se declara un CRUD completo: columnas, campos del formulario y filtros.
const usersConfig: ResourceConfig<User> = {
  title: "Usuarios",
  description: "Administración de cuentas de acceso.",
  endpoint: "/users",
  singular: "usuario",
  searchPlaceholder: "Buscar por nombre o correo…",
  defaultSort: "-id",
  columns: [
    { key: "full_name", header: "Nombre", sortable: true, cell: (u) => <span className="font-medium">{u.full_name}</span> },
    { key: "email", header: "Correo", sortable: true, cell: (u) => u.email },
    {
      key: "role",
      header: "Rol",
      sortable: true,
      cell: (u) => (
        <Badge variant={u.role === "admin" ? "default" : "secondary"}>
          {u.role === "admin" ? "Administrador" : "Usuario"}
        </Badge>
      ),
    },
    {
      key: "is_active",
      header: "Estado",
      sortable: true,
      cell: (u) => <Badge variant={u.is_active ? "success" : "outline"}>{u.is_active ? "Activo" : "Inactivo"}</Badge>,
    },
    { key: "created_at", header: "Creado", sortable: true, cell: (u) => formatDate(u.created_at) },
  ],
  fields: [
    { name: "full_name", label: "Nombre completo", type: "text", required: true },
    { name: "email", label: "Correo", type: "email", required: true },
    {
      name: "password",
      label: "Contraseña",
      type: "password",
      required: "create",
      description: "Mínimo 12 caracteres. Al editar, dejala vacía para no cambiarla.",
    },
    { name: "role", label: "Rol", type: "select", required: true, options: roleOptions, defaultValue: "user" },
    { name: "is_active", label: "Usuario activo", type: "checkbox", defaultValue: true },
  ],
  filters: [
    { name: "role", label: "Rol", options: roleOptions },
    {
      name: "is_active",
      label: "Estado",
      options: [
        { value: "true", label: "Activos" },
        { value: "false", label: "Inactivos" },
      ],
    },
  ],
  toFormValues: (u) => ({ full_name: u.full_name, email: u.email, role: u.role, is_active: u.is_active, password: "" }),
  describeRow: (u) => u.email,
};

export default function UsersPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <ResourcePage config={usersConfig} />
    </RoleGuard>
  );
}
