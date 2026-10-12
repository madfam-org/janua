// Outbound and cross-surface links used by the marketing CTAs.
//
// Each target was checked live on 2026-10-11 (money-engine journeys J1 F7):
//   - demo.janua.dev has no DNS; the working auth playground is janua.dev/demo
//     (app/demo in this app), so the demo CTA stays on-site.
//   - docs.janua.dev has no self-hosting page (/self-hosting is a 404); the
//     self-hosting guide is the README's "Self-hosting (Production)" section.
//   - The GitHub org is madfam-org; github.com/madfam-io/* only answers through
//     a rename redirect.
export const GITHUB_REPO_URL = 'https://github.com/madfam-org/janua'

export const SITE_LINKS = {
  demo: '/demo',
  docs: 'https://docs.janua.dev',
  selfHosting: `${GITHUB_REPO_URL}#self-hosting-production`,
  github: GITHUB_REPO_URL,
  githubIssues: `${GITHUB_REPO_URL}/issues`,
  githubNewIssue: `${GITHUB_REPO_URL}/issues/new`,
} as const
