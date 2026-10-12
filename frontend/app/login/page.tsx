import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Ingresar" };

export default function LoginPage() {
  // useSearchParams (en LoginForm) requiere un límite de Suspense.
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
