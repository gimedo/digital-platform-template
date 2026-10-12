import { api, ApiError } from "./api";

// ---------------------------------------------------------------- tipos (reflejan builder/schemas.py)
export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";
export type SslMode = "disable" | "prefer" | "require";
export type ResourceStatus = "NOT_GENERATED" | "PUBLISHED" | "DISABLED" | "ERROR";

export const METHODS: readonly HttpMethod[] = ["GET", "POST", "PUT", "DELETE"];
/** Operan sobre un registro puntual: la tabla necesita clave primaria. */
export const NEEDS_PRIMARY_KEY: readonly HttpMethod[] = ["PUT", "DELETE"];

export interface ConnectionInput {
  host: string;
  port: number;
  username: string;
  password: string;
  ssl_mode: SslMode;
  database?: string | null;
}

export interface TableRef {
  schema_name: string;
  table_name: string;
}

export interface DiscoveredTable extends TableRef {
  primary_key: string[];
  has_primary_key: boolean;
  sensitive: boolean;
}

export interface EndpointState {
  method: HttpMethod;
  selected: boolean;
  generated: boolean;
}

export interface Resource extends TableRef {
  id: number;
  primary_key: string[];
  has_primary_key: boolean;
  sensitive: boolean;
  status: ResourceStatus;
  endpoints: EndpointState[];
}

export interface Project {
  id: number;
  name: string;
  engine: string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  ssl_mode: SslMode;
  tables_total: number;
  generated_total: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  host: string;
  port: number;
  username: string;
  password: string;
  ssl_mode: SslMode;
  database_name: string;
  tables: TableRef[];
}

/** La base de datos no se cambia; la contraseña vacía o ausente conserva la guardada. */
export interface ProjectUpdate {
  name?: string;
  host?: string;
  port?: number;
  username?: string;
  password?: string;
  ssl_mode?: SslMode;
}

export interface ProbeResult {
  server_version: string;
  databases: string[];
}

// ---------------------------------------------------------------- llamadas a la API
export const builderApi = {
  testConnection: (connection: ConnectionInput) => api.post<ProbeResult>("/builder/connections/test", connection),

  discoverTables: (connection: ConnectionInput & { database: string }) =>
    api.post<{ tables: DiscoveredTable[] }>("/builder/connections/tables", connection).then((r) => r.tables),

  listProjects: () => api.get<Project[]>("/builder/projects"),
  createProject: (data: ProjectCreate) => api.post<Project>("/builder/projects", data),
  updateProject: (id: number, data: ProjectUpdate) => api.patch<Project>(`/builder/projects/${id}`, data),
  deleteProject: (id: number) => api.delete(`/builder/projects/${id}`),
  testProject: (id: number) => api.post<{ server_version: string }>(`/builder/projects/${id}/test`),

  listResources: (projectId: number) => api.get<Resource[]>(`/builder/projects/${projectId}/resources`),
  availableTables: (projectId: number) =>
    api.get<{ tables: DiscoveredTable[] }>(`/builder/projects/${projectId}/available-tables`).then((r) => r.tables),
  addResources: (projectId: number, tables: TableRef[]) =>
    api.post<Resource[]>(`/builder/projects/${projectId}/resources`, { tables }),
  removeResource: (projectId: number, resourceId: number) =>
    api.delete(`/builder/projects/${projectId}/resources/${resourceId}`),
  setEndpoints: (projectId: number, resourceId: number, changes: Partial<Record<HttpMethod, boolean>>) =>
    api.patch<Resource>(`/builder/projects/${projectId}/resources/${resourceId}/endpoints`, changes),
};

// ---------------------------------------------------------------- utilidades puras
/** Clave única e inequívoca de una tabla (los nombres pueden contener puntos o espacios). */
export function tableKey(t: TableRef): string {
  return JSON.stringify([t.schema_name, t.table_name]);
}

export function qualifiedName(t: TableRef): string {
  return `${t.schema_name}.${t.table_name}`;
}

export function filterTables<T extends TableRef>(tables: readonly T[], query: string): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return [...tables];
  return tables.filter((t) => qualifiedName(t).toLowerCase().includes(q));
}

export function groupBySchema<T extends TableRef>(tables: readonly T[]): { schema: string; tables: T[] }[] {
  const groups = new Map<string, T[]>();
  for (const t of tables) {
    const list = groups.get(t.schema_name);
    if (list) list.push(t);
    else groups.set(t.schema_name, [t]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([schema, list]) => ({ schema, tables: list.sort((a, b) => a.table_name.localeCompare(b.table_name)) }));
}

/** off = sin marcar (gris) · pending = marcado, se generará (color claro) · generated = ya generado (color pleno). */
export type EndpointVisual = "off" | "pending" | "generated";

export function endpointVisual(state: { selected: boolean; generated: boolean }): EndpointVisual {
  if (state.generated) return "generated";
  return state.selected ? "pending" : "off";
}

export const STATUS_LABEL: Record<ResourceStatus, string> = {
  NOT_GENERATED: "Sin generar",
  PUBLISHED: "Publicada",
  DISABLED: "Deshabilitada",
  ERROR: "Con error",
};

export function summarize(resources: readonly Resource[]) {
  const published = resources.filter((r) => r.status === "PUBLISHED").length;
  return { total: resources.length, published, pending: resources.length - published };
}

/** Si el error vino del conector, indica de qué tipo fue (auth, network, database, ssl, other). */
export function databaseErrorKind(err: unknown): string | undefined {
  if (err instanceof ApiError && err.code === "database_unreachable" && typeof err.details === "object" && err.details !== null) {
    const kind = (err.details as { kind?: unknown }).kind;
    return typeof kind === "string" ? kind : undefined;
  }
  return undefined;
}

export function connectionLabel(p: { host: string; port: number }): string {
  return `${p.host}:${p.port}`;
}
