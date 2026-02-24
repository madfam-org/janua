import { Command } from "commander";
import chalk from "chalk";
import ora from "ora";
import { post, get } from "../../client.js";
import {
  setConfig,
  clearConfig,
  getConfig,
  isAuthenticated,
  getAccessToken,
  getTokenPayload,
} from "../../config.js";
import { promptLogin } from "../../utils/prompts.js";
import { handleError } from "../../utils/errors.js";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface UserResponse {
  id: string;
  email: string;
  full_name?: string;
  is_admin?: boolean;
  email_verified?: boolean;
  created_at?: string;
}

export function registerAuthCommands(program: Command): void {
  const auth = program.command("auth").description("Authentication commands");

  auth
    .command("login")
    .description("Authenticate with email and password")
    .action(async () => {
      try {
        const { email, password } = await promptLogin();
        const spinner = ora("Authenticating...").start();

        const { data } = await post<LoginResponse>("/api/v1/auth/login", {
          email,
          password,
        });

        setConfig({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          email,
        });

        spinner.succeed(chalk.green(`Authenticated as ${email}`));
      } catch (error) {
        handleError(error);
      }
    });

  auth
    .command("logout")
    .description("Clear stored authentication tokens")
    .action(() => {
      const config = getConfig();
      clearConfig();
      if (config.email) {
        console.log(chalk.green(`Logged out from ${config.email}`));
      } else {
        console.log(chalk.green("Logged out"));
      }
    });

  auth
    .command("status")
    .description("Show current authentication state")
    .action(async () => {
      try {
        const config = getConfig();

        if (!config.accessToken) {
          console.log(chalk.yellow("Not authenticated. Run: janua auth login"));
          return;
        }

        const authenticated = isAuthenticated();
        const payload = getTokenPayload();

        console.log(chalk.bold("Authentication Status"));
        console.log("");
        console.log(`  Email:          ${config.email || "unknown"}`);
        console.log(`  API URL:        ${config.apiUrl}`);
        console.log(
          `  Token valid:    ${authenticated ? chalk.green("Yes") : chalk.red("Expired")}`
        );

        if (payload) {
          if (payload.exp) {
            const expDate = new Date((payload.exp as number) * 1000);
            console.log(`  Expires:        ${expDate.toLocaleString()}`);
          }
          if (payload.sub) {
            console.log(`  User ID:        ${payload.sub}`);
          }
        }

        if (authenticated) {
          const spinner = ora("Fetching user info...").start();
          try {
            const { data } = await get<UserResponse>("/api/v1/auth/me");
            spinner.stop();
            console.log("");
            console.log(chalk.bold("User Info"));
            console.log(`  Name:           ${data.full_name || "-"}`);
            console.log(
              `  Admin:          ${data.is_admin ? chalk.cyan("Yes") : "No"}`
            );
            console.log(
              `  Email verified: ${data.email_verified ? chalk.green("Yes") : chalk.yellow("No")}`
            );
          } catch {
            spinner.stop();
          }
        }
      } catch (error) {
        handleError(error);
      }
    });

  auth
    .command("token")
    .description("Print current access token")
    .action(() => {
      const token = getAccessToken();
      if (!token) {
        console.error(
          chalk.yellow("Not authenticated. Run: janua auth login")
        );
        process.exit(1);
      }
      if (!isAuthenticated()) {
        console.error(
          chalk.yellow("Token expired. Run: janua auth login")
        );
        process.exit(1);
      }
      process.stdout.write(token);
    });
}
