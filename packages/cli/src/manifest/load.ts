import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import {
  multiClientManifestSchema,
  oauthClientManifestSchema,
  type OAuthClientManifest,
} from "./schema.js";

export function loadManifests(filePath: string): OAuthClientManifest[] {
  const resolved = path.resolve(filePath);
  if (!fs.existsSync(resolved)) {
    throw new Error(`Manifest not found: ${resolved}`);
  }

  const raw = fs.readFileSync(resolved, "utf8");
  const parsed = yaml.load(raw);

  if (!parsed || typeof parsed !== "object") {
    throw new Error("Manifest must be a YAML object");
  }

  const doc = parsed as Record<string, unknown>;
  if (doc.kind === "OAuthClientList") {
    const list = multiClientManifestSchema.parse(doc);
    return list.clients;
  }

  return [oauthClientManifestSchema.parse(doc)];
}
