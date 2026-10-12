import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-5xl font-semibold">404</p>
      <p className="text-muted-foreground">La página que buscás no existe.</p>
      <Link href="/dashboard" className={buttonVariants()}>
        Ir al inicio
      </Link>
    </div>
  );
}
