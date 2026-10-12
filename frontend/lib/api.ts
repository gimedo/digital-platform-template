import type { AuthResponse, FieldIssue } from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Errores por campo (422). */
  get fieldIssues(): FieldIssue[] {
    return Array.isArray(this.details) ? (this.details as FieldIssue[]) : [];
  }
}

// El access token vive solo en memoria (no en localStorage). Al recargar la página se
// recupera con la cookie httpOnly de refresco.
let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;
let refreshInFlight: Promise<AuthResponse | null> | null = null;

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler;
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const err = body?.error;
    if (err) return new ApiError(res.status, err.code ?? "error", err.message ?? res.statusText, err.details);
  } catch {
    /* cuerpo sin JSON */
  }
  return new ApiError(res.status, "http_error", `Error ${res.status}`);
}

async function doRefresh(): Promise<AuthResponse | null> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" });
    if (!res.ok) {
      accessToken = null;
      return null;
    }
    const data = (await res.json()) as AuthResponse;
    accessToken = data.access_token;
    return data;
  } catch {
    return null;
  }
}

/** Renueva la sesión. Las llamadas simultáneas comparten una única petición (evita rotar dos veces). */
export function refreshSession(): Promise<AuthResponse | null> {
  if (!refreshInFlight) {
    refreshInFlight = doRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

type QueryValue = string | number | boolean | null | undefined;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
  /** false = sin token ni reintento por 401 (login). */
  auth?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const { method = "GET", body, query, signal, auth = true } = options;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  const url = `${BASE}${path}${qs ? `?${qs}` : ""}`;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      credentials: "same-origin",
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "No se pudo conectar con el servidor.");
  }

  if (res.status === 401 && auth && !retried) {
    const renewed = await refreshSession();
    if (renewed) return request<T>(path, options, true);
    onSessionExpired?.();
  }

  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: Record<string, QueryValue>, signal?: AbortSignal) =>
    request<T>(path, { method: "GET", query, signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T = void>(path: string) => request<T>(path, { method: "DELETE" }),
};

export async function loginRequest(email: string, password: string): Promise<AuthResponse> {
  const data = await request<AuthResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
    auth: false,
  });
  accessToken = data.access_token;
  return data;
}

export async function logoutRequest(): Promise<void> {
  try {
    await request<void>("/auth/logout", { method: "POST", auth: false });
  } finally {
    accessToken = null;
  }
}
