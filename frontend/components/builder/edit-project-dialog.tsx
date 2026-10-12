"use client";

import { useState, type FormEvent } from "react";
import { CircleAlert } from "lucide-react";
import { FormField } from "@/components/forms/form-field";
import { SSL_OPTIONS } from "@/components/builder/new-project-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { builderApi, type Project, type ProjectUpdate, type SslMode } from "@/lib/builder";
import { getErrorMessage, notifySuccess } from "@/lib/errors";

interface Props {
  project: Project;
  onClose: () => void;
  onSaved: (project: Project) => void;
}

export function EditProjectDialog({ project, onClose, onSaved }: Props) {
  const [name, setName] = useState(project.name);
  const [host, setHost] = useState(project.host);
  const [port, setPort] = useState(String(project.port));
  const [username, setUsername] = useState(project.username);
  const [password, setPassword] = useState("");
  const [sslMode, setSslMode] = useState<SslMode>(project.ssl_mode);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const p = Number(port);
    if (!name.trim() || !host.trim() || !username.trim()) {
      setError("Nombre, servidor y usuario son obligatorios.");
      return;
    }
    if (!Number.isInteger(p) || p < 1 || p > 65535) {
      setError("El puerto debe ser un número entre 1 y 65535.");
      return;
    }
    const changes: ProjectUpdate = { name: name.trim(), host: host.trim(), port: p, username: username.trim(), ssl_mode: sslMode };
    if (password) changes.password = password; // vacío = conservar la contraseña guardada
    setBusy(true);
    setError(null);
    try {
      const saved = await builderApi.updateProject(project.id, changes);
      notifySuccess("Conexión actualizada.");
      onSaved(saved);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar conexión</DialogTitle>
          <DialogDescription>La base de datos ({project.database_name}) no se puede cambiar: para otra base, creá otro proyecto.</DialogDescription>
        </DialogHeader>
        <form onSubmit={(e) => void handleSubmit(e)} className="grid gap-4 sm:grid-cols-2" noValidate>
          {error && (
            <Alert variant="destructive" className="sm:col-span-2">
              <CircleAlert />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="sm:col-span-2">
            <FormField label="Nombre del proyecto" htmlFor="ep-name" required>
              <Input id="ep-name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
            </FormField>
          </div>
          <FormField label="Servidor" htmlFor="ep-host" required>
            <Input id="ep-host" value={host} onChange={(e) => setHost(e.target.value)} />
          </FormField>
          <FormField label="Puerto" htmlFor="ep-port" required>
            <Input id="ep-port" inputMode="numeric" value={port} onChange={(e) => setPort(e.target.value)} />
          </FormField>
          <FormField label="Usuario" htmlFor="ep-user" required>
            <Input id="ep-user" value={username} autoComplete="off" onChange={(e) => setUsername(e.target.value)} />
          </FormField>
          <FormField label="Contraseña" htmlFor="ep-pass" description="Dejala vacía para conservar la guardada.">
            <Input id="ep-pass" type="password" value={password} autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} />
          </FormField>
          <div className="sm:col-span-2">
            <FormField label="SSL" htmlFor="ep-ssl">
              <NativeSelect id="ep-ssl" value={sslMode} onChange={(e) => setSslMode(e.target.value as SslMode)}>
                {SSL_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </NativeSelect>
            </FormField>
          </div>
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Cancelar
            </Button>
            <Button type="submit" loading={busy}>
              Guardar cambios
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
