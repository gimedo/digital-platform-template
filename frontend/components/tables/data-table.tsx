"use client";

import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

export interface Column<T> {
  /** Nombre del campo del backend; se usa también como clave de orden. */
  key: string;
  header: string;
  sortable?: boolean;
  className?: string;
  cell: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowId: (row: T) => string | number;
  loading: boolean;
  /** Orden actual: "campo" (asc) o "-campo" (desc). */
  sort: string;
  onSortChange: (sort: string) => void;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  rowActions?: (row: T) => ReactNode;
  emptyMessage?: string;
}

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  loading,
  sort,
  onSortChange,
  page,
  pageSize,
  total,
  onPageChange,
  rowActions,
  emptyMessage = "No hay registros para mostrar.",
}: DataTableProps<T>) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const sortField = sort.replace(/^-/, "");
  const descending = sort.startsWith("-");
  const colSpan = columns.length + (rowActions ? 1 : 0);

  function toggleSort(key: string) {
    onSortChange(sortField === key && !descending ? `-${key}` : key);
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {columns.map((col) => {
                const active = sortField === col.key;
                const Icon = !active ? ArrowUpDown : descending ? ArrowDown : ArrowUp;
                return (
                  <TableHead
                    key={col.key}
                    className={col.className}
                    aria-sort={active ? (descending ? "descending" : "ascending") : undefined}
                  >
                    {col.sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(col.key)}
                        className="inline-flex cursor-pointer items-center gap-1 hover:text-primary"
                      >
                        {col.header}
                        <Icon className={cn("size-3.5", !active && "text-muted-foreground")} aria-hidden />
                      </button>
                    ) : (
                      col.header
                    )}
                  </TableHead>
                );
              })}
              {rowActions && <TableHead className="w-24 text-right">Acciones</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody className={cn(loading && rows.length > 0 && "opacity-60 transition-opacity")}>
            {loading && rows.length === 0 ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i} className="hover:bg-transparent">
                  <TableCell colSpan={colSpan}>
                    <Skeleton className="h-6 w-full" />
                  </TableCell>
                </TableRow>
              ))
            ) : rows.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={colSpan} className="h-24 text-center text-muted-foreground">
                  {emptyMessage}
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={getRowId(row)}>
                  {columns.map((col) => (
                    <TableCell key={col.key} className={col.className}>
                      {col.cell(row)}
                    </TableCell>
                  ))}
                  {rowActions && <TableCell className="text-right whitespace-nowrap">{rowActions(row)}</TableCell>}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col items-center justify-between gap-2 text-sm text-muted-foreground sm:flex-row">
        <span>{total === 0 ? "Sin resultados" : `Mostrando ${from}–${to} de ${total}`}</span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
            <ChevronLeft />
            Anterior
          </Button>
          <span aria-live="polite">
            Página {page} de {totalPages}
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
            Siguiente
            <ChevronRight />
          </Button>
        </div>
      </div>
    </div>
  );
}
