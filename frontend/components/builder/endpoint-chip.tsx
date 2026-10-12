import { Check } from "lucide-react";
import type { EndpointVisual, HttpMethod } from "@/lib/builder";
import { cn } from "@/lib/utils";

// Tres estados por método. Las clases van completas (no armadas con variables) para que Tailwind las detecte.
const STYLES: Record<HttpMethod, { pending: string; generated: string }> = {
  GET: {
    pending: "border-blue-300 bg-blue-100 text-blue-800 hover:bg-blue-200 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200",
    generated: "border-blue-600 bg-blue-600 text-white",
  },
  POST: {
    pending: "border-emerald-300 bg-emerald-100 text-emerald-800 hover:bg-emerald-200 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
    generated: "border-emerald-600 bg-emerald-600 text-white",
  },
  PUT: {
    pending: "border-amber-300 bg-amber-100 text-amber-800 hover:bg-amber-200 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200",
    generated: "border-amber-500 bg-amber-500 text-white",
  },
  DELETE: {
    pending: "border-red-300 bg-red-100 text-red-800 hover:bg-red-200 dark:border-red-800 dark:bg-red-950 dark:text-red-200",
    generated: "border-red-600 bg-red-600 text-white",
  },
};

const OFF = "border-dashed border-border bg-muted/40 text-muted-foreground/70 hover:bg-muted";

interface EndpointChipProps {
  method: HttpMethod;
  visual: EndpointVisual;
  /** Texto que explica por qué no se puede cambiar (se muestra al pasar el mouse). */
  disabledReason?: string;
  busy?: boolean;
  onToggle?: () => void;
}

/** Casilla de un endpoint: gris = sin marcar, color claro = marcado (se generará), color pleno = ya generado. */
export function EndpointChip({ method, visual, disabledReason, busy = false, onToggle }: EndpointChipProps) {
  const checked = visual !== "off";
  const locked = visual === "generated" || Boolean(disabledReason);
  const disabled = locked || busy || !onToggle;

  const title =
    disabledReason ??
    (visual === "generated" ? "Ya generado" : visual === "pending" ? "Marcado: se generará" : "Sin marcar: no se generará");

  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={`${method}: ${title}`}
      title={title}
      disabled={disabled}
      onClick={onToggle}
      data-visual={visual}
      className={cn(
        "inline-flex h-7 min-w-[4.75rem] cursor-pointer items-center justify-center gap-1.5 rounded-md border px-2 text-xs font-semibold transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
        visual === "off" ? OFF : STYLES[method][visual],
        disabledReason && "opacity-50",
        disabled && "cursor-not-allowed",
        busy && "animate-pulse",
      )}
    >
      <span
        className={cn(
          "flex size-3.5 items-center justify-center rounded-[3px] border",
          checked ? "border-current/60 bg-white/30" : "border-muted-foreground/40",
        )}
        aria-hidden
      >
        {checked && <Check className="size-3" strokeWidth={3} />}
      </span>
      {method}
    </button>
  );
}
