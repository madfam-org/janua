import { Command } from "commander";
import chalk from "chalk";
import ora from "ora";
import { get, post } from "../../client.js";
import { output, outputSingle, type ColumnDef, type OutputFormat } from "../../utils/output.js";
import { promptWebhook } from "../../utils/prompts.js";
import { handleError } from "../../utils/errors.js";

interface Webhook {
  id: string;
  url: string;
  events: string[];
  description?: string;
  is_active?: boolean;
  created_at?: string;
  last_triggered?: string;
}

interface WebhooksListResponse {
  webhooks: Webhook[];
  total: number;
}

interface WebhookTestResponse {
  success: boolean;
  status_code?: number;
  response_time_ms?: number;
  error?: string;
}

const WEBHOOK_COLUMNS: ColumnDef[] = [
  { key: "id", header: "ID", width: 38 },
  { key: "url", header: "URL", width: 40 },
  {
    key: "events",
    header: "Events",
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

export function registerWebhookCommands(program: Command): void {
  const webhooks = program
    .command("webhooks")
    .description("Webhook management commands");

  webhooks
    .command("list")
    .description("List webhooks")
    .action(async () => {
      try {
        const spinner = ora("Fetching webhooks...").start();
        const { data } = await get<WebhooksListResponse>("/api/v1/webhooks");
        spinner.stop();

        const format = (program.opts() as { format: OutputFormat }).format || "table";

        if (format === "table") {
          console.log(chalk.dim(`${data.webhooks.length} webhooks`));
        }

        output(data.webhooks, format, WEBHOOK_COLUMNS);
      } catch (error) {
        handleError(error);
      }
    });

  webhooks
    .command("create")
    .description("Create a new webhook")
    .action(async () => {
      try {
        const webhookData = await promptWebhook();

        const spinner = ora("Creating webhook...").start();
        const { data } = await post<Webhook>("/api/v1/webhooks", webhookData);
        spinner.succeed(chalk.green("Webhook created."));

        const format = (program.opts() as { format: OutputFormat }).format || "table";
        outputSingle(data as unknown as Record<string, unknown>, format);
      } catch (error) {
        handleError(error);
      }
    });

  webhooks
    .command("test")
    .description("Test a webhook by sending a test event")
    .argument("<id>", "Webhook ID")
    .action(async (id: string) => {
      try {
        const spinner = ora("Sending test event...").start();
        const { data } = await post<WebhookTestResponse>(
          `/api/v1/webhooks/${id}/test`
        );
        spinner.stop();

        if (data.success) {
          console.log(chalk.green("Webhook test succeeded."));
          if (data.status_code) {
            console.log(`  Status code:    ${data.status_code}`);
          }
          if (data.response_time_ms) {
            console.log(`  Response time:  ${data.response_time_ms}ms`);
          }
        } else {
          console.log(chalk.red("Webhook test failed."));
          if (data.error) {
            console.log(`  Error: ${data.error}`);
          }
          if (data.status_code) {
            console.log(`  Status code: ${data.status_code}`);
          }
        }
      } catch (error) {
        handleError(error);
      }
    });
}
