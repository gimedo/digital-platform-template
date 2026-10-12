import { toast } from "sonner";
import { ApiError } from "./api";

export function getErrorMessage(err: unknown, fallback = "Ocurrió un error inesperado."): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export function notifyError(err: unknown, fallback?: string) {
  toast.error(getErrorMessage(err, fallback));
}

export function notifySuccess(message: string) {
  toast.success(message);
}
