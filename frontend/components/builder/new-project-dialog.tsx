"use client";

import { useState } from "react";
import { ChevronLeft, CircleAlert } from "lucide-react";
import { FormField } from "@/components/forms/form-field";
import { TablePicker } from "@/components/builder/table-picker";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  builderApi,
  databaseErrorKind,
  tableKey,
  type ConnectionInput,
  type DiscoveredTable,
  type Project,
  type SslMode,
} from "@/lib/builder";
import { getErrorMessage, notifySuccess } from "@/lib/errors";

type Step = 1 | 2 | 3;

const STEP_TITLES: Record<Step, string> = {
  1: "Conexión",
  2: "Base de datos",
  3: "Tablas",
};

export const SSL_OPTIONS: { value: SslMode; label: string }[] = [
  { value: "prefer", label: "Preferido (usa SSL si el servidor lo ofrece)" },
  { value: "require", label: "Obligatorio" },
  { value: "disable", label: "Desactivado" },
];

interface Props {
  onClose: () => void;
  onCreated: (project: Project) => void;
}

/** Asistente de 3 pasos: conexión → base de datos → tablas. Se monta solo mientras está abierto, así empieza limpio cada vez. */
export function NewProjectDialog({ onClose, onCreated }: Props) {
  const [step, setStep] = useState<Step>(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("5432");
  const [username, setUsername] = useState("postgres");
  const [password, setPassword] = useState("");
  const [sslMode, setSslMode] = useState<SslMode>("prefer");

  // Solo se pide la base a mano si el servidor no deja listar las bases (por ejemplo, no existe "postgres").
  const [askDatabase, setAskDatabase] = useState(false);
  const [manualDatabase, setManualDatabase] = useState("");

  const [serverVersion, setServerVersion] = useState("");
  const [databases, setDatabases] = useState<string[]>([]);
  const [database, setDatabase] = useState("");
  const [tables, setTables] = useState<DiscoveredTable[]>([]);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());

  function connection(database?: string): ConnectionInput {
    return {
      host: host.trim(),
      port: Number(port),
      username: username.trim(),
      password,
      ssl_mode: sslMode,
      database: database || null,
    };
  }

  function validateStep1(): string | null {
    if (!name.trim()) return "Ingresá el nombre del proyecto.";
    if (!host.trim()) return "Ingresá el servidor.";
    const p = Number(port);
    if (!Number.isInteger(p) || p < 1 || p > 65535) return "El puerto debe ser un número entre 1 y 65535.";
    if (!username.trim()) return "Ingresá el usuario.";
    return null;
  }

  async function handleConnect() {
    const problem = validateStep1();
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await builderApi.testConnection(connection(manualDatabase.trim()));
      if (result.databases.length === 0) {
        setError("La conexión funciona, pero el usuario no tiene acceso a ninguna base de datos.");
        return;
      }
      setServerVersion(result.server_version);
      setDatabases(result.databases);
      const manual = manualDatabase.trim();
      setDatabase(result.databases.includes(manual) ? manual : result.databases.length === 1 ? result.databases[0] : "");
      setStep(2);
    } catch (err) {
      if (databaseErrorKind(err) === "database") setAskDatabase(true);
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadTables() {
    if (!database) {
      setError("Elegí una base de datos.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const found = await builderApi.discoverTables({ ...connection(database), database });
      setTables(found);
      setSelected(new Set());
      setStep(3);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      const chosen = tables.filter((t) => selected.has(tableKey(t))).map((t) => ({ schema_name: t.schema_name, table_name: t.table_name }));
      const project = await builderApi.createProject({
        name: name.trim(),
        host: host.trim(),
        port: Number(port),
        username: username.trim(),
        password,
        ssl_mode: sslMode,
        database_name: database,
        tables: chosen,
      });
      notifySuccess(`Proyecto "${project.name}" creado.`);
      onCreated(project);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function back() {
    setError(null);
    setStep((s) => (s === 3 ? 2 : 1));
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Nuevo proyecto</DialogTitle>
          <DialogDescription>
            Paso {step} de 3 · {STEP_TITLES[step]}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive">
            <CircleAlert />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {step === 1 && (
          <form
            className="grid gap-4 sm:grid-cols-2"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              void handleConnect();
            }}
          >
            <div className="sm:col-span-2">
              <FormField label="Nombre del proyecto" htmlFor="np-name" required>
                <Input id="np-name" value={name} maxLength={80} placeholder="abmprueba" autoFocus onChange={(e) => setName(e.target.value)} />
              </FormField>
            </div>
            <FormField label="Servidor" htmlFor="np-host" required>
              <Input id="np-host" value={host} placeholder="192.168.50.11" autoComplete="off" onChange={(e) => setHost(e.target.value)} />
            </FormField>
            <FormField label="Puerto" htmlFor="np-port" required>
              <Input id="np-port" inputMode="numeric" value={port} onChange={(e) => setPort(e.target.value)} />
            </FormField>
            <FormField label="Usuario" htmlFor="np-user" required>
              <Input id="np-user" value={username} autoComplete="off" onChange={(e) => setUsername(e.target.value)} />
            </FormField>
            <FormField label="Contraseña" htmlFor="np-pass">
              <Input id="np-pass" type="password" value={password} autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} />
            </FormField>
            <div className="sm:col-span-2">
              <FormField label="SSL" htmlFor="np-ssl">
                <NativeSelect id="np-ssl" value={sslMode} onChange={(e) => setSslMode(e.target.value as SslMode)}>
                  {SSL_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
            </div>
            {askDatabase && (
              <div className="sm:col-span-2">
                <FormField label="Base de datos" htmlFor="np-db" description="No pude listar las bases del servidor: indicá el nombre de la base a la que querés conectarte.">
                  <Input id="np-db" value={manualDatabase} onChange={(e) => setManualDatabase(e.target.value)} />
                </FormField>
              </div>
            )}
            <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
          </form>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Conectado a {host}:{port} · PostgreSQL {serverVersion}. Elegí la base de datos de este proyecto.
            </p>
            <FormField label="Base de datos" htmlFor="np-database" required>
              <NativeSelect id="np-database" value={database} onChange={(e) => setDatabase(e.target.value)}>
                <option value="">Seleccioná una base…</option>
                {databases.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Elegí las tablas que querés desarrollar como API. Podés agregar más después.
            </p>
            <TablePicker tables={tables} selected={selected} onChange={(next) => setSelected(next)} disabled={busy} emptyMessage="Esta base no tiene tablas." />
          </div>
        )}

        <DialogFooter className="sm:justify-between">
          <div>
            {step > 1 && (
              <Button type="button" variant="ghost" onClick={back} disabled={busy}>
                <ChevronLeft />
                Atrás
              </Button>
            )}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Cancelar
            </Button>
            {step === 1 && (
              <Button type="button" loading={busy} onClick={() => void handleConnect()}>
                Probar conexión y continuar
              </Button>
            )}
            {step === 2 && (
              <Button type="button" loading={busy} disabled={!database} onClick={() => void handleLoadTables()}>
                Continuar
              </Button>
            )}
            {step === 3 && (
              <Button type="button" loading={busy} onClick={() => void handleCreate()}>
                {selected.size > 0 ? `Crear proyecto (${selected.size} ${selected.size === 1 ? "tabla" : "tablas"})` : "Crear proyecto"}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
