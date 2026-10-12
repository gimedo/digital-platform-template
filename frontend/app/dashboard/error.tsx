"use client";

import { useEffect } from "react";
import { CircleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

// Un error en una página queda contenido aquí: el menú y la barra superior siguen funcionando.
export default function DashboardError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <Alert variant="destructive">
      <CircleAlert />
      <AlertTitle>Esta pantalla tuvo un problema</AlertTitle>
      <AlertDescription>
        <p>Ocurrió un error inesperado al mostrarla.</p>
        <Button variant="outline" size="sm" className="mt-2 text-foreground" onClick={reset}>
          Reintentar
        </Button>
      </AlertDescription>
    </Alert>
  );
}
