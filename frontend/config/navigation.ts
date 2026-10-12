import { Database, LayoutDashboard, Users, type LucideIcon } from "lucide-react";
import type { Role } from "@/lib/types";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  /** Si se define, solo esos roles ven el ítem. */
  roles?: Role[];
}

// Para agregar una pantalla al menú: sumar un ítem acá.
export const navigation: NavItem[] = [
  { title: "Inicio", href: "/dashboard", icon: LayoutDashboard },
  { title: "Usuarios", href: "/dashboard/users", icon: Users, roles: ["admin"] },
  { title: "API Builder", href: "/dashboard/builder", icon: Database, roles: ["admin"] },
];
