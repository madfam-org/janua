# Enclii Agent Handoff: janua-api K8s Deployment Rollout Failure

## 1. Problem Statement

- **Workflow**: `Publish Docker Image` (`.github/workflows/docker-publish.yml`) in `madfam-org/janua`
- **Failing step**: `Deploy to Kubernetes (comprehensive deployment fix)` in job `deploy-api`
- **Symptom**: `kubectl rollout status deployment/janua-api -n janua --timeout=300s` times out with `0 out of 2 new replicas have been updated`
- **Impact**: No janua-api code changes have reached production since Jan 26

## 2. Timeline

- **Last successful deploy**: 2026-01-26 (~01:14 UTC)
- **First failure**: 2026-02-02 (~01:42 UTC) — 18 consecutive failures since
- **No code changes to the workflow or K8s manifests** between last success and first failure — only dependency bumps and application code changes

## 3. Failure Evidence (verbatim logs)

The deployment step produces the following sequence every run:

1. Image patch succeeds:
   ```
   deployment.apps/janua-api patched
   ```

2. imagePullSecrets/service/networkPolicy report no change:
   ```
   patched (no change)
   ```

3. Rollout stalls immediately:
   ```
   Waiting for deployment "janua-api" rollout to finish: 0 out of 2 new replicas have been updated...
   ```

4. After 300 seconds:
   ```
   error: timed out waiting for the condition
   ```

**Key observation**: The deployment accepts the image patch but **never begins creating new ReplicaSet pods**. The count stays at `0 out of 2` for the entire timeout — it does not progress to 1/2 or show scheduling activity.

## 4. Enclii/Switchyard Interaction Context

- The workflow **removes** Enclii labels before patching. All four removals report "not found":
  - `enclii.dev/managed-by`
  - `enclii.dev/project`
  - `enclii.dev/release`
  - `enclii.dev/deployment`
- The K8s manifest includes the annotation `enclii.dev/reconcile: "disabled"`
- Despite this, Switchyard may be interfering at the admission controller or reconciliation level, reverting or blocking the image patch before a new ReplicaSet is created

## 5. Diagnostic Questions for Enclii Agent

1. **Has Switchyard's reconciliation controller been updated between Jan 26 and Feb 2?** Does it now ignore the `enclii.dev/reconcile: "disabled"` annotation?
2. **Is there a Switchyard admission webhook or mutating webhook** that could prevent new ReplicaSets from being created even when the annotation is set?
3. **Are there resource quotas or LimitRanges** in the `janua` namespace that could block pod scheduling?
4. **Is the `ghcr-credentials` imagePullSecret still valid** in the `janua` namespace? (The GHCR token refresh step runs in the workflow, but credential expiry could cause silent pull failures)
5. **Are there node resource exhaustion issues on `foundry-core`** preventing new pods from scheduling?
6. **Is there a PodDisruptionBudget or other policy** blocking the rolling update from progressing?

## 6. Requested Actions

Run these diagnostic commands on `foundry-core` and report the output:

```bash
# 1. Deployment state and conditions
kubectl describe deployment janua-api -n janua

# 2. Check if a new ReplicaSet was created at all
kubectl get rs -n janua -l app=janua-api

# 3. Recent events for janua-api
kubectl get events -n janua --sort-by='.lastTimestamp' | grep janua-api

# 4. Current pod states
kubectl get pods -n janua -l app=janua-api

# 5. Describe the newest janua-api pod (check for ImagePullBackOff, resource, or scheduling issues)
kubectl describe pod <newest-janua-api-pod> -n janua

# 6. Check Switchyard controller logs for reconciliation activity against janua-api
# (use whatever log access method is available for the Switchyard controller)

# 7. Check for mutating/validating webhooks that fire for deployments in the janua namespace
kubectl get mutatingwebhookconfigurations,validatingwebhookconfigurations -o wide
```

## 7. Configuration Reference

| Parameter | Value |
|-----------|-------|
| **Cluster** | foundry-core (K3s, 95.217.198.239) |
| **Namespace** | `janua` |
| **Deployment** | `janua-api` (2 replicas, RollingUpdate, maxSurge=1, maxUnavailable=0) |
| **Image** | `ghcr.io/madfam-org/janua-api:main-<sha>` |
| **Container port** | 8080 |
| **Service** | ClusterIP, port 80 → targetPort 8080 |
| **Health probes** | `/health:8080` (liveness, readiness, startup) |
| **Resources** | 100m/256Mi request, 500m/512Mi limit |
| **Repo** | `madfam-org/janua` |
| **Latest failing run** | 21576466593 |
| **Last successful run** | 21343062500 |

## 8. Port Mismatch Flag

`.enclii.yml` specifies `port: 4100` while the K8s manifest and Dockerfile use `8080`. The workflow patches `containerPort: 8080`.

**If Switchyard's reconciler reads `.enclii.yml` and tries to enforce port 4100**, this could cause:
- Container startup failures (app listens on 8080, probe hits 4100)
- Health check failures preventing readiness
- Stalled rollout as new pods never become ready

This mismatch should be investigated as a potential root cause if Switchyard is actively reconciling despite the `disabled` annotation.
