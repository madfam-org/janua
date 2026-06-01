# Janua Public Repo Sanitization Owner Decision

Date: 2026-06-01
Current status: blocked, not sanitized

## Evidence summary

- Current-tree exact credential-signature paths: 0
- Git-history matched paths: 17
- GitHub Actions artifacts reported: 10921
- Releases page count: 1

## Required owner decisions

- Choose `history_rewrite` or `risk_acceptance_plus_revocation` for history matches.
- Choose `artifact_body_review`, `artifact_retention_cleanup`, or `artifact_risk_acceptance` for public artifacts.
- Confirm no real signing key, OAuth secret, webhook secret, database URL, redis URL, encryption key, tenant data, or privileged auth procedure exists in public source/history/artifacts.
- Approve or reject whether Janua can produce `PUBLIC_GITHUB_REPO_SANITIZED` Tulana evidence.

## Recommended decision

Keep status blocked. Prioritize artifact retention cleanup and targeted review because Janua has the largest artifact surface and identity blast radius.

## Artifact retention evidence update

Current-tree workflow audit found zero checked workflows using `actions/upload-artifact`, so no current workflow retention edit was applied in this pass. Existing GitHub artifact volume remains launch-blocking.

Full metadata-only artifact evidence for Janua is captured centrally in Tulana at `docs/evidence/public-github-artifact-full-metadata-dhanam-janua-2026-06-01.tsv`.

Owner still needs to choose artifact body review, artifact retention cleanup, or explicit time-bounded artifact risk acceptance.

## Full artifact metadata update

- Total artifacts: 10,921
- Active artifacts: 2,007
- Expired artifacts: 8,914
- Total artifact bytes: 4,456,118,936
- Risk-name artifacts: 7,419
- Active risk-name artifacts: 919
- Risk-name artifact bytes: 3,431,302,088

Owner review should start with active risk-name artifacts. Janua is the highest-risk repo in this pass by artifact count and risk-name volume.
