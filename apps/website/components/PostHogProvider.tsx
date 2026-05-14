"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { initPostHog } from "@/lib/analytics/posthog";

type PostHogWindow = Window & {
  posthog?: {
    capture: (eventName: string) => void;
  };
};

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    initPostHog();
  }, []);

  useEffect(() => {
    const posthogWindow = window as PostHogWindow;
    if (posthogWindow.posthog) {
      posthogWindow.posthog.capture("$pageview");
    }
  }, [pathname, searchParams]);

  return <>{children}</>;
}
