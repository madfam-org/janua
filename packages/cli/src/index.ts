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
import { registerProvisionCommands } from "./commands/provision/index.js";
import { setConfig } from "./config.js";

const program = new Command();

program
  .name("janua")
  .description(
    "Janua CLI — provision OAuth clients for consumer apps and administer the platform"
  )
  .version("0.2.0")
  .option("--format <format>", "Output format: table, json, yaml", "table")
  .option("--api-url <url>", "Override the API base URL (JANUA_API_URL)")
  .hook("preAction", (thisCommand) => {
    const opts = thisCommand.opts() as { apiUrl?: string; format?: string };

    if (opts.apiUrl) {
      setConfig({ apiUrl: opts.apiUrl.replace(/\/$/, "") });
    }

    const format = opts.format;
    if (format && !["table", "json", "yaml"].includes(format)) {
      console.error(
        chalk.red(`Invalid format "${format}". Use: table, json, yaml`)
      );
      process.exit(1);
    }
  });

registerProvisionCommands(program);
registerConfigCommands(program);

const admin = program
  .command("admin")
  .description("Platform administration (requires login)");

registerAuthCommands(admin);
registerUserCommands(admin);
registerOrgCommands(admin);

const adminClients = admin
  .command("clients")
  .description("OAuth client administration");
registerAppCommands(adminClients);

registerWebhookCommands(admin);
registerLogCommands(admin);

registerAuthCommands(program);
registerUserCommands(program);
registerOrgCommands(program);
registerAppCommands(program, { group: "apps" });
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
${chalk.bold("Consumer provisioning (CI):")}
  ${chalk.dim("$ janua provision apply -f janua.client.yaml")}
  ${chalk.dim("$ janua provision plan -f janua.client.yaml")}
  ${chalk.dim("$ janua provision verify -f janua.client.yaml")}

${chalk.bold("Administration:")}
  ${chalk.dim("$ janua admin auth login")}
  ${chalk.dim("$ janua admin clients list")}

${chalk.bold("Documentation:")}
  ${chalk.dim("https://docs.janua.dev/cli")}
`
);

program.parse();
