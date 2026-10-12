"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { PageSpinner } from "@/components/feedback/page-spinner";
import { useAuth } from "@/lib/auth";

/** Protege un grupo de páginas: sin sesión redirige a /login (y vuelve luego a la página pedida). */
export function AuthGuard({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, router, pathname]);

  if (status !== "authenticated") return <PageSpinner />;
  return <>{children}</>;
}
