import { Command } from "commander";
import chalk from "chalk";
import fs from "node:fs";
import path from "node:path";
import ora from "ora";
import { provisionLookupByName, provisionRegister } from "../../provision-http.js";
import { loadManifests } from "../../manifest/load.js";
import {
  compareManifestToRemote,
  manifestToRegisterBody,
  type RemoteOAuthClient,
} from "../../manifest/schema.js";
import { handleError } from "../../utils/errors.js";
import { output, outputSingle, type OutputFormat } from "../../utils/output.js";

export interface ProvisionGlobalOptions {
  format?: OutputFormat;
  apiUrl?: string;
  internalApiKey?: string;
  manifest?: string;
  secretsFile?: string;
  quiet?: boolean;
}

function getFormat(program: Command): OutputFormat {
  return (program.opts() as { format?: OutputFormat }).format || "table";
}

function getProvisionOpts(program: Command): ProvisionGlobalOptions {
  return program.opts() as ProvisionGlobalOptions;
}

async function lookupRemote(
  name: string,
  opts: ProvisionGlobalOptions
): Promise<RemoteOAuthClient | null> {
  try {
    const { data } = await provisionLookupByName<RemoteOAuthClient>(
      name,
      opts.apiUrl,
      opts.internalApiKey
    );
    return data;
  } catch (error) {
    const status =
      typeof error === "object" &&
      error !== null &&
      "status" in error &&
      typeof (error as { status?: number }).status === "number"
        ? (error as { status: number }).status
        : undefined;
    if (status === 404) return null;
    const message = error instanceof Error ? error.message : String(error);
    if (message.toLowerCase().includes("not found")) return null;
    throw error;
  }
}

function writeSecretsFile(
  filePath: string,
  lines: Record<string, string>
): void {
  const resolved = path.resolve(filePath);
  const content =
    Object.entries(lines)
      .map(([key, value]) => `${key}=${value}`)
      .join("\n") + "\n";
  fs.writeFileSync(resolved, content, { mode: 0o600 });
}

function printProvisionResult(
  manifestPath: string,
  remote: RemoteOAuthClient,
  created: boolean,
  opts: ProvisionGlobalOptions
): void {
  if (opts.quiet) return;

  console.log("");
  console.log(chalk.bold(`Client: ${remote.name}`));
  console.log(`  Manifest:  ${manifestPath}`);
  console.log(`  Client ID: ${remote.client_id}`);
  if (created && remote.client_secret) {
    console.log(`  Secret:    ${chalk.yellow(remote.client_secret)}`);
    console.log(chalk.dim("  Save the client secret now — it is shown only once."));
  } else if (!created) {
    console.log(chalk.dim("  Secret:    (already provisioned — not available)"));
  }
  console.log("");
}

