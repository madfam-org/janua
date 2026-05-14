# Private Package Resolution Policy

Janua uses two dependency-resolution modes. Choose the mode based on whether
the dependent package is part of the current pnpm workspace.

## Same-workspace packages

Packages under the root workspace (`apps/*` and `packages/*`) must depend on
other Janua workspace packages with pnpm workspace protocol:

```json
{
  "@janua/typescript-sdk": "workspace:^",
  "@janua/ui": "workspace:^"
}
```

This keeps local development and CI deterministic: tests exercise the package
currently checked out in the monorepo instead of a previously published build.

Before publishing, verify package output with `pnpm pack` or the release job.
Published packages must not leak `workspace:` references.

## Standalone consumers

Examples, external repos, smoke-test apps, and deployed consumers that are not
members of the Janua root workspace must use normal semver ranges:

```json
{
  "@janua/typescript-sdk": "^0.1.4"
}
```

Those consumers resolve private packages through MADFAM's npm registry:

```ini
@janua:registry=https://npm.madfam.io/
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

CI environments that install standalone consumers must provide
`NPM_MADFAM_TOKEN`. Workspace-only CI jobs should not need registry access for
local Janua package edges.
