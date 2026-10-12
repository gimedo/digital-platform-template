"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

// Error inesperado de renderizado en cualquier página fuera del dashboard.
export default function RootError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-xl font-semibold">Algo salió mal</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Ocurrió un error inesperado. Podés reintentar; si persiste, avisá al equipo responsable.
      </p>
      <Button onClick={reset}>Reintentar</Button>
    </div>
  );
}
