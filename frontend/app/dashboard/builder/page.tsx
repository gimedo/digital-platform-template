"use client";

import { useCallback, useEffect, useState } from "react";
import { Database, Plus } from "lucide-react";
import { AddTablesDialog } from "@/components/builder/add-tables-dialog";
import { EditProjectDialog } from "@/components/builder/edit-project-dialog";
import { Inventory, busyKey, type ConnectionStatus } from "@/components/builder/inventory";
import { NewProjectDialog } from "@/components/builder/new-project-dialog";
import { ProjectList } from "@/components/builder/project-list";
import { ErrorState } from "@/components/feedback/error-state";
import { RoleGuard } from "@/components/layout/role-guard";
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
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { builderApi, type HttpMethod, type Project, type Resource } from "@/lib/builder";
import { getErrorMessage, notifyError, notifySuccess } from "@/lib/errors";

type Dialog = "new" | "edit" | "add" | "delete" | null;

function BuilderScreen() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [resources, setResources] = useState<Resource[] | null>(null);
  const [resourcesError, setResourcesError] = useState<unknown>(null);
  const [statuses, setStatuses] = useState<Record<number, ConnectionStatus | undefined>>({});
  const [busyKeys, setBusyKeys] = useState<ReadonlySet<string>>(new Set());
  const [dialog, setDialog] = useState<Dialog>(null);
  const [removing, setRemoving] = useState<Resource | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const selected = projects?.find((p) => p.id === selectedId) ?? null;

  const loadProjects = useCallback(async (preferId?: number) => {
    try {
      const list = await builderApi.listProjects();
      setProjects(list);
      setLoadError(null);
      setSelectedId((current) =>
        preferId !== undefined ? preferId : current !== null && list.some((p) => p.id === current) ? current : (list[0]?.id ?? null),
      );
    } catch (err) {
      setLoadError(err);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const checkConnection = useCallback(async (id: number) => {
    setStatuses((s) => ({ ...s, [id]: { state: "checking" } }));
    try {
      const result = await builderApi.testProject(id);
      setStatuses((s) => ({ ...s, [id]: { state: "ok", detail: `PostgreSQL ${result.server_version}` } }));
    } catch (err) {
      setStatuses((s) => ({ ...s, [id]: { state: "error", detail: getErrorMessage(err) } }));
    }
  }, []);

  // Al elegir un proyecto: se carga su inventario y se verifica la conexión.
  useEffect(() => {
    if (selectedId === null) {
      setResources(null);
      return;
    }
    let active = true;
    setResources(null);
    setResourcesError(null);
    builderApi
      .listResources(selectedId)
      .then((list) => active && setResources(list))
      .catch((err) => active && setResourcesError(err));
    void checkConnection(selectedId);
    return () => {
      active = false;
    };
  }, [selectedId, reloadKey, checkConnection]);

  async function toggleEndpoint(resource: Resource, method: HttpMethod) {
    if (selectedId === null) return;
    const current = resource.endpoints.find((e) => e.method === method);
    if (!current || current.generated) return;
    const next = !current.selected;
    const key = busyKey(resource.id, method);
    const setSelectedFlag = (flag: boolean) =>
      setResources((list) =>
        list
          ? list.map((r) =>
              r.id === resource.id ? { ...r, endpoints: r.endpoints.map((e) => (e.method === method ? { ...e, selected: flag } : e)) } : r,
            )
          : list,
      );

    setSelectedFlag(next); // se refleja al instante y se revierte si el servidor lo rechaza
    setBusyKeys((keys) => new Set(keys).add(key));
    try {
      const changes: Partial<Record<HttpMethod, boolean>> = {};
      changes[method] = next;
      const updated = await builderApi.setEndpoints(selectedId, resource.id, changes);
      setResources((list) => (list ? list.map((r) => (r.id === updated.id ? updated : r)) : list));
    } catch (err) {
      setSelectedFlag(!next);
      notifyError(err);
    } finally {
      setBusyKeys((keys) => {
        const rest = new Set(keys);
        rest.delete(key);
        return rest;
      });
    }
  }

  async function confirmRemove() {
    if (!removing || selectedId === null) return;
    const target = removing;
    setRemoving(null);
    try {
      await builderApi.removeResource(selectedId, target.id);
      setResources((list) => (list ? list.filter((r) => r.id !== target.id) : list));
      notifySuccess(`Se quitó ${target.table_name} del inventario.`);
      void loadProjects();
    } catch (err) {
      notifyError(err);
    }
  }

  async function confirmDeleteProject() {
    if (!selected) return;
    setDeleting(true);
    try {
      await builderApi.deleteProject(selected.id);
      notifySuccess(`Se eliminó el proyecto "${selected.name}".`);
      setDialog(null);
      setSelectedId(null);
      await loadProjects();
    } catch (err) {
      notifyError(err);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">API Builder</h1>
          <p className="text-sm text-muted-foreground">Conectá una base de datos y armá el inventario de las APIs a desarrollar.</p>
        </div>
        <Button onClick={() => setDialog("new")}>
          <Plus />
          Nuevo proyecto
        </Button>
      </div>

      {loadError && !projects ? (
        <ErrorState error={loadError} title="No se pudieron cargar los proyectos" onRetry={() => void loadProjects()} />
      ) : projects === null ? (
        <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed p-12 text-center">
          <Database className="size-8 text-muted-foreground" aria-hidden />
          <p className="font-medium">Todavía no hay proyectos</p>
          <p className="max-w-md text-sm text-muted-foreground">
            Un proyecto es una conexión a una base de datos con su inventario de tablas. Creá el primero para empezar.
          </p>
          <Button onClick={() => setDialog("new")}>
            <Plus />
            Nuevo proyecto
          </Button>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <ProjectList projects={projects} selectedId={selectedId} statuses={statuses} onSelect={setSelectedId} onNew={() => setDialog("new")} />
          {selected && (
            <Inventory
              key={selected.id}
              project={selected}
              resources={resources}
              error={resourcesError}
              status={statuses[selected.id]}
              busyKeys={busyKeys}
              onToggle={(resource, method) => void toggleEndpoint(resource, method)}
              onRemove={setRemoving}
              onAddTables={() => setDialog("add")}
              onEdit={() => setDialog("edit")}
              onDelete={() => setDialog("delete")}
              onRetest={() => void checkConnection(selected.id)}
              onRetry={() => setReloadKey((k) => k + 1)}
            />
          )}
        </div>
      )}

      {dialog === "new" && (
        <NewProjectDialog
          onClose={() => setDialog(null)}
          onCreated={(project) => {
            setDialog(null);
            void loadProjects(project.id);
          }}
        />
      )}
      {dialog === "edit" && selected && (
        <EditProjectDialog
          project={selected}
          onClose={() => setDialog(null)}
          onSaved={(saved) => {
            setDialog(null);
            setProjects((list) => (list ? list.map((p) => (p.id === saved.id ? saved : p)) : list));
            void checkConnection(saved.id);
          }}
        />
      )}
      {dialog === "add" && selected && (
        <AddTablesDialog
          project={selected}
          onClose={() => setDialog(null)}
          onAdded={(added) => {
            setDialog(null);
            setResources((list) => (list ? [...list, ...added] : list));
            void loadProjects();
          }}
        />
      )}

      <AlertDialog open={dialog === "delete"} onOpenChange={(open) => !open && !deleting && setDialog(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar el proyecto “{selected?.name}”?</AlertDialogTitle>
            <AlertDialogDescription>
              Se elimina la conexión guardada y el inventario de este proyecto. No se modifica ni se borra nada en la base de datos conectada.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              onClick={(e) => {
                e.preventDefault();
                void confirmDeleteProject();
              }}
            >
              Eliminar proyecto
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Quitar {removing?.table_name} del inventario?</AlertDialogTitle>
            <AlertDialogDescription>
              Se pierde la selección de endpoints de esta tabla. La tabla en sí no se toca y la podés volver a agregar cuando quieras.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => void confirmRemove()}>Quitar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function BuilderPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <BuilderScreen />
    </RoleGuard>
  );
}
