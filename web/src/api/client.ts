import axios from "axios";

export const apiClient = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (typeof d !== "object" || d === null) return String(d);
          const loc = Array.isArray(d.loc) ? d.loc.join(".") : "";
          const msg = d.msg ?? String(d);
          return loc ? `${loc}: ${msg}` : msg;
        })
        .join("; ");
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Неизвестная ошибка";
}
