"""Policy Engine — policy-as-code for the ontology runtime.

Policies are composable, enable/disable-able rules that evaluate runtime
context and produce PolicyResult (pass/warn/block). Inspired by OOSK's
Policy Skill: every policy is a named check with severity and logic.

Policy levels:
  L1_STATIC:     Code-level checks (CI-enforceable)
  L2_RUNTIME:    Pre-execution checks (action preconditions)
  L3_GOVERNANCE: Post-execution governance (QA gate / publish gate)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("gw2.ontology.policy")


class PolicyLevel(Enum):
    L1_STATIC = "L1_STATIC"
    L2_RUNTIME = "L2_RUNTIME"
    L3_GOVERNANCE = "L3_GOVERNANCE"


class PolicySeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class PolicyResult:
    policy_name: str
    passed: bool
    severity: PolicySeverity = PolicySeverity.ERROR
    detail: str = ""
    blocking: bool = True


@dataclass
class PolicyDef:
    name: str
    description: str = ""
    level: PolicyLevel = PolicyLevel.L2_RUNTIME
    severity: PolicySeverity = PolicySeverity.ERROR
    enabled: bool = True
    check_fn: Callable[..., Any] | None = None


_policies: dict[str, PolicyDef] = {}


def register(policy: PolicyDef) -> None:
    """Register a policy."""
    _policies[policy.name] = policy


def enable(name: str) -> None:
    p = _policies.get(name)
    if p:
        p.enabled = True


def disable(name: str) -> None:
    p = _policies.get(name)
    if p:
        p.enabled = False


def list_policies(level: PolicyLevel | None = None) -> list[PolicyDef]:
    if level:
        return [p for p in _policies.values() if p.level == level]
    return list(_policies.values())


async def evaluate(context: dict | None = None, level: PolicyLevel | None = None) -> list[PolicyResult]:
    """Evaluate all enabled policies at the given level (or all levels)."""
    results: list[PolicyResult] = []
    ctx = context or {}
    for policy in _policies.values():
        if not policy.enabled:
            continue
        if level and policy.level != level:
            continue
        if policy.check_fn is None:
            continue
        try:
            if policy.check_fn.__code__.co_flags & 0x80:  # is coroutine
                result = await policy.check_fn(ctx)
            else:
                result = policy.check_fn(ctx)
        except Exception as e:
            result = PolicyResult(
                policy_name=policy.name,
                passed=False,
                severity=policy.severity,
                detail=f"Policy evaluation error: {e}",
                blocking=True,
            )
        if isinstance(result, dict):
            result = PolicyResult(
                policy_name=policy.name,
                passed=result.get("passed", False),
                severity=PolicySeverity(result.get("severity", policy.severity.value)),
                detail=result.get("detail", ""),
                blocking=result.get("blocking", True),
            )
        if not isinstance(result, PolicyResult):
            continue
        results.append(result)
    return results


def has_failures(results: list[PolicyResult], min_severity: PolicySeverity = PolicySeverity.WARNING) -> bool:
    """Check if any result has failed at or above the minimum severity."""
    severity_order = {PolicySeverity.INFO: 0, PolicySeverity.WARNING: 1, PolicySeverity.ERROR: 2}
    threshold = severity_order.get(min_severity, 0)
    return any(
        not r.passed and severity_order.get(r.severity, 0) >= threshold
        for r in results
    )


def summary(results: list[PolicyResult]) -> dict:
    """Policy evaluation summary."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    errors = [r for r in results if not r.passed and r.severity == PolicySeverity.ERROR]
    warnings = [r for r in results if not r.passed and r.severity == PolicySeverity.WARNING]
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "blocking_errors": [r.policy_name for r in errors if r.blocking],
        "warnings": [r.policy_name for r in warnings],
        "status": "pass" if failed == 0 else "fail",
    }
