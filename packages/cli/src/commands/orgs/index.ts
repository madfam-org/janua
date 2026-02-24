import { Command } from "commander";
import chalk from "chalk";
import ora from "ora";
import { get } from "../../client.js";
import { output, outputSingle, type ColumnDef, type OutputFormat } from "../../utils/output.js";
import { handleError } from "../../utils/errors.js";

interface Organization {
  id: string;
  name: string;
  slug?: string;
  description?: string;
  is_active?: boolean;
  member_count?: number;
  created_at?: string;
}

interface OrgMember {
  id: string;
  user_id: string;
  email: string;
  full_name?: string;
  role: string;
  joined_at?: string;
}

interface OrgsListResponse {
  organizations: Organization[];
  total: number;
}

interface MembersListResponse {
  members: OrgMember[];
  total: number;
}

const ORG_COLUMNS: ColumnDef[] = [
  { key: "id", header: "ID", width: 38 },
  { key: "name", header: "Name", width: 25 },
  { key: "slug", header: "Slug", width: 20 },
  { key: "member_count", header: "Members", width: 10 },
  {
    key: "is_active",
    header: "Active",
    width: 8,
    formatter: (v) => (v ? chalk.green("Yes") : chalk.red("No")),
  },
];

const MEMBER_COLUMNS: ColumnDef[] = [
  { key: "user_id", header: "User ID", width: 38 },
  { key: "email", header: "Email", width: 30 },
  { key: "full_name", header: "Name", width: 20 },
  { key: "role", header: "Role", width: 15 },
  { key: "joined_at", header: "Joined", width: 22 },
];

export function registerOrgCommands(program: Command): void {
  const orgs = program
    .command("orgs")
    .description("Organization management commands");

  orgs
    .command("list")
    .description("List organizations")
    .option("-p, --page <page>", "Page number", "1")
    .option("-l, --limit <limit>", "Results per page", "20")
    .action(async (options: { page: string; limit: string }) => {
      try {
        const spinner = ora("Fetching organizations...").start();
        const { data } = await get<OrgsListResponse>(
          `/api/v1/organizations?page=${options.page}&per_page=${options.limit}`
        );
        spinner.stop();

        const format = (program.opts() as { format: OutputFormat }).format || "table";

        if (format === "table") {
          console.log(
            chalk.dim(`Showing ${data.organizations.length} of ${data.total} organizations`)
          );
        }

        output(data.organizations, format, ORG_COLUMNS);
      } catch (error) {
        handleError(error);
      }
    });

  orgs
    .command("get")
    .description("Get organization details")
    .argument("<id>", "Organization ID")
    .action(async (id: string) => {
      try {
        const spinner = ora("Fetching organization...").start();
        const { data } = await get<Organization>(
          `/api/v1/organizations/${id}`
        );
        spinner.stop();

        const format = (program.opts() as { format: OutputFormat }).format || "table";
        outputSingle(data as unknown as Record<string, unknown>, format);
      } catch (error) {
        handleError(error);
      }
    });

  orgs
    .command("members")
    .description("List organization members")
    .argument("<id>", "Organization ID")
    .option("-p, --page <page>", "Page number", "1")
    .option("-l, --limit <limit>", "Results per page", "20")
    .action(async (id: string, options: { page: string; limit: string }) => {
      try {
        const spinner = ora("Fetching members...").start();
        const { data } = await get<MembersListResponse>(
          `/api/v1/organizations/${id}/members?page=${options.page}&per_page=${options.limit}`
        );
        spinner.stop();

        const format = (program.opts() as { format: OutputFormat }).format || "table";

        if (format === "table") {
          console.log(
            chalk.dim(`Showing ${data.members.length} of ${data.total} members`)
          );
        }

        output(data.members, format, MEMBER_COLUMNS);
      } catch (error) {
        handleError(error);
      }
    });
}
