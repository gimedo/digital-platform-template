import { branding } from "@/config/branding";

export function Footer() {
  return (
    <footer className="border-t px-4 py-3 text-center text-xs text-muted-foreground md:px-6">
      © {new Date().getFullYear()} {branding.copyright}
    </footer>
  );
}
