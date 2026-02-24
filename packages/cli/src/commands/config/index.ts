import { Command } from "commander";
import chalk from "chalk";
import ora from "ora";
import { setConfig, getConfig } from "../../config.js";
import { promptApiUrl, promptLogin } from "../../utils/prompts.js";
import { post } from "../../client.js";
import { handleError } from "../../utils/errors.js";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export function registerConfigCommands(program: Command): void {
  const config = program
    .command("config")
    .description("CLI configuration commands");

  config
    .command("init")
    .description("Interactive setup wizard")
    .action(async () => {
      try {
        console.log(chalk.bold("Janua CLI Setup"));
        console.log("");

        const apiUrl = await promptApiUrl();
        setConfig({ apiUrl });
        console.log(chalk.green(`API URL set to ${apiUrl}`));

        console.log("");
        console.log("Verifying API connection...");

        const spinner = ora("Connecting to API...").start();
        try {
          const response = await fetch(`${apiUrl}/health`);
          if (response.ok) {
            spinner.succeed(chalk.green("API is reachable."));
          } else {
            spinner.warn(
              chalk.yellow(
                `API responded with status ${response.status}. Continuing anyway.`
              )
            );
          }
        } catch {
          spinner.warn(
            chalk.yellow(
              "Could not reach API. You can still configure credentials."
            )
          );
        }

        console.log("");
        console.log("Now log in to authenticate the CLI.");
        console.log("");

        const { email, password } = await promptLogin();
        const loginSpinner = ora("Authenticating...").start();

        const { data } = await post<LoginResponse>(
          "/api/v1/auth/login",
          { email, password },
          apiUrl
        );

        setConfig({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          email,
        });

        loginSpinner.succeed(chalk.green(`Authenticated as ${email}`));

        console.log("");
        console.log(chalk.bold("Setup complete."));
        console.log(chalk.dim("Configuration saved to ~/.config/janua/"));
        console.log("");
        console.log("Try these commands:");
        console.log(chalk.dim("  janua auth status     - Check authentication"));
        console.log(chalk.dim("  janua users list      - List users"));
        console.log(chalk.dim("  janua orgs list       - List organizations"));
      } catch (error) {
        handleError(error);
      }
    });

  config
    .command("show")
    .description("Show current configuration")
    .action(() => {
      const cfg = getConfig();
      console.log(chalk.bold("Current Configuration"));
      console.log("");
      console.log(`  API URL:    ${cfg.apiUrl}`);
      console.log(`  Email:      ${cfg.email || chalk.dim("not set")}`);
      console.log(
        `  Token:      ${cfg.accessToken ? chalk.green("stored") : chalk.dim("not set")}`
      );
      console.log(
        `  Refresh:    ${cfg.refreshToken ? chalk.green("stored") : chalk.dim("not set")}`
      );
    });

  config
    .command("set")
    .description("Set a configuration value")
    .argument("<key>", "Configuration key (apiUrl)")
    .argument("<value>", "Configuration value")
    .action((key: string, value: string) => {
      const allowedKeys = ["apiUrl"];
      if (!allowedKeys.includes(key)) {
        console.error(
          chalk.red(
            `Invalid key "${key}". Allowed keys: ${allowedKeys.join(", ")}`
          )
        );
        process.exit(1);
      }

      setConfig({ [key]: value });
      console.log(chalk.green(`${key} set to ${value}`));
    });

  config
    .command("reset")
    .description("Reset all configuration to defaults")
    .action(() => {
      setConfig({
        apiUrl: "http://localhost:4100",
        accessToken: "",
        refreshToken: "",
        email: "",
      });
      console.log(chalk.green("Configuration reset to defaults."));
    });
}
