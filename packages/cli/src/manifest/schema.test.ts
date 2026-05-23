import { describe, expect, it } from "vitest";
import {
  compareManifestToRemote,
  manifestToRegisterBody,
  oauthClientManifestSchema,
  type RemoteOAuthClient,
} from "./schema.js";

const baseManifest = {
  apiVersion: "janua.dev/v1" as const,
  kind: "OAuthClient" as const,
  metadata: { name: "my-service-web" },
  spec: {
    audience: "my-service-api",
    redirect_uris: [
      "https://app.example.com/api/auth/callback",
      "http://localhost:3000/api/auth/callback",
    ],
    allowed_scopes: ["openid", "profile", "email"],
    grant_types: ["authorization_code", "refresh_token"] as const,
    is_confidential: true,
  },
};

describe("oauthClientManifestSchema", () => {
  it("accepts a valid interactive client manifest", () => {
    const parsed = oauthClientManifestSchema.parse(baseManifest);
    expect(parsed.metadata.name).toBe("my-service-web");
  });

  it("rejects non-https production redirect URIs", () => {
    expect(() =>
      oauthClientManifestSchema.parse({
        ...baseManifest,
        spec: {
          ...baseManifest.spec,
          redirect_uris: ["http://app.example.com/callback"],
        },
      })
    ).toThrow();
  });

  it("allows machine clients without redirect URIs", () => {
    const parsed = oauthClientManifestSchema.parse({
      ...baseManifest,
      metadata: { name: "probe" },
      spec: {
        redirect_uris: [],
        grant_types: ["client_credentials"],
        allowed_scopes: ["openid", "yantra4d:quote"],
        is_confidential: true,
      },
    });
    expect(parsed.spec.redirect_uris).toEqual([]);
  });

  it("requires redirect URIs for authorization_code grants", () => {
    expect(() =>
      oauthClientManifestSchema.parse({
        ...baseManifest,
        spec: {
          ...baseManifest.spec,
          redirect_uris: [],
        },
      })
    ).toThrow();
  });
});

describe("manifestToRegisterBody", () => {
  it("maps manifest fields to register API payload", () => {
    const manifest = oauthClientManifestSchema.parse(baseManifest);
    expect(manifestToRegisterBody(manifest)).toEqual({
      name: "my-service-web",
      client_id: undefined,
      description: undefined,
      redirect_uris: manifest.spec.redirect_uris,
      allowed_scopes: manifest.spec.allowed_scopes,
      grant_types: manifest.spec.grant_types,
      audience: "my-service-api",
      organization_id: undefined,
      logo_url: undefined,
      website_url: undefined,
      is_confidential: true,
    });
  });
});

describe("compareManifestToRemote", () => {
  it("returns no drift when remote matches manifest", () => {
    const manifest = oauthClientManifestSchema.parse(baseManifest);
    const remote: RemoteOAuthClient = {
      id: "1",
      client_id: "jnc_test",
      name: "my-service-web",
      redirect_uris: manifest.spec.redirect_uris,
      allowed_scopes: manifest.spec.allowed_scopes,
      grant_types: manifest.spec.grant_types,
      audience: "my-service-api",
      is_confidential: true,
    };
    expect(compareManifestToRemote(manifest, remote)).toEqual([]);
  });

  it("detects audience drift", () => {
    const manifest = oauthClientManifestSchema.parse(baseManifest);
    const remote: RemoteOAuthClient = {
      id: "1",
      client_id: "jnc_test",
      name: "my-service-web",
      redirect_uris: manifest.spec.redirect_uris,
      allowed_scopes: manifest.spec.allowed_scopes,
      grant_types: manifest.spec.grant_types,
      audience: "other-api",
      is_confidential: true,
    };
    expect(compareManifestToRemote(manifest, remote).length).toBeGreaterThan(0);
  });
});
