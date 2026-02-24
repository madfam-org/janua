import { Command } from "commander";
import chalk from "chalk";
import ora from "ora";
import { get, patch } from "../../client.js";
import { output, outputSingle, type ColumnDef, type OutputFormat } from "../../utils/output.js";
import { handleError } from "../../utils/errors.js";

interface User {
  id: string;
  email: string;
  full_name?: string;
  is_admin?: boolean;
  is_active?: boolean;
  email_verified?: boolean;
  created_at?: string;
  last_login?: string;
}

interface UsersListResponse {
  users: User[];
  total: number;
  page: number;
  per_page: number;
}

const USER_COLUMNS: ColumnDef[] = [
  { key: "id", header: "ID", width: 38 },
  { key: "email", header: "Email", width: 30 },
  { key: "full_name", header: "Name", width: 20 },
  {
    key: "is_active",
    header: "Active",
    width: 8,
    formatter: (v) => (v ? chalk.green("Yes") : chalk.red("No")),
  },
  {
    key: "is_admin",
    header: "Admin",
    width: 8,
    formatter: (v) => (v ? chalk.cyan("Yes") : "No"),
  },
  {
    key: "email_verified",
    header: "Verified",
    width: 10,
    formatter: (v) => (v ? chalk.green("Yes") : chalk.yellow("No")),
  },
];

export function registerUserCommands(program: Command): void {
  const users = program.command("users").description("User management commands");

  users
    .command("list")
    .description("List all users")
    .option("-p, --page <page>", "Page number", "1")
    .option("-l, --limit <limit>", "Results per page", "20")
    .option("-s, --search <query>", "Search by email or name")
    .action(async (options: { page: string; limit: string; search?: string }) => {
      try {
        const spinner = ora("Fetching users...").start();

        let path = `/api/v1/admin/users?page=${options.page}&per_page=${options.limit}`;
        if (options.search) {
          path += `&search=${encodeURIComponent(options.search)}`;
        }

        const { data } = await get<UsersListResponse>(path);
        spinner.stop();

        const format = (program.opts() as { format: OutputFormat }).format || "table";

        if (format === "table") {
          console.log(
            chalk.dim(
              `Showing ${data.users.length} of ${data.total} users (page ${data.page})`
            )
          );
        }

        output(data.users, format, USER_COLUMNS);
      } catch (error) {
        handleError(error);
      }
    });

  users
    .command("get")
    .description("Get user details")
    .argument("<id>", "User ID")
    .action(async (id: string) => {
      try {
        const spinner = ora("Fetching user...").start();
        const { data } = await get<User>(`/api/v1/users/${id}`);
        spinner.stop();

        const format = (program.opts() as { format: OutputFormat }).format || "table";
        outputSingle(data as unknown as Record<string, unknown>, format);
      } catch (error) {
        handleError(error);
      }
    });

  users
    .command("update")
    .description("Update a user")
    .argument("<id>", "User ID")
    .option("--name <name>", "Full name")
    .option("--active <active>", "Active status (true/false)")
    .option("--admin <admin>", "Admin status (true/false)")
    .action(
      async (
        id: string,
        options: { name?: string; active?: string; admin?: string }
      ) => {
        try {
          const body: Record<string, unknown> = {};
          if (options.name !== undefined) body.full_name = options.name;
          if (options.active !== undefined)
            body.is_active = options.active === "true";
          if (options.admin !== undefined)
            body.is_admin = options.admin === "true";

          if (Object.keys(body).length === 0) {
            console.error(
              chalk.yellow(
                "No update fields provided. Use --name, --active, or --admin."
              )
            );
            process.exit(1);
          }

          const spinner = ora("Updating user...").start();
          const { data } = await patch<User>(
            `/api/v1/admin/users/${id}`,
            body
          );
          spinner.stop();

          console.log(chalk.green(`User ${data.email} updated successfully.`));

          const format = (program.opts() as { format: OutputFormat }).format || "table";
          outputSingle(data as unknown as Record<string, unknown>, format);
        } catch (error) {
          handleError(error);
        }
      }
    );
}
