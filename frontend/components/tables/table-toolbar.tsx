"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { useDebounce } from "@/hooks/use-debounce";

export interface FilterConfig {
  name: string;
  label: string;
  options: { value: string; label: string }[];
}

interface TableToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters?: FilterConfig[];
  filterValues: Record<string, string>;
  onFilterChange: (name: string, value: string) => void;
  onClear: () => void;
  actions?: ReactNode;
}

export function TableToolbar({
  search,
  onSearchChange,
  searchPlaceholder = "Buscar…",
  filters = [],
  filterValues,
  onFilterChange,
  onClear,
  actions,
}: TableToolbarProps) {
  const [text, setText] = useState(search);
  const debounced = useDebounce(text, 350);

  // Búsqueda con retardo: no consulta al backend en cada tecla.
  useEffect(() => {
    if (debounced !== search) onSearchChange(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  // Si se limpian los filtros desde afuera, se limpia también el cuadro de búsqueda.
  useEffect(() => {
    if (search === "") setText("");
  }, [search]);

  const hasActiveFilters = Boolean(search) || Object.values(filterValues).some(Boolean);

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className="relative w-full sm:max-w-xs">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={searchPlaceholder}
          className="pl-8"
          aria-label="Buscar"
        />
      </div>
      {filters.map((filter) => (
        <div key={filter.name} className="w-full sm:w-44">
          <NativeSelect
            aria-label={filter.label}
            value={filterValues[filter.name] ?? ""}
            onChange={(e) => onFilterChange(filter.name, e.target.value)}
          >
            <option value="">{filter.label}: todos</option>
            {filter.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </NativeSelect>
        </div>
      ))}
      {hasActiveFilters && (
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X />
          Limpiar
        </Button>
      )}
      {actions && <div className="sm:ml-auto">{actions}</div>}
    </div>
  );
}
