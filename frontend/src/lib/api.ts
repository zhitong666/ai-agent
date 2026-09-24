import type { AuthKind, QuotaStatus, TokenResponse } from "./types";

const TOKEN_KEY = "ai_job_agent_token";
const KIND_KEY = "ai_job_agent_auth_kind";

export function createId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getStoredAuthKind(): AuthKind {
  const value = localStorage.getItem(KIND_KEY);
  return value === "user" || value === "guest" ? value : "guest";
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function storeSession(token: string, kind: "user" | "guest") {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(KIND_KEY, kind);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(KIND_KEY);
}

function authHeaders(headers: HeadersInit = {}) {
  const next = new Headers(headers);
  const token = getAccessToken();

  if (token) {
    next.set("Authorization", `Bearer ${token}`);
  }

  return next;
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = authHeaders(init.headers);

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(path, {
    ...init,
    headers,
  });
}

export async function createGuestSession(): Promise<TokenResponse> {
  const response = await fetch("/auth/guest", {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("游客会话创建失败");
  }

  return response.json();
}

export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const response = await fetch("/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "登录失败");
  }

  return response.json();
}

export async function fetchQuota(): Promise<QuotaStatus> {
  const response = await apiFetch("/auth/quota");

  if (!response.ok) {
    throw new Error("额度查询失败");
  }

  return response.json();
}
