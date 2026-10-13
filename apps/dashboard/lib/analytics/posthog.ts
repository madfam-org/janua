"use client";

import posthog from "posthog-js";

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "";
const POSTHOG_HOST =
  process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://analytics.madfam.io";

let initialized = false;

// Invitations are capability URLs, including when embedded in a login return.
// These checks also cover SDK-added current/referrer/session attribution, not
// only the properties explicitly supplied by dashboard callers.
function invitationCapability(value: string, depth = 0): boolean {
  if (value.length > 8192 || depth > 3) return true;
  try {
    const url = new URL(value, "https://app.janua.dev");
    if (url.pathname === "/invitations/accept" && url.searchParams.has("token")) return true;
    const redirect = url.pathname === "/login" ? url.searchParams.get("redirect") : null;
    if (redirect && invitationCapability(redirect, depth + 1)) return true;
    // Attribution can encode a complete URL or an already-encoded login return.
    if (value.includes("%")) {
      const decoded = decodeURIComponent(value);
      if (decoded !== value) return invitationCapability(decoded, depth + 1);
    }
  } catch {
    // Malformed unrelated URLs are not invitation authority.
  }
  return false;
}

function sensitiveLocation(): boolean {
  if (typeof window === "undefined") return false;
  return invitationCapability(window.location.href) ||
    (typeof document !== "undefined" && invitationCapability(document.referrer));
}

function sensitivePayload(payload: unknown): boolean {
  let visited = 0;
  const seen = new Set<object>();
  function inspect(value: unknown, depth: number): boolean {
    if (++visited > 1024 || depth > 12) return true;
    if (typeof value === "string") return invitationCapability(value);
    if (value === null || typeof value !== "object") return false;
    if (seen.has(value)) return true;
    seen.add(value);
    const sensitive = Object.values(value).some(child => inspect(child, depth + 1));
    seen.delete(value);
    return sensitive;
  }
  return inspect(payload, 0);
}

export function initPostHog(): void {
  if (initialized || typeof window === "undefined") return;
  if (!POSTHOG_KEY) return;
  if (sensitiveLocation()) return;

  if (
    navigator.doNotTrack === "1" ||
    (window as unknown as { doNotTrack?: string }).doNotTrack === "1"
  ) {
    return;
  }

  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    capture_pageview: false,
    autocapture: false,
    respect_dnt: true,
    persistence: "localStorage+cookie",
    secure_cookie: true,
    disable_session_recording: true,
    before_send: event => sensitiveLocation() || sensitivePayload(event) ? null : event,
  });

  initialized = true;
}

export function identifyUser(
  userId: string,
  traits?: Record<string, unknown>,
): void {
  if (!initialized) return;
  if (sensitiveLocation()) return;
  posthog.identify(userId, traits);
}

export function resetUser(): void {
  if (!initialized) return;
  posthog.reset();
}

export function trackEvent(
  event: string,
  properties?: Record<string, unknown>,
): void {
  if (!initialized) return;
  if (sensitiveLocation()) return;
  posthog.capture(event, properties);
}
