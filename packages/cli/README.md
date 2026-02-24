# @janua/cli

> Command-line interface for the Janua authentication platform

**Version:** 0.1.0 | **Language:** TypeScript | **Status:** Development

## Overview

The Janua CLI provides command-line access to the Janua authentication platform for managing users, organizations, OAuth clients, webhooks, and audit logs. Built with Commander.js for a familiar CLI experience.

## Installation

```bash
# Install globally from npm
npm install -g @janua/cli

# Or from the monorepo
cd packages/cli
pnpm install
pnpm build
npm link
```

## Quick Start

```bash
# Interactive setup wizard
janua config init

# Authenticate
janua auth login

# Check connection
janua auth status

# List users
janua users list
```

## Commands

### Configuration

```bash
janua config init          # Interactive setup (API URL, login)
janua config show          # Show current configuration
janua config set <k> <v>   # Set a config value
janua config reset          # Reset to defaults
```

### Authentication

```bash
janua auth login           # Authenticate and store token
janua auth logout          # Clear stored credentials
janua auth status          # Show current auth state
janua auth token           # Print current access token
```

### Users

```bash
janua users list                    # List all users
janua users list --status active    # Filter by status
janua users list --limit 50         # Control page size
janua users get <user-id>           # Get user details
janua users update <user-id> --status suspended   # Update user
```

### Organizations

```bash
janua orgs list                     # List organizations
janua orgs get <org-id>             # Get org details
janua orgs members <org-id>         # List org members
```

### OAuth Applications

```bash
janua apps list                     # List OAuth clients
janua apps create                   # Interactive client creation
janua apps get <client-id>          # Get client details
janua apps rotate-secret <id>       # Rotate client secret
```

### Webhooks

```bash
janua webhooks list                 # List webhook endpoints
janua webhooks create               # Interactive webhook creation
janua webhooks test <id>            # Send test event
```

### Audit Logs

```bash
janua logs list                     # List recent audit events
janua logs list --action login      # Filter by action
janua logs list --user <email>      # Filter by user
janua logs list --limit 100         # Control page size
```

## Output Formats

All commands support multiple output formats:

```bash
janua users list                    # Default: table format
janua users list --format json      # JSON output
janua users list --format yaml      # YAML output
```

## Configuration

Configuration is stored at `~/.config/janua/config.json`:

```json
{
  "apiUrl": "https://api.janua.dev",
  "token": "...",
  "defaultFormat": "table"
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JANUA_API_URL` | API base URL | `https://api.janua.dev` |
| `JANUA_TOKEN` | Access token (overrides stored) | - |
| `JANUA_FORMAT` | Default output format | `table` |

## Development

```bash
cd packages/cli

# Install dependencies
pnpm install

# Build
pnpm build

# Run in dev mode (watch)
pnpm dev

# Type check
pnpm typecheck

# Run locally without installing
node dist/index.js users list
```

## Architecture

```
packages/cli/
├── src/
│   ├── index.ts              # Entry point, command registration
│   ├── config.ts             # Persistent config (~/.config/janua/)
│   ├── client.ts             # HTTP client with auth headers
│   ├── commands/
│   │   ├── auth/index.ts     # login, logout, status, token
│   │   ├── users/index.ts    # list, get, update
│   │   ├── orgs/index.ts     # list, get, members
│   │   ├── apps/index.ts     # list, create, get, rotate-secret
│   │   ├── config/index.ts   # init, show, set, reset
│   │   ├── webhooks/index.ts # list, create, test
│   │   └── logs/index.ts     # list (with filters)
│   └── utils/
│       ├── output.ts         # Table/JSON/YAML formatters
│       ├── prompts.ts        # Interactive prompts (inquirer)
│       └── errors.ts         # Error categorization & display
├── package.json
└── tsconfig.json
```

## License

Part of the Janua platform. See [LICENSE](../../LICENSE) for details.
