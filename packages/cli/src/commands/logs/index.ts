import { Command } from "commander";
import chalk from "chalk";
import ora from "ora";
import { get } from "../../client.js";
import { output, type ColumnDef, type OutputFormat } from "../../utils/output.js";
import { handleError } from "../../utils/errors.js";

interface AuditLog {
  id: string;
  action: string;
  actor_email?: string;
  actor_id?: string;
  resource_type?: string;
  resource_id?: string;
  ip_address?: string;
  details?: Record<string, unknown>;
  created_at: string;
}

interface LogsListResponse {
  logs: AuditLog[];
  total: number;
  page: number;
  per_page: number;
}

const LOG_COLUMNS: ColumnDef[] = [
  { key: "created_at", header: "Timestamp", width: 22 },
  { key: "action", header: "Action", width: 25 },
  { key: "actor_email", header: "Actor", width: 28 },
  { key: "resource_type", header: "Resource", width: 15 },
  { key: "resource_id", header: "Resource ID", width: 38 },
  { key: "ip_address", header: "IP", width: 16 },
];

export function registerLogCommands(program: Command): void {
  const logs = program.command("logs").description("Audit log commands");

  logs
    .command("list")
    .description("List audit logs")
    .option("-p, --page <page>", "Page number", "1")
    .option("-l, --limit <limit>", "Results per page", "20")
    .option("-a, --action <action>", "Filter by action type")
    .option("-u, --user <userId>", "Filter by actor user ID")
    .option("--from <date>", "Start date (ISO 8601)")
    .option("--to <date>", "End date (ISO 8601)")
    .action(
      async (options: {
        page: string;
        limit: string;
        action?: string;
        user?: string;
        from?: string;
        to?: string;
      }) => {
        try {
          const spinner = ora("Fetching audit logs...").start();

          const params = new URLSearchParams({
            page: options.page,
            per_page: options.limit,
          });
          if (options.action) params.set("action", options.action);
          if (options.user) params.set("actor_id", options.user);
          if (options.from) params.set("from_date", options.from);
          if (options.to) params.set("to_date", options.to);

          const { data } = await get<LogsListResponse>(
            `/api/v1/admin/activity-logs?${params.toString()}`
          );
          spinner.stop();

          const format = (program.opts() as { format: OutputFormat }).format || "table";

          if (format === "table") {
            console.log(
              chalk.dim(
                `Showing ${data.logs.length} of ${data.total} log entries (page ${data.page})`
              )
            );
          }

          output(data.logs, format, LOG_COLUMNS);
        } catch (error) {
          handleError(error);
        }
      }
    );
}
