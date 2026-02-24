import {
  getApiUrl,
  getAccessToken,
  getRefreshToken,
  setConfig,
} from "./config.js";

export interface ApiResponse<T = unknown> {
  ok: boolean;
  status: number;
  data: T;
}

export interface ApiError {
  detail: string;
  code?: string;
}

async function refreshAccessToken(apiUrl: string): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${apiUrl}/api/v1/auth/token/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) return false;

    const data = (await response.json()) as {
      access_token: string;
      refresh_token?: string;
    };
    setConfig({
      accessToken: data.access_token,
      ...(data.refresh_token ? { refreshToken: data.refresh_token } : {}),
    });
    return true;
  } catch {
    return false;
  }
}

function buildHeaders(token: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function request<T = unknown>(
  method: string,
  path: string,
  body?: unknown,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  const apiUrl = apiUrlOverride || getApiUrl();
  let token = getAccessToken();
  const url = `${apiUrl}${path}`;

  let response = await fetch(url, {
    method,
    headers: buildHeaders(token),
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  if (response.status === 401 && token) {
    const refreshed = await refreshAccessToken(apiUrl);
    if (refreshed) {
      token = getAccessToken();
      response = await fetch(url, {
        method,
        headers: buildHeaders(token),
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
    }
  }

  let data: T;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = (await response.json()) as T;
  } else {
    data = (await response.text()) as unknown as T;
  }

  if (!response.ok) {
    const errorData = data as unknown as ApiError;
    const message =
      typeof errorData === "object" && errorData !== null && "detail" in errorData
        ? errorData.detail
        : `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return { ok: true, status: response.status, data };
}

export async function get<T = unknown>(
  path: string,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  return request<T>("GET", path, undefined, apiUrlOverride);
}

export async function post<T = unknown>(
  path: string,
  body?: unknown,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  return request<T>("POST", path, body, apiUrlOverride);
}

export async function patch<T = unknown>(
  path: string,
  body?: unknown,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  return request<T>("PATCH", path, body, apiUrlOverride);
}

export async function del<T = unknown>(
  path: string,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  return request<T>("DELETE", path, undefined, apiUrlOverride);
}
