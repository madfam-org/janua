"""
Policy evaluation engine for OPA-compatible authorization.
"""

import hashlib
import json
import re
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)

from app.models.policy import (
    Policy,
    PolicyEffect,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyEvaluation,
    Role,
    RolePolicy,
    UserRole,
)
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.cache import CacheService


class PolicyEngine:
    """
    OPA-compatible policy evaluation engine with caching and performance optimization.
    """

    def __init__(self, db: Session, cache: Optional[CacheService] = None):
        self.db = db
        self.cache = cache or CacheService()
        self.audit_logger = AuditLogger(db)

    async def evaluate(
        self, request: PolicyEvaluateRequest, organization_id: str
    ) -> PolicyEvaluateResponse:
        """
        Evaluate policies for a given request.

        `organization_id` is the tenancy key — `policies` has no `tenant_id`
        column, so the filters this replaced could never have run.
        """
        start_time = time.time()

        # Check cache first
        cache_key = self._generate_cache_key(request, organization_id)
        if self.cache:
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                return PolicyEvaluateResponse(**json.loads(cached_result))

        # Get applicable policies
        policies = await self._get_applicable_policies(
            organization_id=organization_id,
            subject=request.subject,
            resource=request.resource,
            action=request.action,
        )

        # Evaluate policies in priority order
        allowed = False
        denied_by = None
        reasons = []
        matched_policy_ids = []

        for policy in sorted(policies, key=lambda p: p.priority or 0, reverse=True):
            if not policy.enabled:
                continue

            if policy.expires_at and policy.expires_at < datetime.utcnow():
                continue

            result, reason = await self._evaluate_single_policy(policy=policy, request=request)

            if not result:
                continue

            matched_policy_ids.append(str(policy.id))
            reasons.append(f"{policy.name}: {reason}")

            if policy.effect == PolicyEffect.DENY:
                # Explicit deny takes precedence and short-circuits.
                allowed = False
                denied_by = str(policy.id)
                reasons.append(f"Explicitly denied by policy: {policy.name}")
                break
            elif policy.effect == PolicyEffect.ALLOW:
                allowed = True

        # Calculate evaluation time
        evaluation_time_ms = int((time.time() - start_time) * 1000)

        # Create response. These are the fields PolicyEvaluateResponse actually
        # declares; the previous call passed `reasons`/`applied_policies`/
        # `evaluation_time_ms`, which pydantic dropped as extras, so reading
        # them back in _log_evaluation raised AttributeError.
        response = PolicyEvaluateResponse(
            allowed=allowed,
            matched_policies=matched_policy_ids,
            denied_by=denied_by,
            reason="; ".join(reasons) if reasons else "No applicable policy matched",
            metadata={
                "evaluation_time_ms": evaluation_time_ms,
                "organization_id": str(organization_id),
                "policies_considered": len(policies),
            },
        )

        # Log evaluation
        await self._log_evaluation(
            request=request, response=response, organization_id=organization_id
        )

        # Cache result
        if self.cache:
            await self.cache.set(
                cache_key,
                json.dumps(response.dict()),
                ttl=300,  # 5 minutes
            )

        return response

    async def _get_applicable_policies(
        self, organization_id: str, subject: str, resource: str, action: str
    ) -> List[Policy]:
        """
        Get all policies that could apply to this request.

        Every branch is constrained to `organization_id`, including the
        role-derived one — a role-policy mapping must not pull a policy in from
        another organization.
        """
        in_org = and_(Policy.organization_id == organization_id, Policy.enabled.is_(True))

        # Get user's roles
        role_ids = []
        if subject:
            result = await self.db.execute(
                select(UserRole.role_id).where(UserRole.user_id == subject)
            )
            role_ids = list(result.scalars().all())

        # Get policies directly assigned to user
        result = await self.db.execute(
            select(Policy).where(
                and_(in_org, Policy.target_type == "user", Policy.target_id == subject)
            )
        )
        user_policies = list(result.scalars().all())

        # Get policies assigned to user's roles
        role_policies = []
        if role_ids:
            result = await self.db.execute(
                select(RolePolicy.policy_id).where(RolePolicy.role_id.in_(role_ids))
            )
            policy_ids = list(result.scalars().all())

            if policy_ids:
                result = await self.db.execute(
                    select(Policy).where(and_(in_org, Policy.id.in_(policy_ids)))
                )
                role_policies = list(result.scalars().all())

        # Get organization-wide policies
        result = await self.db.execute(
            select(Policy).where(and_(in_org, Policy.target_type == "organization"))
        )
        org_policies = list(result.scalars().all())

        # Get resource-specific policies
        result = await self.db.execute(
            select(Policy).where(and_(in_org, Policy.resource_type.is_not(None)))
        )
        resource_policies = list(result.scalars().all())

        # Filter resource policies by pattern matching
        matching_resource_policies = []
        for policy in resource_policies:
            if policy.resource_pattern and self._matches_pattern(resource, policy.resource_pattern):
                matching_resource_policies.append(policy)

        # Combine all applicable policies
        all_policies = user_policies + role_policies + org_policies + matching_resource_policies

        # Remove duplicates
        unique_policies = {p.id: p for p in all_policies}

        return list(unique_policies.values())

    async def _evaluate_single_policy(
        self, policy: Policy, request: PolicyEvaluateRequest
    ) -> Tuple[bool, str]:
        """
        Evaluate a single policy against the request.
        """
        # Check if action is in policy's allowed actions
        if policy.actions:
            if request.action not in policy.actions:
                return False, f"Action '{request.action}' not in policy actions"

        # Check resource pattern
        if policy.resource_pattern:
            if not self._matches_pattern(request.resource, policy.resource_pattern):
                return False, f"Resource '{request.resource}' doesn't match pattern"

        # Evaluate conditions
        if policy.conditions:
            condition_result = await self._evaluate_conditions(
                policy.conditions, request.context or {}
            )
            if not condition_result:
                return False, "Conditions not met"

        # Evaluate rules (simplified - in production, use OPA or similar)
        if policy.rules:
            rule_result = await self._evaluate_rules(policy.rules, request)
            if not rule_result:
                return False, "Rules evaluation failed"

        return True, "Policy matched and allowed"

    async def _evaluate_conditions(
        self, conditions: Dict[str, Any], context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate policy conditions against request context.
        """
        for key, expected_value in conditions.items():
            if key == "ip_range":
                # Check IP range condition
                client_ip = context.get("client_ip")
                if not client_ip or not self._ip_in_range(client_ip, expected_value):
                    return False

            elif key == "time_window":
                # Check time window condition
                current_time = datetime.utcnow()
                start_time = datetime.fromisoformat(expected_value.get("start"))
                end_time = datetime.fromisoformat(expected_value.get("end"))
                if not (start_time <= current_time <= end_time):
                    return False

            elif key == "mfa_required":
                # Check MFA requirement
                has_mfa = context.get("mfa_verified", False)
                if expected_value and not has_mfa:
                    return False

            elif key == "attributes":
                # Check custom attributes
                for attr_key, attr_value in expected_value.items():
                    if context.get(attr_key) != attr_value:
                        return False

        return True

    async def _evaluate_rules(self, rules: Dict[str, Any], request: PolicyEvaluateRequest) -> bool:
        """
        Evaluate policy rules (simplified version).
        In production, integrate with OPA for full Rego support.
        """
        # Simple rule evaluation logic
        if "allow" in rules:
            allow_rules = rules["allow"]

            # Check if all allow conditions are met
            if isinstance(allow_rules, dict):
                for key, value in allow_rules.items():
                    if key == "subject":
                        if not self._matches_pattern(request.subject, value):
                            return False
                    elif key == "action":
                        if not self._matches_pattern(request.action, value):
                            return False
                    elif key == "resource":
                        if not self._matches_pattern(request.resource, value):
                            return False

            return True

        if "deny" in rules:
            deny_rules = rules["deny"]

            # Check if any deny conditions are met
            if isinstance(deny_rules, dict):
                for key, value in deny_rules.items():
                    if key == "subject":
                        if self._matches_pattern(request.subject, value):
                            return False
                    elif key == "action":
                        if self._matches_pattern(request.action, value):
                            return False
                    elif key == "resource":
                        if self._matches_pattern(request.resource, value):
                            return False

        return True

    def _matches_pattern(self, value: str, pattern: str) -> bool:
        """
        Check if a value matches a pattern (supports wildcards).
        """
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        regex_pattern = f"^{regex_pattern}$"

        return bool(re.match(regex_pattern, value))

    def _ip_in_range(self, ip: str, ip_range: str) -> bool:
        """
        Check if an IP address is in a CIDR range.
        """
        # Simplified IP range checking
        # In production, use ipaddress module for proper CIDR checking
        if "/" in ip_range:
            network, mask = ip_range.split("/")
            # Simplified check - just check if IP starts with network prefix
            return ip.startswith(network.rsplit(".", 1)[0])
        else:
            return ip == ip_range

    def _generate_cache_key(self, request: PolicyEvaluateRequest, tenant_id: str) -> str:
        """
        Generate a cache key for policy evaluation results.
        """
        key_data = f"{tenant_id}:{request.subject}:{request.action}:{request.resource}"
        if request.context:
            key_data += f":{json.dumps(request.context, sort_keys=True)}"

        return f"policy:eval:{hashlib.sha256(key_data.encode()).hexdigest()}"

    async def _log_evaluation(
        self, request: PolicyEvaluateRequest, response: PolicyEvaluateResponse, organization_id: str
    ):
        """
        Log policy evaluation for audit trail.

        Only the kwargs below are real columns on `PolicyEvaluation`; the call
        this replaced passed six that do not exist (`subject`, `resource`,
        `allowed`, `reasons`, `applied_policies`, `evaluation_time_ms`) and
        would have raised TypeError in the declarative constructor.
        """
        # `policy_evaluations.policy_id` is NOT NULL, so a no-match evaluation
        # cannot be recorded as a row — it is captured in the audit log only.
        if response.matched_policies:
            evaluation = PolicyEvaluation(
                policy_id=response.matched_policies[0],
                subject_id=request.subject_id,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                action=request.action,
                result=response.allowed,
                context=request.context or {},
            )

            self.db.add(evaluation)
            await self.db.commit()

        # Also log to audit system
        await self.audit_logger.log(
            event_type=AuditAction.POLICY_EVALUATE,
            tenant_id=str(organization_id),
            identity_id=request.subject_id,
            organization_id=str(organization_id),
            resource_type="policy",
            resource_id=request.resource_id,
            details={
                "allowed": response.allowed,
                "action": request.action,
                "resource": request.resource,
                "matched_policies": response.matched_policies,
                "evaluation_time_ms": response.metadata.get("evaluation_time_ms"),
            },
            ip_address=request.context.get("client_ip") if request.context else None,
        )
        # The logger flushes into this session; commit so the audit row persists.
        await self.db.commit()

    async def compile_to_wasm(self, policy: Policy) -> Optional[str]:
        """
        Compile policy to WASM for edge evaluation.
        Requires OPA CLI installed and configured.

        NOTE: `rego_code` is not a column on `Policy` and never has been, so for
        a persisted policy this returns None. Nothing in the application calls
        this method; it is kept for the OPA integration it was written for.
        """
        import os
        import subprocess
        import tempfile

        if not getattr(policy, "rego_code", None):
            logger.warning("Policy has no rego_code; nothing to compile")
            return None

        try:
            # Check if OPA is available
            opa_check = subprocess.run(
                ["opa", "version"], capture_output=True, text=True, timeout=5
            )

            if opa_check.returncode != 0:
                logger.warning("OPA not available for WASM compilation")
                return None

            # Create temporary file for policy
            with tempfile.NamedTemporaryFile(mode="w", suffix=".rego", delete=False) as f:
                f.write(policy.rego_code)
                policy_file = f.name

            # Create temporary output directory
            output_dir = tempfile.mkdtemp()

            try:
                # Compile to WASM using OPA CLI
                compile_result = subprocess.run(
                    [
                        "opa",
                        "build",
                        "-t",
                        "wasm",
                        "-e",
                        policy.name,
                        "-o",
                        os.path.join(output_dir, "bundle.tar.gz"),
                        policy_file,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if compile_result.returncode != 0:
                    logger.error(f"OPA WASM compilation failed: {compile_result.stderr}")
                    return None

                # Read the compiled WASM bundle
                bundle_path = os.path.join(output_dir, "bundle.tar.gz")
                if os.path.exists(bundle_path):
                    with open(bundle_path, "rb") as f:
                        import base64

                        wasm_bundle = base64.b64encode(f.read()).decode("utf-8")
                        logger.info(f"Policy {policy.name} compiled to WASM successfully")
                        return wasm_bundle

                return None

            finally:
                # Cleanup temporary files
                import shutil

                os.unlink(policy_file)
                shutil.rmtree(output_dir, ignore_errors=True)

        except subprocess.TimeoutExpired:
            logger.error("OPA compilation timeout")
            return None
        except Exception as e:
            logger.error(f"WASM compilation error: {e}")
            return None

    @lru_cache(maxsize=1000)
    def get_user_permissions(self, user_id: str, tenant_id: str) -> List[str]:
        """
        Get all permissions for a user based on their roles.
        """
        user_roles = self.db.query(UserRole).filter(UserRole.user_id == user_id).all()

        permissions = set()
        for user_role in user_roles:
            role = self.db.query(Role).filter(Role.id == user_role.role_id).first()
            if role and role.permissions:
                permissions.update(role.permissions)

        return list(permissions)
