import chalk from "chalk";

export function handleError(error: unknown): never {
  if (error instanceof Error) {
    const message = error.message;

    if (
      message.includes("ECONNREFUSED") ||
      message.includes("fetch failed")
    ) {
      console.error(
        chalk.red("Connection refused. Is the Janua API running?")
      );
      console.error(
        chalk.dim("Start the API with: uvicorn app.main:app --port 4100")
      );
      process.exit(1);
    }

    if (
      message.includes("AUTHENTICATION_ERROR") ||
      message.includes("TOKEN_ERROR") ||
      message.includes("Not authenticated")
    ) {
      console.error(chalk.red("Authentication failed. Please log in again."));
      console.error(chalk.dim("Run: janua auth login"));
      process.exit(1);
    }

    if (
      message.includes("AUTHORIZATION_ERROR") ||
      message.includes("Permission denied") ||
      message.includes("Forbidden")
    ) {
      console.error(
        chalk.red("Permission denied. You do not have access to this resource.")
      );
      process.exit(1);
    }

    if (message.includes("RATE_LIMIT_ERROR")) {
      console.error(
        chalk.red("Rate limit exceeded. Please wait and try again.")
      );
      process.exit(1);
    }

    if (message.includes("NOT_FOUND_ERROR") || message.includes("Not found")) {
      console.error(chalk.red("Resource not found."));
      process.exit(1);
    }

    if (message.includes("VALIDATION_ERROR")) {
      console.error(chalk.red(`Validation error: ${message}`));
      process.exit(1);
    }

    console.error(chalk.red(`Error: ${message}`));
  } else {
    console.error(chalk.red("An unexpected error occurred."));
  }

  process.exit(1);
}
