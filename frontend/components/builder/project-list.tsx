"use client";

import { Database, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { connectionLabel, type Project } from "@/lib/builder";
import { cn } from "@/lib/utils";
import type { ConnectionStatus } from "./inventory";

interface ProjectListProps {
  projects: Project[];
  selectedId: number | null;
  statuses: Record<number, ConnectionStatus | undefined>;
  onSelect: (id: number) => void;
  onNew: () => void;
}

const DOT: Record<ConnectionStatus["state"] | "unknown", string> = {
  ok: "bg-emerald-500",
  error: "bg-red-500",
  checking: "animate-pulse bg-amber-400",
  unknown: "bg-muted-foreground/30",
};

const DOT_LABEL: Record<ConnectionStatus["state"] | "unknown", string> = {
  ok: "Conectado",
  error: "Sin conexión",
  checking: "Verificando",
  unknown: "Sin verificar",
};

export function ProjectList({ projects, selectedId, statuses, onSelect, onNew }: ProjectListProps) {
  return (
    <aside className="space-y-3" aria-label="Conexiones disponibles">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Conexiones disponibles</h2>
        <Button variant="ghost" size="icon" className="size-7" onClick={onNew} aria-label="Nuevo proyecto">
          <Plus />
        </Button>
      </div>
      <ul className="space-y-1.5">
        {projects.map((project) => {
          const active = project.id === selectedId;
          const state = statuses[project.id]?.state ?? "unknown";
          return (
            <li key={project.id}>
              <button
                type="button"
                onClick={() => onSelect(project.id)}
                aria-current={active ? "true" : undefined}
                className={cn(
                  "flex w-full cursor-pointer items-start gap-3 rounded-lg border p-3 text-left transition-colors",
                  active ? "border-primary/40 bg-sidebar-accent" : "bg-card hover:bg-muted/60",
                )}
              >
                <Database className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold">{project.name}</span>
                    <span className={cn("size-2 shrink-0 rounded-full", DOT[state])} title={DOT_LABEL[state]} role="img" aria-label={DOT_LABEL[state]} />
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {connectionLabel(project)} · {project.database_name}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {project.tables_total} {project.tables_total === 1 ? "tabla" : "tablas"}
                    {project.generated_total > 0 && ` · ${project.generated_total} publicadas`}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
