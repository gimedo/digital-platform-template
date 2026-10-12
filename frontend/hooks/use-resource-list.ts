"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Page } from "@/lib/types";

interface Options {
  pageSize?: number;
  defaultSort?: string;
}

/**
 * Lista paginada contra un endpoint estándar del backend (`GET /api/<recurso>`):
 * búsqueda, filtros, orden y paginación. Cancela la petición anterior si cambian los parámetros.
 */
export function useResourceList<T>(endpoint: string, { pageSize = 10, defaultSort = "-id" }: Options = {}) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sort, setSort] = useState(defaultSort);
  const [data, setData] = useState<Page<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    api
      .get<Page<T>>(
        endpoint,
        { search, order_by: sort, limit: pageSize, offset: (page - 1) * pageSize, ...filters },
        controller.signal,
      )
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [endpoint, search, sort, page, pageSize, filters, reloadKey]);

  const changeSearch = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const changeFilter = useCallback((name: string, value: string) => {
    setFilters((prev) => ({ ...prev, [name]: value }));
    setPage(1);
  }, []);

  const changeSort = useCallback((value: string) => {
    setSort(value);
    setPage(1);
  }, []);

  const clearFilters = useCallback(() => {
    setSearch("");
    setFilters({});
    setPage(1);
  }, []);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  return {
    data,
    loading,
    error,
    page,
    pageSize,
    search,
    filters,
    sort,
    setPage,
    changeSearch,
    changeFilter,
    changeSort,
    clearFilters,
    reload,
  };
}
