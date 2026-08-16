const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "story_assistant_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type FetchOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string>;
  skipAuth?: boolean;
  signal?: AbortSignal;
};

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const url = new URL(BASE_URL + path);
  if (options.query) {
    for (const [key, value] of Object.entries(options.query)) url.searchParams.set(key, value);
  }

  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token && !options.skipAuth) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });

  if (response.status === 401) {
    clearToken();
    window.location.assign("/login");
    throw new ApiError(401, "Session expired — sign in again.");
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.detail ?? `Request failed (${response.status})`;
    throw new ApiError(response.status, typeof message === "string" ? message : JSON.stringify(message));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

type StreamEvent = { delta?: string; done?: boolean; error?: string };

/** POST + read a `text/event-stream` body, invoking onDelta per chunk as it
 * arrives. Separate from apiFetch since the response here is never a single
 * JSON body — used by the generation endpoints only. */
export async function apiStream(
  path: string,
  body: unknown,
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(BASE_URL + path, { method: "POST", headers, body: JSON.stringify(body), signal });

  if (response.status === 401) {
    clearToken();
    window.location.assign("/login");
    throw new ApiError(401, "Session expired — sign in again.");
  }

  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => null);
    const message = payload?.detail ?? `Request failed (${response.status})`;
    throw new ApiError(response.status, typeof message === "string" ? message : JSON.stringify(message));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      if (!frame.startsWith("data: ")) continue;
      const event = JSON.parse(frame.slice(6)) as StreamEvent;
      if (event.error) throw new ApiError(500, event.error);
      if (event.delta) onDelta(event.delta);
      if (event.done) return;
    }
  }
}
