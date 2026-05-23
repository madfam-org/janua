import { z } from "zod";

const httpsOrLocalRedirect = z
  .string()
  .refine((uri) => {
    try {
      const url = new URL(uri);
      if (
        url.hostname === "localhost" ||
        url.hostname === "127.0.0.1" ||
        url.hostname.endsWith(".localhost")
      ) {
        return true;
      }
      return url.protocol === "https:";
    } catch {
      return false;
    }
  }, "Redirect URI must use HTTPS (localhost/127.0.0.1 allowed for development)");

export const oauthClientManifestSchema = z
  .object({
    apiVersion: z.literal("janua.dev/v1"),
    kind: z.literal("OAuthClient"),
    metadata: z.object({
      name: z
        .string()
        .min(1)
        .max(255)
        .regex(
          /^[a-z0-9][a-z0-9._-]*$/,
          "metadata.name must be lowercase alphanumeric with . _ -"
        ),
    }),
    spec: z.object({
      audience: z.string().min(1).max(255).optional(),
      description: z.string().max(1000).optional(),
      redirect_uris: z.array(httpsOrLocalRedirect).default([]),
      allowed_scopes: z
        .array(z.string())
        .default(["openid", "profile", "email"]),
      grant_types: z
        .array(
          z.enum([
            "authorization_code",
            "refresh_token",
            "client_credentials",
            "implicit",
          ])
        )
        .default(["authorization_code", "refresh_token"]),
      is_confidential: z.boolean().default(true),
      organization_id: z.string().uuid().nullable().optional(),
      logo_url: z.string().url().max(500).optional(),
      website_url: z.string().url().max(500).optional(),
    }),
  })
  .superRefine((manifest, ctx) => {
    const grants = manifest.spec.grant_types;
    const interactive = grants.some((g) =>
      ["authorization_code", "implicit"].includes(g)
    );
    if (interactive && manifest.spec.redirect_uris.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message:
          "spec.redirect_uris is required when grant_types include authorization_code or implicit",
        path: ["spec", "redirect_uris"],
      });
    }
  });

export type OAuthClientManifest = z.infer<typeof oauthClientManifestSchema>;

export const multiClientManifestSchema = z.object({
  apiVersion: z.literal("janua.dev/v1"),
  kind: z.literal("OAuthClientList"),
  clients: z.array(oauthClientManifestSchema).min(1),
});

export type MultiClientManifest = z.infer<typeof multiClientManifestSchema>;

export function manifestToRegisterBody(manifest: OAuthClientManifest): Record<string, unknown> {
  const { spec, metadata } = manifest;
  return {
    name: metadata.name,
    description: spec.description,
    redirect_uris: spec.redirect_uris,
    allowed_scopes: spec.allowed_scopes,
    grant_types: spec.grant_types,
    audience: spec.audience,
    organization_id: spec.organization_id ?? undefined,
    logo_url: spec.logo_url,
    website_url: spec.website_url,
    is_confidential: spec.is_confidential,
  };
}

export interface RemoteOAuthClient {
  id: string;
  client_id: string;
  client_secret?: string | null;
  name: string;
  description?: string | null;
  redirect_uris: string[];
  allowed_scopes: string[];
  grant_types: string[];
  audience?: string | null;
  is_active?: boolean;
  is_confidential?: boolean;
  organization_id?: string | null;
}

export function compareManifestToRemote(
  manifest: OAuthClientManifest,
  remote: RemoteOAuthClient
): string[] {
  const diffs: string[] = [];
  const spec = manifest.spec;

  if (remote.name !== manifest.metadata.name) {
    diffs.push(`name: remote=${remote.name} manifest=${manifest.metadata.name}`);
  }
  if ((remote.audience ?? null) !== (spec.audience ?? null)) {
    diffs.push(
      `audience: remote=${remote.audience ?? "(null)"} manifest=${spec.audience ?? "(null)"}`
    );
  }
  if (remote.is_confidential !== spec.is_confidential) {
    diffs.push(
      `is_confidential: remote=${remote.is_confidential} manifest=${spec.is_confidential}`
    );
  }

  const sort = (values: string[]) => [...values].sort().join(",");
  if (sort(remote.redirect_uris ?? []) !== sort(spec.redirect_uris)) {
    diffs.push("redirect_uris mismatch");
  }
  if (sort(remote.allowed_scopes ?? []) !== sort(spec.allowed_scopes)) {
    diffs.push("allowed_scopes mismatch");
  }
  if (sort(remote.grant_types ?? []) !== sort(spec.grant_types)) {
    diffs.push("grant_types mismatch");
  }
  if ((remote.organization_id ?? null) !== (spec.organization_id ?? null)) {
    diffs.push("organization_id mismatch");
  }

  return diffs;
}
