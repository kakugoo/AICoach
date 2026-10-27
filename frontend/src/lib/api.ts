export type Profile = { id: string; email: string; created_at: string };
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options, credentials: "include", cache: "no-store",
    headers: { ...(options.method === "POST" ? { "Content-Type": "application/json", "X-CSRF-Protection": "1" } : {}), ...options.headers },
  });
  if (!response.ok) throw new ApiError(response.status, "Не удалось выполнить запрос");
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
