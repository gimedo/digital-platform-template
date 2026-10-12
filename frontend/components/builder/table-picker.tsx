"use client";

import { useMemo, useState } from "react";
import { Search, TriangleAlert } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { filterTables, groupBySchema, tableKey, type DiscoveredTable } from "@/lib/builder";

interface TablePickerProps {
  tables: DiscoveredTable[];
  /** Claves (ver tableKey) de las tablas marcadas. */
  selected: ReadonlySet<string>;
  onChange: (next: Set<string>) => void;
  disabled?: boolean;
  emptyMessage?: string;
}

/** Lista de tablas agrupadas por esquema, con búsqueda y selección múltiple. */
export function TablePicker({ tables, selected, onChange, disabled, emptyMessage = "No hay tablas para mostrar." }: TablePickerProps) {
  const [query, setQuery] = useState("");
  const groups = useMemo(() => groupBySchema(filterTables(tables, query)), [tables, query]);
  const sensitiveChosen = tables.some((t) => t.sensitive && selected.has(tableKey(t)));

  function toggle(table: DiscoveredTable) {
    const next = new Set(selected);
    const key = tableKey(table);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  function setGroup(list: DiscoveredTable[], on: boolean) {
    const next = new Set(selected);
    for (const t of list) {
      if (on) next.add(tableKey(t));
      else next.delete(tableKey(t));
    }
    onChange(next);
  }

  if (tables.length === 0) {
    return <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar tabla…" className="pl-8" aria-label="Buscar tabla" />
        </div>
        <span className="text-sm whitespace-nowrap text-muted-foreground" aria-live="polite">
          {selected.size} de {tables.length} seleccionadas
        </span>
      </div>

      <div className="max-h-72 overflow-y-auto rounded-lg border">
        {groups.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Ninguna tabla coincide con la búsqueda.</p>
        ) : (
          groups.map((group) => {
            const allOn = group.tables.every((t) => selected.has(tableKey(t)));
            return (
              <div key={group.schema} className="border-b last:border-b-0">
                <div className="sticky top-0 flex items-center justify-between bg-muted/70 px-3 py-1.5 backdrop-blur">
                  <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    {group.schema} · {group.tables.length}
                  </span>
                  <Button type="button" variant="ghost" size="sm" className="h-6 px-2 text-xs" disabled={disabled} onClick={() => setGroup(group.tables, !allOn)}>
                    {allOn ? "Ninguna" : "Todas"}
                  </Button>
                </div>
                {group.tables.map((table) => {
                  return (
                    <label key={tableKey(table)} className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm hover:bg-muted/50">
                      <input
                        type="checkbox"
                        className="size-4 rounded border-input accent-primary"
                        checked={selected.has(tableKey(table))}
                        disabled={disabled}
                        onChange={() => toggle(table)}
                      />
                      <span className="font-medium">{table.table_name}</span>
                      {table.sensitive && (
                        <Badge variant="destructive" className="gap-1">
                          <TriangleAlert className="size-3" aria-hidden /> Sensible
                        </Badge>
                      )}
                      {!table.has_primary_key && <Badge variant="outline">Sin clave primaria</Badge>}
                    </label>
                  );
                })}
              </div>
            );
          })
        )}
      </div>

      {sensitiveChosen && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertDescription>
            Marcaste tablas sensibles (usuarios, credenciales o sesiones). Se agregan al inventario, pero no deberían publicarse
            como API sin una confirmación explícita.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
