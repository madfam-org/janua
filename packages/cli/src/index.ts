#!/usr/bin/env node

import { Command } from "commander";
import chalk from "chalk";
import { registerAuthCommands } from "./commands/auth/index.js";
import { registerUserCommands } from "./commands/users/index.js";
import { registerOrgCommands } from "./commands/orgs/index.js";
import { registerAppCommands } from "./commands/apps/index.js";
import { registerWebhookCommands } from "./commands/webhooks/index.js";
import { registerLogCommands } from "./commands/logs/index.js";
import { registerConfigCommands } from "./commands/config/index.js";
import { setConfig } from "./config.js";

const program = new Command();

program
  .name("janua")
  .description("Janua Authentication CLI - manage your self-hosted auth platform")
  .version("0.1.0")
  .option(
    "--format <format>",
    "Output format: table, json, yaml",
    "table"
  )
  .option("--api-url <url>", "Override the API base URL")
  .hook("preAction", (thisCommand) => {
    const opts = thisCommand.opts() as { apiUrl?: string; format?: string };

    if (opts.apiUrl) {
      setConfig({ apiUrl: opts.apiUrl });
    }

    const format = opts.format;
    if (format && !["table", "json", "yaml"].includes(format)) {
      console.error(
        chalk.red(`Invalid format "${format}". Use: table, json, yaml`)
      );
      process.exit(1);
    }
  });

registerConfigCommands(program);
registerAuthCommands(program);
registerUserCommands(program);
registerOrgCommands(program);
registerAppCommands(program);
registerWebhookCommands(program);
registerLogCommands(program);

program
  .command("whoami")
  .description("Show current user and API URL")
  .action(async () => {
    const { getConfig, isAuthenticated } = await import("./config.js");
    const config = getConfig();
    console.log(chalk.bold("Janua CLI"));
    console.log(`  API URL:  ${config.apiUrl}`);
    console.log(
      `  Email:    ${config.email || chalk.dim("not authenticated")}`
    );
    console.log(
      `  Auth:     ${isAuthenticated() ? chalk.green("valid") : chalk.yellow("expired or not set")}`
    );
  });

program.addHelpText(
  "after",
  `
${chalk.bold("Examples:")}
  ${chalk.dim("$ janua config init              # Setup wizard")}
  ${chalk.dim("$ janua auth login               # Log in")}
  ${chalk.dim("$ janua users list               # List all users")}
  ${chalk.dim("$ janua orgs list --format json   # List orgs as JSON")}
  ${chalk.dim("$ janua apps create              # Create OAuth client")}
  ${chalk.dim("$ janua logs list --action login  # Filter audit logs")}

${chalk.bold("Documentation:")}
  ${chalk.dim("https://docs.janua.dev/cli")}
`
);

program.parse();
