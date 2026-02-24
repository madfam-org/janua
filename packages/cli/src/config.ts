import Conf from "conf";

export interface JanuaConfig {
  apiUrl: string;
  accessToken: string;
  refreshToken: string;
  email: string;
}

const DEFAULT_API_URL = "http://localhost:4100";

const store = new Conf<Partial<JanuaConfig>>({
  projectName: "janua",
  projectSuffix: "",
  defaults: {
    apiUrl: DEFAULT_API_URL,
    accessToken: "",
    refreshToken: "",
    email: "",
  },
});

export function getConfig(): Partial<JanuaConfig> {
  return {
    apiUrl: store.get("apiUrl") || DEFAULT_API_URL,
    accessToken: store.get("accessToken") || "",
    refreshToken: store.get("refreshToken") || "",
    email: store.get("email") || "",
  };
}

export function setConfig(values: Partial<JanuaConfig>): void {
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) {
      store.set(key as keyof JanuaConfig, value);
    }
  }
}

export function clearConfig(): void {
  store.set("accessToken", "");
  store.set("refreshToken", "");
  store.set("email", "");
}

export function getApiUrl(): string {
  return store.get("apiUrl") || DEFAULT_API_URL;
}

export function getAccessToken(): string {
  return store.get("accessToken") || "";
}

export function getRefreshToken(): string {
  return store.get("refreshToken") || "";
}

export function isAuthenticated(): boolean {
  const token = getAccessToken();
  if (!token) return false;

  try {
    const payload = JSON.parse(
      Buffer.from(token.split(".")[1], "base64").toString()
    );
    const exp = payload.exp;
    if (!exp) return false;
    return Date.now() / 1000 < exp;
  } catch {
    return false;
  }
}

export function getTokenPayload(): Record<string, unknown> | null {
  const token = getAccessToken();
  if (!token) return null;
  try {
    return JSON.parse(
      Buffer.from(token.split(".")[1], "base64").toString()
    ) as Record<string, unknown>;
  } catch {
    return null;
  }
}
