import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { branding } from "@/config/branding";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: { default: branding.name, template: `%s · ${branding.name}` },
  description: branding.tagline,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-background font-sans antialiased">
        <AuthProvider>{children}</AuthProvider>
        <Toaster />
      </body>
    </html>
  );
}
