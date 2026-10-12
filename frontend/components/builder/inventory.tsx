"use client";

import { useState } from "react";
import { Pencil, Plus, RefreshCw, Trash2, TriangleAlert } from "lucide-react";
import { EndpointChip } from "@/components/builder/endpoint-chip";
import { ErrorState } from "@/components/feedback/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  METHODS,
  NEEDS_PRIMARY_KEY,
  STATUS_LABEL,
  connectionLabel,
  endpointVisual,
  filterTables,
  summarize,
  type HttpMethod,
  type Project,
  type Resource,
  type ResourceStatus,
} from "@/lib/builder";

export interface ConnectionStatus {
  state: "checking" | "ok" | "error";
  detail?: string;
}

interface InventoryProps {
  project: Project;
  resources: Resource[] | null;
  error: unknown;
  status: ConnectionStatus | undefined;
  /** Claves "idTabla:MÉTODO" con un cambio en curso. */
  busyKeys: ReadonlySet<string>;
  onToggle: (resource: Resource, method: HttpMethod) => void;
  onRemove: (resource: Resource) => void;
  onAddTables: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onRetest: () => void;
  onRetry: () => void;
}

const STATUS_VARIANT: Record<ResourceStatus, "outline" | "success" | "secondary" | "destructive"> = {
  NOT_GENERATED: "outline",
  PUBLISHED: "success",
  DISABLED: "secondary",
  ERROR: "destructive",
};

export function busyKey(resourceId: number, method: HttpMethod): string {
  return `${resourceId}:${method}`;
}

function ConnectionBadge({ status }: { status: ConnectionStatus | undefined }) {
  if (!status) return null;
  if (status.state === "checking") return <Badge variant="outline">Verificando conexión…</Badge>;
  if (status.state === "ok") return <Badge variant="success" title={status.detail}>Conectado</Badge>;
  return (
    <Badge variant="destructive" title={status.detail}>
      Sin conexión
    </Badge>
  );
}

export function Inventory(props: InventoryProps) {
  const { project, resources, error, status, busyKeys } = props;
  const [query, setQuery] = useState("");
  const visible = resources ? filterTables(resources, query) : [];
  const summary = resources ? summarize(resources) : null;

  return (
    <section className="min-w-0 space-y-4" aria-label={`Inventario de ${project.name}`}>
      <div className="flex flex-col gap-3 rounded-xl border bg-card p-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-lg font-semibold">{project.name}</h2>
            <ConnectionBadge status={status} />
          </div>
          <p className="text-sm text-muted-foreground">
            PostgreSQL · {connectionLabel(project)} · {project.database_name} · usuario {project.username}
          </p>
          {status?.state === "error" && status.detail && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <TriangleAlert className="size-4 shrink-0" aria-hidden />
              {status.detail}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={props.onRetest} disabled={status?.state === "checking"}>
            <RefreshCw className={status?.state === "checking" ? "animate-spin" : undefined} />
            Probar conexión
          </Button>
          <Button variant="outline" size="sm" onClick={props.onEdit}>
            <Pencil />
            Editar
          </Button>
          <Button variant="outline" size="sm" onClick={props.onDelete}>
            <Trash2 className="text-destructive" />
            Eliminar
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          {resources && resources.length > 8 && (
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar tabla…" aria-label="Buscar tabla" className="w-56" />
          )}
          {summary && (
            <p className="text-sm text-muted-foreground">
              {summary.total} {summary.total === 1 ? "tabla" : "tablas"} · {summary.published} publicadas · {summary.pending} sin generar
            </p>
          )}
        </div>
        <Button size="sm" onClick={props.onAddTables}>
          <Plus />
          Agregar tablas
        </Button>
      </div>

      {error && !resources ? (
        <ErrorState error={error} title="No se pudo cargar el inventario" onRetry={props.onRetry} />
      ) : resources === null ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-4">Tabla</TableHead>
                <TableHead>Estado API</TableHead>
                <TableHead>Endpoints</TableHead>
                <TableHead className="w-16 text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {resources.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={4} className="h-28 text-center text-muted-foreground">
                    El inventario está vacío. Usá “Agregar tablas” para elegir qué querés desarrollar.
                  </TableCell>
                </TableRow>
              ) : visible.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={4} className="h-20 text-center text-muted-foreground">
                    Ninguna tabla coincide con la búsqueda.
                  </TableCell>
                </TableRow>
              ) : (
                visible.map((resource) => (
                  <TableRow key={resource.id}>
                    <TableCell className="pl-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{resource.table_name}</span>
                        <span className="text-xs text-muted-foreground">{resource.schema_name}</span>
                        {resource.sensitive && (
                          <Badge variant="destructive" className="gap-1">
                            <TriangleAlert className="size-3" aria-hidden /> Sensible
                          </Badge>
                        )}
                        {!resource.has_primary_key && <Badge variant="outline">Sin clave primaria</Badge>}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[resource.status]}>{STATUS_LABEL[resource.status]}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1.5">
                        {METHODS.map((method) => {
                          const endpoint = resource.endpoints.find((e) => e.method === method);
                          if (!endpoint) return null;
                          const lacksPk = !resource.has_primary_key && NEEDS_PRIMARY_KEY.includes(method);
                          return (
                            <EndpointChip
                              key={method}
                              method={method}
                              visual={endpointVisual(endpoint)}
                              disabledReason={lacksPk ? "Requiere que la tabla tenga clave primaria" : undefined}
                              busy={busyKeys.has(busyKey(resource.id, method))}
                              onToggle={() => props.onToggle(resource, method)}
                            />
                          );
                        })}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" aria-label={`Quitar ${resource.table_name} del inventario`} onClick={() => props.onRemove(resource)}>
                        <Trash2 className="text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <EndpointChip method="GET" visual="pending" /> marcado: se generará
        </span>
        <span className="flex items-center gap-1.5">
          <EndpointChip method="GET" visual="off" /> sin marcar
        </span>
        <span className="flex items-center gap-1.5">
          <EndpointChip method="GET" visual="generated" /> ya generado
        </span>
        <span>Hacé clic en un endpoint para marcarlo o desmarcarlo. La generación llega en la próxima fase.</span>
      </div>
    </section>
  );
}
