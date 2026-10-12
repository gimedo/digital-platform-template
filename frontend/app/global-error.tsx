"use client";

// Último recurso: reemplaza al layout raíz, por eso lleva su propio <html> y estilos mínimos en línea.
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="es">
      <body style={{ fontFamily: "system-ui, sans-serif", display: "grid", placeItems: "center", minHeight: "100vh", margin: 0 }}>
        <div style={{ textAlign: "center", padding: 24 }}>
          <h1 style={{ fontSize: 20 }}>Error inesperado</h1>
          <p style={{ color: "#666" }}>La aplicación no pudo cargarse correctamente.</p>
          <button onClick={reset} style={{ padding: "8px 16px", cursor: "pointer" }}>
            Reintentar
          </button>
        </div>
      </body>
    </html>
  );
}
