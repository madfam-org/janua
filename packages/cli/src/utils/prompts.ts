import inquirer from "inquirer";

export async function promptLogin(): Promise<{
  email: string;
  password: string;
}> {
  const answers = await inquirer.prompt([
    {
      type: "input",
      name: "email",
      message: "Email:",
      validate: (input: string) => {
        if (!input.trim()) return "Email is required";
        if (!input.includes("@")) return "Please enter a valid email address";
        return true;
      },
    },
    {
      type: "password",
      name: "password",
      message: "Password:",
      mask: "*",
      validate: (input: string) => {
        if (!input) return "Password is required";
        return true;
      },
    },
  ]);
  return answers as { email: string; password: string };
}

export async function promptConfirm(message: string): Promise<boolean> {
  const { confirmed } = (await inquirer.prompt([
    {
      type: "confirm",
      name: "confirmed",
      message,
      default: false,
    },
  ])) as { confirmed: boolean };
  return confirmed;
}

export async function promptApiUrl(): Promise<string> {
  const { apiUrl } = (await inquirer.prompt([
    {
      type: "input",
      name: "apiUrl",
      message: "Janua API URL:",
      default: "http://localhost:4100",
      validate: (input: string) => {
        try {
          new URL(input);
          return true;
        } catch {
          return "Please enter a valid URL (e.g., http://localhost:4100)";
        }
      },
    },
  ])) as { apiUrl: string };
  return apiUrl.replace(/\/$/, "");
}

export async function promptOAuthClient(): Promise<{
  name: string;
  redirect_uris: string[];
  grant_types: string[];
}> {
  const answers = await inquirer.prompt([
    {
      type: "input",
      name: "name",
      message: "Client name:",
      validate: (input: string) =>
        input.trim() ? true : "Client name is required",
    },
    {
      type: "input",
      name: "redirect_uris",
      message: "Redirect URIs (comma-separated):",
      validate: (input: string) =>
        input.trim() ? true : "At least one redirect URI is required",
      filter: (input: string) =>
        input.split(",").map((uri: string) => uri.trim()),
    },
    {
      type: "checkbox",
      name: "grant_types",
      message: "Grant types:",
      choices: [
        { name: "Authorization Code", value: "authorization_code", checked: true },
        { name: "Client Credentials", value: "client_credentials" },
        { name: "Refresh Token", value: "refresh_token", checked: true },
        { name: "Implicit", value: "implicit" },
      ],
      validate: (input: string[]) =>
        input.length > 0 ? true : "Select at least one grant type",
    },
  ]);
  return answers as {
    name: string;
    redirect_uris: string[];
    grant_types: string[];
  };
}

export async function promptWebhook(): Promise<{
  url: string;
  events: string[];
  description: string;
}> {
  const answers = await inquirer.prompt([
    {
      type: "input",
      name: "url",
      message: "Webhook URL:",
      validate: (input: string) => {
        try {
          new URL(input);
          return true;
        } catch {
          return "Please enter a valid URL";
        }
      },
    },
    {
      type: "checkbox",
      name: "events",
      message: "Events to subscribe to:",
      choices: [
        { name: "user.created", value: "user.created", checked: true },
        { name: "user.updated", value: "user.updated" },
        { name: "user.deleted", value: "user.deleted" },
        { name: "user.login", value: "user.login" },
        { name: "user.logout", value: "user.logout" },
        { name: "org.created", value: "org.created" },
        { name: "org.updated", value: "org.updated" },
        { name: "org.member.added", value: "org.member.added" },
        { name: "org.member.removed", value: "org.member.removed" },
      ],
      validate: (input: string[]) =>
        input.length > 0 ? true : "Select at least one event",
    },
    {
      type: "input",
      name: "description",
      message: "Description (optional):",
      default: "",
    },
  ]);
  return answers as { url: string; events: string[]; description: string };
}