export function registerProvisionCommands(program: Command): void {
  const provision = program
    .command("provision")
    .description("Provision OAuth clients for consumer apps (CI/bootstrap)")
    .option(
      "-f, --manifest <path>",
      "Path to janua.client.yaml",
      "janua.client.yaml"
    )
    .option(
      "--internal-api-key <key>",
      "Internal API key (or JANUA_INTERNAL_API_KEY)"
    )
    .option("--secrets-file <path>", "Write credentials to a mode-0600 env file")
    .option("-q, --quiet", "Minimal output");

  provision
    .command("apply")
    .description("Register OAuth clients from manifest (idempotent)")
    .action(async function (this: Command) {
      const parent = this.parent;
      if (!parent) return;
      const opts = getProvisionOpts(parent);
      const format = getFormat(parent);

      try {
        const manifests = loadManifests(opts.manifest || "janua.client.yaml");
        let exitCode = 0;

        for (const manifest of manifests) {
          const spinner = ora(
            `Provisioning ${manifest.metadata.name}...`
          ).start();
          const body = manifestToRegisterBody(manifest);
          const response = await provisionRegister<RemoteOAuthClient>(
            body,
            opts.apiUrl,
            opts.internalApiKey
          );
          spinner.stop();

          const created = response.status === 201;
          const remote = response.data;
          printProvisionResult(opts.manifest || "janua.client.yaml", remote, created, opts);

          if (format !== "table") {
            outputSingle(
              { created, ...remote } as Record<string, unknown>,
              format
            );
          }

          if (opts.secretsFile) {
            const envLines: Record<string, string> = {
              JANUA_CLIENT_ID: remote.client_id,
            };
            if (remote.audience) envLines.JANUA_AUDIENCE = remote.audience;
            if (remote.client_secret) {
              envLines.JANUA_CLIENT_SECRET = remote.client_secret;
            }
            writeSecretsFile(opts.secretsFile, envLines);
            if (!opts.quiet) {
              console.log(chalk.dim(`Wrote env file: ${path.resolve(opts.secretsFile)}`));
            }
          }

          if (!created) {
            const drift = compareManifestToRemote(manifest, remote);
            if (drift.length > 0) {
              console.error(
                chalk.yellow(
                  `Warning: ${manifest.metadata.name} exists but drifts from manifest:`
                )
              );
              drift.forEach((line) => console.error(chalk.yellow(`  - ${line}`)));
              exitCode = 1;
            }
          }
        }

        if (exitCode !== 0) process.exit(exitCode);
      } catch (error) {
        handleError(error);
      }
    });

  provision
    .command("plan")
    .description("Show whether manifests would create or drift against Janua")
    .action(async function (this: Command) {
      const parent = this.parent;
      if (!parent) return;
      const opts = getProvisionOpts(parent);
      const format = getFormat(parent);

      try {
        const manifests = loadManifests(opts.manifest || "janua.client.yaml");
        const plans: Array<Record<string, unknown>> = [];
        let exitCode = 0;

        for (const manifest of manifests) {
          const remote = await lookupRemote(manifest.metadata.name, opts);
          if (!remote) {
            plans.push({
              name: manifest.metadata.name,
              action: "create",
            });
            if (!opts.quiet) {
              console.log(
                chalk.green(`+ ${manifest.metadata.name}: would create (not found)`)
              );
            }
            continue;
          }

          const drift = compareManifestToRemote(manifest, remote);
          if (drift.length === 0) {
            plans.push({
              name: manifest.metadata.name,
              action: "noop",
              client_id: remote.client_id,
            });
            if (!opts.quiet) {
              console.log(
                chalk.dim(`= ${manifest.metadata.name}: in sync (${remote.client_id})`)
              );
            }
          } else {
            exitCode = 1;
            plans.push({
              name: manifest.metadata.name,
              action: "drift",
              client_id: remote.client_id,
              drift,
            });
            if (!opts.quiet) {
              console.log(
                chalk.yellow(`! ${manifest.metadata.name}: drift (${remote.client_id})`)
              );
              drift.forEach((line) => console.log(chalk.yellow(`    ${line}`)));
            }
          }
        }

        if (format !== "table") {
          output(plans, format);
        }

        if (exitCode !== 0) process.exit(exitCode);
      } catch (error) {
        handleError(error);
      }
    });

  provision
    .command("verify")
    .description("Verify manifest matches provisioned OAuth client")
    .action(async function (this: Command) {
      const parent = this.parent;
      if (!parent) return;
      const opts = getProvisionOpts(parent);

      try {
        const manifests = loadManifests(opts.manifest || "janua.client.yaml");

        for (const manifest of manifests) {
          const remote = await lookupRemote(manifest.metadata.name, opts);
          if (!remote) {
            console.error(
              chalk.red(`Missing OAuth client: ${manifest.metadata.name}`)
            );
            process.exit(1);
          }

          const drift = compareManifestToRemote(manifest, remote);
          if (drift.length > 0) {
            console.error(
              chalk.red(`Drift detected for ${manifest.metadata.name}:`)
            );
            drift.forEach((line) => console.error(chalk.red(`  - ${line}`)));
            process.exit(1);
          }

          if (!opts.quiet) {
            console.log(
              chalk.green(
                `OK ${manifest.metadata.name} (${remote.client_id}) matches manifest`
              )
            );
          }
        }
      } catch (error) {
        handleError(error);
      }
    });

  provision
    .command("export-env")
    .description("Print shell exports for provisioned client (no secret on idempotent clients)")
    .action(async function (this: Command) {
      const parent = this.parent;
      if (!parent) return;
      const opts = getProvisionOpts(parent);

      try {
        const manifests = loadManifests(opts.manifest || "janua.client.yaml");
        const apiUrl = opts.apiUrl || process.env.JANUA_API_URL || "https://api.janua.dev";

        for (const manifest of manifests) {
          const remote = await lookupRemote(manifest.metadata.name, opts);
          if (!remote) {
            console.error(
              chalk.red(
                `Client not provisioned: ${manifest.metadata.name}. Run: janua provision apply`
              )
            );
            process.exit(1);
          }

          const lines = [
            `JANUA_CLIENT_ID=${remote.client_id}`,
            `JANUA_ISSUER_URL=${apiUrl}`,
          ];
          if (remote.audience) lines.push(`JANUA_AUDIENCE=${remote.audience}`);
          if (remote.client_secret) {
            lines.push(`JANUA_CLIENT_SECRET=${remote.client_secret}`);
          }

          console.log(lines.join("\n"));
        }
      } catch (error) {
        handleError(error);
      }
    });
}
