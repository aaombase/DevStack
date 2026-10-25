// Small fetch wrapper: attaches the JWT, refreshes it once on 401, and turns
// DRF error payloads into readable messages.

const KEY = "devtrack.tokens";

export function getTokens() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || null;
  } catch {
    return null;
  }
}

export function setTokens(tokens) {
  localStorage.setItem(KEY, JSON.stringify(tokens));
}

export function clearTokens() {
  localStorage.removeItem(KEY);
}

export class ApiError extends Error {
  constructor(status, data) {
    super(flatten(data) || `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

function flatten(data) {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(flatten).join(" ");
  if (data.detail) return flatten(data.detail);
  return Object.entries(data)
    .map(([field, msg]) => `${field === "non_field_errors" ? "" : field + ": "}${flatten(msg)}`)
    .join(" ");
}

let refreshing = null;

async function refreshAccess() {
  const tokens = getTokens();
  if (!tokens?.refresh) return false;
  // Share one refresh between concurrent requests.
  refreshing ??= fetch("/api/auth/token/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: tokens.refresh }),
  })
    .then(async (res) => {
      if (!res.ok) return false;
      setTokens({ ...tokens, access: (await res.json()).access });
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

export async function api(path, { method = "GET", body, params, auth = true } = {}) {
  const query = params
    ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null))
    : "";

  const send = () => {
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const tokens = getTokens();
    if (auth && tokens?.access) headers.Authorization = `Bearer ${tokens.access}`;
    return fetch(`/api${path}${query}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let res = await send();
  if (res.status === 401 && auth && (await refreshAccess())) res = await send();
  if (res.status === 401 && auth) {
    clearTokens();
    window.dispatchEvent(new Event("devtrack:logout"));
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export const canEdit = (role) => ["owner", "maintainer", "developer"].includes(role);
export const canManage = (role) => ["owner", "maintainer"].includes(role);
