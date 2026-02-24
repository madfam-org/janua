import { Command } from "commander";
import chalk from "chalk";
import ora from "ora";
import { get, post } from "../../client.js";
import { output, outputSingle, type ColumnDef, type OutputFormat } from "../../utils/output.js";
import { promptOAuthClient, promptConfirm } from "../../utils/prompts.js";
import { handleError } from "../../utils/errors.js";

interface OAuthClient {
  id: string;
  client_id: string;
  client_secret?: string;
  name: string;
  redirect_uris: string[];
  grant_types: string[];
  is_active?: boolean;
  created_at?: string;
}

interface ClientsListResponse {
  clients: OAuthClient[];
  total: number;
}

interface RotateSecretResponse {
  client_id: string;
  client_secret: string;
}

const CLIENT_COLUMNS: ColumnDef[] = [
  { key: "client_id", header: "Client ID", width: 38 },
  { key: "name", header: "Name", width: 25 },
  {
    key: "grant_types",
    header: "Grant Types",
    width: 30,
    formatter: (v) => (Array.isArray(v) ? (v as string[]).join(", ") : String(v || "-")),
  },
  {
    key: "is_active",
    header: "Active",
    width: 8,
    formatter: (v) => (v ? chalk.green("Yes") : chalk.red("No")),
  },
];

export function registerAppCommands(program: Command): void {
  const apps = program
    .command("apps")
    .description("OAuth client application commands");

  apps
    .command("list")
    .description("List OAuth clients")
    .action(async () => {
      try {
        const spinner = ora("Fetching OAuth clients...").start();
        const { data } = await get<ClientsListResponse>(
          "/api/v1/oauth/clients"
        );
        spinner.stop();

        const format = (program.opts() as { format: OutputFormat }).format || "table";

        if (format === "table") {
          console.log(chalk.dim(`${data.clients.length} OAuth clients`));
        }

        output(data.clients, format, CLIENT_COLUMNS);
      } catch (error) {
        handleError(error);
      }
    });

  apps
    .command("create")
    .description("Create a new OAuth client")
    .action(async () => {
      try {
        const clientData = await promptOAuthClient();

        const spinner = ora("Creating OAuth client...").start();
        const { data } = await post<OAuthClient>(
          "/api/v1/oauth/clients",
          clientData
        );
        spinner.succeed(chalk.green(`OAuth client "${data.name}" created.`));

        console.log("");
        console.log(chalk.bold("Client Credentials"));
        console.log(`  Client ID:     ${data.client_id}`);
        if (data.client_secret) {
          console.log(`  Client Secret: ${chalk.yellow(data.client_secret)}`);
          console.log("");
          console.log(
            chalk.dim(
              "Save the client secret now. It will not be shown again."
            )
          );
        }
        console.log("");

        const format = (program.opts() as { format: OutputFormat }).format || "table";
        if (format !== "table") {
          outputSingle(data as unknown as Record<string, unknown>, format);
        }
      } catch (error) {
        handleError(error);
      }
    });

  apps
    .command("get")
    .description("Get OAuth client details")
    .argument("<id>", "Client ID")
    .action(async (id: string) => {
      try {
        const spinner = ora("Fetching OAuth client...").start();
        const { data } = await get<OAuthClient>(
          `/api/v1/oauth/clients/${id}`
        );
        spinner.stop();

        const format = (program.opts() as { format: OutputFormat }).format || "table";
        outputSingle(data as unknown as Record<string, unknown>, format);
      } catch (error) {
        handleError(error);
      }
    });

  apps
    .command("rotate-secret")
    .description("Rotate an OAuth client secret")
    .argument("<id>", "Client ID")
    .action(async (id: string) => {
      try {
        const confirmed = await promptConfirm(
          "Rotating the client secret will invalidate the current one. Continue?"
        );

        if (!confirmed) {
          console.log(chalk.dim("Cancelled."));
          return;
        }

        const spinner = ora("Rotating client secret...").start();
        const { data } = await post<RotateSecretResponse>(
          `/api/v1/oauth/clients/${id}/rotate`
        );
        spinner.succeed(chalk.green("Client secret rotated."));

        console.log("");
        console.log(`  Client ID:     ${data.client_id}`);
        console.log(`  New Secret:    ${chalk.yellow(data.client_secret)}`);
        console.log("");
        console.log(
          chalk.dim("Save the new client secret now. It will not be shown again.")
        );
      } catch (error) {
        handleError(error);
      }
    });
}
