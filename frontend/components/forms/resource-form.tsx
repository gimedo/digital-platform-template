"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { FormField } from "./form-field";

export type FieldType = "text" | "email" | "password" | "select" | "checkbox";

export interface FieldConfig {
  name: string;
  label: string;
  type: FieldType;
  /** true = siempre; "create" = solo al crear (ej.: contraseña). */
  required?: boolean | "create";
  placeholder?: string;
  description?: string;
  options?: { value: string; label: string }[];
  defaultValue?: string | boolean;
  autoComplete?: string;
  /** Al editar, un valor vacío no se envía (ej.: contraseña que no se quiere cambiar). */
  omitOnEditIfEmpty?: boolean;
}

export type FormValues = Record<string, string | boolean>;

interface ResourceFormProps {
  fields: FieldConfig[];
  mode: "create" | "edit";
  initialValues?: Partial<FormValues>;
  submitting: boolean;
  /** Errores por campo devueltos por el backend (422). */
  serverErrors?: Record<string, string>;
  submitLabel?: string;
  onSubmit: (payload: Record<string, unknown>) => void | Promise<void>;
  onCancel: () => void;
}

function initialState(fields: FieldConfig[], initial?: Partial<FormValues>): FormValues {
  const state: FormValues = {};
  for (const f of fields) {
    const fallback = f.defaultValue ?? (f.type === "checkbox" ? false : "");
    state[f.name] = initial?.[f.name] ?? fallback;
  }
  return state;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Formulario genérico de alta/edición a partir de una lista de campos. */
export function ResourceForm({
  fields,
  mode,
  initialValues,
  submitting,
  serverErrors,
  submitLabel,
  onSubmit,
  onCancel,
}: ResourceFormProps) {
  const [values, setValues] = useState<FormValues>(() => initialState(fields, initialValues));
  const [errors, setErrors] = useState<Record<string, string>>({});

  const isRequired = (f: FieldConfig) => f.required === true || (f.required === "create" && mode === "create");

  function validate(): boolean {
    const next: Record<string, string> = {};
    for (const f of fields) {
      const value = values[f.name];
      if (f.type === "checkbox") continue;
      const text = String(value ?? "").trim();
      if (isRequired(f) && !text) next[f.name] = "Este campo es obligatorio";
      else if (text && f.type === "email" && !EMAIL_RE.test(text)) next[f.name] = "Ingresá un correo válido";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!validate()) return;

    const payload: Record<string, unknown> = {};
    for (const f of fields) {
      const value = values[f.name];
      if (f.type === "checkbox") {
        payload[f.name] = Boolean(value);
        continue;
      }
      const text = typeof value === "string" ? value.trim() : "";
      const omit = mode === "edit" && (f.omitOnEditIfEmpty ?? f.type === "password") && text === "";
      if (!omit) payload[f.name] = f.type === "password" ? String(value) : text;
    }
    void onSubmit(payload);
  }

  function setValue(name: string, value: string | boolean) {
    setValues((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: "" }));
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      {fields.map((f) => {
        const id = `field-${f.name}`;
        const error = errors[f.name] || serverErrors?.[f.name];

        if (f.type === "checkbox") {
          return (
            <label key={f.name} htmlFor={id} className="flex items-center gap-2 text-sm font-medium">
              <input
                id={id}
                type="checkbox"
                className="size-4 rounded border-input accent-primary"
                checked={Boolean(values[f.name])}
                onChange={(e) => setValue(f.name, e.target.checked)}
              />
              {f.label}
            </label>
          );
        }

        return (
          <FormField
            key={f.name}
            label={f.label}
            htmlFor={id}
            required={isRequired(f)}
            description={f.description}
            error={error}
          >
            {f.type === "select" ? (
              <NativeSelect
                id={id}
                value={String(values[f.name] ?? "")}
                aria-invalid={Boolean(error)}
                onChange={(e) => setValue(f.name, e.target.value)}
              >
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </NativeSelect>
            ) : (
              <Input
                id={id}
                type={f.type}
                value={String(values[f.name] ?? "")}
                placeholder={f.placeholder}
                autoComplete={f.autoComplete ?? (f.type === "password" ? "new-password" : "off")}
                aria-invalid={Boolean(error)}
                onChange={(e) => setValue(f.name, e.target.value)}
              />
            )}
          </FormField>
        );
      })}

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" loading={submitting}>
          {submitLabel ?? (mode === "create" ? "Crear" : "Guardar cambios")}
        </Button>
      </div>
    </form>
  );
}
