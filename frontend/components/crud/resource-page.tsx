"use client";

import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { ErrorState } from "@/components/feedback/error-state";
import { ResourceForm, type FieldConfig, type FormValues } from "@/components/forms/resource-form";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DataTable, type Column } from "@/components/tables/data-table";
import { TableToolbar, type FilterConfig } from "@/components/tables/table-toolbar";
import { useResourceList } from "@/hooks/use-resource-list";
import { api, ApiError } from "@/lib/api";
import { notifyError, notifySuccess } from "@/lib/errors";

export interface ResourceConfig<T extends { id: number }> {
  title: string;
  description?: string;
  /** Endpoint del backend, ej.: "/users" (=> /api/users). */
  endpoint: string;
  /** Nombre en singular para botones y mensajes, ej.: "usuario". */
  singular: string;
  columns: Column<T>[];
  fields: FieldConfig[];
  filters?: FilterConfig[];
  searchPlaceholder?: string;
  defaultSort?: string;
  pageSize?: number;
  /** Qué acciones ofrece la pantalla (por defecto todas). Debe coincidir con los endpoints del backend. */
  operations?: { create?: boolean; update?: boolean; delete?: boolean };
  /** Convierte una fila en valores iniciales del formulario de edición. */
  toFormValues?: (row: T) => Partial<FormValues>;
  /** Texto que identifica a la fila en el diálogo de eliminación. */
  describeRow?: (row: T) => string;
}

/** Pantalla CRUD completa: buscador, filtros, tabla ordenable, paginación, alta, edición y baja. */
export function ResourcePage<T extends { id: number }>({ config }: { config: ResourceConfig<T> }) {
  const { operations = {}, singular } = config;
  const canCreate = operations.create !== false;
  const canUpdate = operations.update !== false;
  const canDelete = operations.delete !== false;

  const list = useResourceList<T>(config.endpoint, {
    pageSize: config.pageSize ?? 10,
    defaultSort: config.defaultSort ?? "-id",
  });

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<T | null>(null);
  const [deleting, setDeleting] = useState<T | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  const formOpen = creating || editing !== null;

  function closeForm() {
    setCreating(false);
    setEditing(null);
    setServerErrors({});
  }

  async function handleSubmit(payload: Record<string, unknown>) {
    setSubmitting(true);
    setServerErrors({});
    try {
      if (editing) {
        await api.patch(`${config.endpoint}/${editing.id}`, payload);
        notifySuccess(`Se guardaron los cambios del ${singular}.`);
      } else {
        await api.post(config.endpoint, payload);
        notifySuccess(`Se creó el ${singular}.`);
      }
      closeForm();
      list.reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && err.fieldIssues.length > 0) {
        const byField: Record<string, string> = {};
        for (const issue of err.fieldIssues) byField[issue.field] = issue.message;
        setServerErrors(byField); // se muestran junto a cada campo
      } else {
        notifyError(err);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    const target = deleting;
    try {
      await api.delete(`${config.endpoint}/${target.id}`);
      notifySuccess(`Se eliminó el ${singular}.`);
      setDeleting(null);
      // Si era el último de la página, volver a la anterior.
      if (list.data && list.data.items.length === 1 && list.page > 1) list.setPage(list.page - 1);
      else list.reload();
    } catch (err) {
      setDeleting(null);
      notifyError(err);
    }
  }

  const showActions = canUpdate || canDelete;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{config.title}</h1>
          {config.description && <p className="text-sm text-muted-foreground">{config.description}</p>}
        </div>
        {canCreate && (
          <Button onClick={() => setCreating(true)}>
            <Plus />
            Nuevo {singular}
          </Button>
        )}
      </div>

      <TableToolbar
        search={list.search}
        onSearchChange={list.changeSearch}
        searchPlaceholder={config.searchPlaceholder}
        filters={config.filters}
        filterValues={list.filters}
        onFilterChange={list.changeFilter}
        onClear={list.clearFilters}
      />

      {list.error && !list.data ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : (
        <>
          {list.error && <ErrorState error={list.error} title="No se pudo actualizar la lista" onRetry={list.reload} />}
          <DataTable<T>
            columns={config.columns}
            rows={list.data?.items ?? []}
            getRowId={(row) => row.id}
            loading={list.loading}
            sort={list.sort}
            onSortChange={list.changeSort}
            page={list.page}
            pageSize={list.pageSize}
            total={list.data?.total ?? 0}
            onPageChange={list.setPage}
            rowActions={
              showActions
                ? (row) => (
                    <>
                      {canUpdate && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Editar ${singular}`}
                          onClick={() => setEditing(row)}
                        >
                          <Pencil />
                        </Button>
                      )}
                      {canDelete && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Eliminar ${singular}`}
                          onClick={() => setDeleting(row)}
                        >
                          <Trash2 className="text-destructive" />
                        </Button>
                      )}
                    </>
                  )
                : undefined
            }
          />
        </>
      )}

      <Dialog open={formOpen} onOpenChange={(open) => !open && !submitting && closeForm()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? `Editar ${singular}` : `Nuevo ${singular}`}</DialogTitle>
            <DialogDescription>Los campos con * son obligatorios.</DialogDescription>
          </DialogHeader>
          {formOpen && (
            <ResourceForm
              key={editing ? `edit-${editing.id}` : "create"}
              fields={config.fields}
              mode={editing ? "edit" : "create"}
              initialValues={editing && config.toFormValues ? config.toFormValues(editing) : undefined}
              submitting={submitting}
              serverErrors={serverErrors}
              onSubmit={handleSubmit}
              onCancel={closeForm}
            />
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar {singular}?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleting && config.describeRow ? `Se eliminará "${config.describeRow(deleting)}". ` : ""}
              Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => void handleDelete()}>Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
