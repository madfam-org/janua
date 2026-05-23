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

export interface ApiErrorBody {
  detail?: string | { msg: string }[];
  code?: string;
}

function parseErrorMessage(data: unknown, status: number): string {
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = (data as ApiErrorBody).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => d.msg).join("; ");
    }
  }
  return `Request failed with status ${status}`;
}

function throwApiError(data: unknown, status: number): never {
  const error = new Error(parseErrorMessage(data, status)) as Error & {
    status?: number;
  };
  error.status = status;
  throw error;
}

function getProvisionApiKey(explicit?: string): string {
  const key =
    explicit ||
    process.env.JANUA_INTERNAL_API_KEY ||
    process.env.INTERNAL_API_KEY;
  if (!key) {
    throw new Error(
      "Missing internal API key. Set JANUA_INTERNAL_API_KEY or pass --internal-api-key."
    );
  }
  return key;
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

async function adminRequest<T>(
  method: string,
  path: string,
  body?: unknown,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  const apiUrl = apiUrlOverride || getApiUrl();
  let token = getAccessToken();
  const url = `${apiUrl}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let response = await fetch(url, {
    method,
    headers,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (response.status === 401 && token) {
    const refreshed = await refreshAccessToken(apiUrl);
    if (refreshed) {
      token = getAccessToken();
      headers.Authorization = `Bearer ${token}`;
      response = await fetch(url, {
        method,
        headers,
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
    }
  }

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? ((await response.json()) as T)
    : (((await response.text()) as unknown) as T);

  if (!response.ok) {
    throwApiError(data, response.status);
  }

  return { ok: true, status: response.status, data };
}

async function provisionRequest<T>(
  method: string,
  path: string,
  body?: unknown,
  apiUrlOverride?: string,
  internalApiKey?: string
): Promise<ApiResponse<T>> {
  const apiUrl = apiUrlOverride || getApiUrl();
  const key = getProvisionApiKey(internalApiKey);
  const url = `${apiUrl}${path}`;

  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Internal-API-Key": key,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? ((await response.json()) as T)
    : (((await response.text()) as unknown) as T);

  if (!response.ok) {
    throwApiError(data, response.status);
  }

  return { ok: true, status: response.status, data };
}

export async function provisionRegister<T>(
  body: unknown,
  apiUrlOverride?: string,
  internalApiKey?: string
): Promise<ApiResponse<T>> {
  return provisionRequest<T>(
    "POST",
    "/api/v1/oauth/clients/register",
    body,
    apiUrlOverride,
    internalApiKey
  );
}

export async function provisionLookupByName<T>(
  name: string,
  apiUrlOverride?: string,
  internalApiKey?: string
): Promise<ApiResponse<T>> {
  const encoded = encodeURIComponent(name);
  return provisionRequest<T>(
    "GET",
    `/api/v1/oauth/clients/internal/by-name/${encoded}`,
    undefined,
    apiUrlOverride,
    internalApiKey
  );
}

export async function adminGet<T>(
  path: string,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  return adminRequest<T>("GET", path, undefined, apiUrlOverride);
}

export async function adminPost<T>(
  path: string,
  body?: unknown,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  return adminRequest<T>("POST", path, body, apiUrlOverride);
}

export async function adminPatch<T>(
  path: string,
  body?: unknown,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  return adminRequest<T>("PATCH", path, body, apiUrlOverride);
}

export async function adminDelete<T>(
  path: string,
  apiUrlOverride?: string
): Promise<ApiResponse<T>> {
  return adminRequest<T>("DELETE", path, undefined, apiUrlOverride);
}

/** @deprecated Use adminGet — kept for existing command modules */
export const get = adminGet;
/** @deprecated Use adminPost */
export const post = adminPost;
/** @deprecated Use adminPatch */
export const patch = adminPatch;
/** @deprecated Use adminDelete */
export const del = adminDelete;
