"use client";

import { useEffect, useState } from "react";
import { ErrorState } from "@/components/feedback/error-state";
import { TablePicker } from "@/components/builder/table-picker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { builderApi, tableKey, type DiscoveredTable, type Project, type Resource } from "@/lib/builder";
import { notifyError, notifySuccess } from "@/lib/errors";

interface Props {
  project: Project;
  onClose: () => void;
  onAdded: (added: Resource[]) => void;
}

/** Muestra las tablas de la base que todavía no están en el inventario del proyecto. */
export function AddTablesDialog({ project, onClose, onAdded }: Props) {
  const [tables, setTables] = useState<DiscoveredTable[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setTables(null);
    setError(null);
    builderApi
      .availableTables(project.id)
      .then((list) => active && setTables(list))
      .catch((err) => active && setError(err));
    return () => {
      active = false;
    };
  }, [project.id, reloadKey]);

  async function handleAdd() {
    if (!tables) return;
    setBusy(true);
    try {
      const chosen = tables.filter((t) => selected.has(tableKey(t))).map((t) => ({ schema_name: t.schema_name, table_name: t.table_name }));
      const added = await builderApi.addResources(project.id, chosen);
      notifySuccess(added.length === 1 ? "Se agregó 1 tabla al inventario." : `Se agregaron ${added.length} tablas al inventario.`);
      onAdded(added);
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Agregar tablas</DialogTitle>
          <DialogDescription>Tablas de {project.database_name} que todavía no están en el inventario de {project.name}.</DialogDescription>
        </DialogHeader>

        {error ? (
          <ErrorState error={error} title="No se pudieron leer las tablas" onRetry={() => setReloadKey((k) => k + 1)} />
        ) : tables === null ? (
          <div className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <TablePicker
            tables={tables}
            selected={selected}
            onChange={(next) => setSelected(next)}
            disabled={busy}
            emptyMessage="Todas las tablas de la base ya están en el inventario."
          />
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Cancelar
          </Button>
          <Button type="button" loading={busy} disabled={selected.size === 0} onClick={() => void handleAdd()}>
            {selected.size > 0 ? `Agregar ${selected.size} ${selected.size === 1 ? "tabla" : "tablas"}` : "Agregar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
