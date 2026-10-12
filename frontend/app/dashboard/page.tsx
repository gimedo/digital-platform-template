"use client";

import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Page, User } from "@/lib/types";

export default function DashboardPage() {
  const { user } = useAuth();
  const [totalUsers, setTotalUsers] = useState<number | null>(null);

  useEffect(() => {
    if (user?.role !== "admin") return;
    api
      .get<Page<User>>("/users", { limit: 1 })
      .then((p) => setTotalUsers(p.total))
      .catch(() => setTotalUsers(null)); // es un dato accesorio: si falla, no se muestra
  }, [user?.role]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Hola, {user?.full_name}</h1>
        <p className="text-sm text-muted-foreground">Bienvenido a la plataforma.</p>
      </div>

      {totalUsers !== null && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardDescription className="flex items-center gap-2">
                <Users className="size-4" aria-hidden /> Usuarios registrados
              </CardDescription>
              <CardTitle className="text-3xl">{totalUsers}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">Total de cuentas en la plataforma.</CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
