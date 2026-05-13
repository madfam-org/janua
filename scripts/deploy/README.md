# Janua Deployment Scripts

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


Scripts for building and deploying Janua services.

## build-and-push.sh

Local build and deployment script for development and manual deployments.

### Prerequisites

- Docker installed locally
- SSH access to `ssh.madfam.io`
- Docker registry running on server at `localhost:5000`

### Usage

```bash
# Build API image only
./build-and-push.sh api

# Build and push to server registry
./build-and-push.sh api --push

# Build, push, and deploy to K8s
./build-and-push.sh api --deploy

# Build and deploy all services
./build-and-push.sh all --deploy
```

### Available Services

| Service | Dockerfile | Deployment |
|---------|------------|------------|
| api | Dockerfile.api | janua-api |
| dashboard | Dockerfile.dashboard | janua-dashboard |
| admin | Dockerfile.admin | janua-admin |
| docs | Dockerfile.docs | janua-docs |
| website | Dockerfile.website | janua-website |

## GitHub Actions CI/CD

The primary CI/CD pipeline is defined in `.github/workflows/deploy.yml`.

### Workflow Triggers

- **Push to main**: Runs tests, builds images, and deploys
- **Pull Request to main**: Runs tests only
- **workflow_dispatch**: Manual trigger for full build

### Jobs

1. **test**: Runs type checking and linting
2. **build-api**: Builds and pushes API image to GHCR
3. **build-dashboard**: Builds and pushes Dashboard image
4. **build-website**: Builds and pushes Website image
5. **build-docs**: Builds and pushes Docs image
6. **build-admin**: Builds and pushes Admin image
7. **deploy**: Triggers deployment via Enclii webhook

### Container Registry

Images are published to GitHub Container Registry:
- `ghcr.io/madfam-org/janua-api:latest`
- `ghcr.io/madfam-org/janua-dashboard:latest`
- `ghcr.io/madfam-org/janua-admin:latest`
- `ghcr.io/madfam-org/janua-docs:latest`
- `ghcr.io/madfam-org/janua-website:latest`

### Required Secrets

| Secret | Description |
|--------|-------------|
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions |
| `ENCLII_DEPLOY_WEBHOOK` | Enclii deployment webhook URL |
| `ENCLII_DEPLOY_TOKEN` | Enclii API token |

## Manual Deployment

For emergency or manual deployments:

```bash
# SSH to server
ssh ssh.madfam.io

# Update K8s deployment directly
sudo kubectl set image deployment/janua-api \
  janua-api=localhost:5000/janua-api:latest \
  -n janua

# Monitor rollout
sudo kubectl rollout status deployment/janua-api -n janua
```
