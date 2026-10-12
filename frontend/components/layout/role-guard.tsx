"use client";

import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";

/**
 * Comodidad de interfaz: evita mostrar pantallas a quien no corresponde.
 * La seguridad real la aplica el backend en cada endpoint.
 */
export function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) {
    return (
      <Alert variant="destructive">
        <ShieldAlert />
        <AlertTitle>Sin permisos</AlertTitle>
        <AlertDescription>No tenés permisos para ver esta sección.</AlertDescription>
      </Alert>
    );
  }
  return <>{children}</>;
}
