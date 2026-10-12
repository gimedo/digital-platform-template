"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";

/** Montar una sola vez en app/layout.tsx. Para notificar: toast.success(...) / notifyError(...). */
function Toaster(props: ToasterProps) {
  return <Sonner richColors closeButton position="top-right" {...props} />;
}

export { Toaster };
