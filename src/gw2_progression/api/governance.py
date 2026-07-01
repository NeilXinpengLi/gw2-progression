"""API route governance: product category, stability, and release gates."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import FastAPI


class ApiCategory(StrEnum):
    CORE_PRODUCT = "Core Product"
    COMMERCE = "Commerce"
    AI_LAB = "AI Lab"
    INFRASTRUCTURE = "Infrastructure"


class StabilityLevel(StrEnum):
    GA = "GA"
    BETA = "Beta"
    EXPERIMENTAL = "Experimental"
    INTERNAL = "Internal"


class ReleaseGate(StrEnum):
    ALWAYS_ON = "always_on"
    COMMERCE_ENABLED = "commerce_enabled"
    AI_LAB_ENABLED = "ai_lab_enabled"
    INFRASTRUCTURE_ENABLED = "infrastructure_enabled"


@dataclass(frozen=True)
class RouteGovernance:
    key: str
    category: ApiCategory
    stability: StabilityLevel
    gate: ReleaseGate
    owner: str
    decision_role: str
    release_gate: str


API_ROUTE_GOVERNANCE: dict[str, RouteGovernance] = {
    "account": RouteGovernance("account", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "account overview", "contract + smoke"),
    "advice": RouteGovernance("advice", ApiCategory.CORE_PRODUCT, StabilityLevel.BETA, ReleaseGate.ALWAYS_ON, "product", "player advice", "contract + smoke"),
    "analyze": RouteGovernance("analyze", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "legacy analyze", "contract + smoke"),
    "reports": RouteGovernance("reports", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "report artifacts", "contract + smoke"),
    "resolve": RouteGovernance("resolve", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "name/id resolution", "contract"),
    "valuation": RouteGovernance("valuation", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "account valuation", "contract + smoke"),
    "crafting": RouteGovernance("crafting", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "crafting planning", "contract + smoke"),
    "goals": RouteGovernance("goals", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "goal tracking", "contract"),
    "guild": RouteGovernance("guild", ApiCategory.CORE_PRODUCT, StabilityLevel.BETA, ReleaseGate.ALWAYS_ON, "product", "guild workspace", "contract"),
    "progression": RouteGovernance("progression", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "progression templates", "contract"),
    "quests": RouteGovernance("quests", ApiCategory.CORE_PRODUCT, StabilityLevel.BETA, ReleaseGate.ALWAYS_ON, "product", "quest planning", "contract"),
    "tp": RouteGovernance("tp", ApiCategory.CORE_PRODUCT, StabilityLevel.BETA, ReleaseGate.ALWAYS_ON, "product", "trading-post strategy", "contract"),
    "builds": RouteGovernance("builds", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "build readiness", "contract"),
    "engine": RouteGovernance("engine", ApiCategory.CORE_PRODUCT, StabilityLevel.BETA, ReleaseGate.ALWAYS_ON, "product", "decision engine", "contract"),
    "goal_driven": RouteGovernance("goal_driven", ApiCategory.CORE_PRODUCT, StabilityLevel.BETA, ReleaseGate.ALWAYS_ON, "product", "product planning layer", "contract + smoke"),
    "insight": RouteGovernance("insight", ApiCategory.CORE_PRODUCT, StabilityLevel.BETA, ReleaseGate.ALWAYS_ON, "product", "insight UI data", "contract"),
    "production": RouteGovernance("production", ApiCategory.AI_LAB, StabilityLevel.EXPERIMENTAL, ReleaseGate.AI_LAB_ENABLED, "ai-lab", "v4/v5 production experiment", "AI lab gate"),
    "agent": RouteGovernance("agent", ApiCategory.CORE_PRODUCT, StabilityLevel.BETA, ReleaseGate.ALWAYS_ON, "product", "coach facade", "contract"),
    "commerce": RouteGovernance("commerce", ApiCategory.COMMERCE, StabilityLevel.BETA, ReleaseGate.COMMERCE_ENABLED, "commerce", "orders and licenses", "idempotency + contract"),
    "commercial": RouteGovernance("commercial", ApiCategory.COMMERCE, StabilityLevel.BETA, ReleaseGate.COMMERCE_ENABLED, "commerce", "paid reports", "idempotency + contract"),
    "payment": RouteGovernance("payment", ApiCategory.COMMERCE, StabilityLevel.BETA, ReleaseGate.COMMERCE_ENABLED, "commerce", "payment webhooks", "webhook idempotency"),
    "affiliates": RouteGovernance("affiliates", ApiCategory.COMMERCE, StabilityLevel.BETA, ReleaseGate.COMMERCE_ENABLED, "commerce", "affiliate sales", "idempotency + contract"),
    "subscriptions": RouteGovernance("subscriptions", ApiCategory.COMMERCE, StabilityLevel.BETA, ReleaseGate.COMMERCE_ENABLED, "commerce", "scheduled delivery", "delivery retry tests"),
    "credentials": RouteGovernance("credentials", ApiCategory.INFRASTRUCTURE, StabilityLevel.BETA, ReleaseGate.INFRASTRUCTURE_ENABLED, "platform", "credential storage", "security review"),
    "audit": RouteGovernance("audit", ApiCategory.INFRASTRUCTURE, StabilityLevel.INTERNAL, ReleaseGate.INFRASTRUCTURE_ENABLED, "platform", "audit trail", "internal only"),
    "workspaces": RouteGovernance("workspaces", ApiCategory.INFRASTRUCTURE, StabilityLevel.BETA, ReleaseGate.INFRASTRUCTURE_ENABLED, "platform", "collaboration", "contract"),
    "data_mesh": RouteGovernance("data_mesh", ApiCategory.INFRASTRUCTURE, StabilityLevel.BETA, ReleaseGate.INFRASTRUCTURE_ENABLED, "platform", "data governance", "contract"),
    "v4": RouteGovernance("v4", ApiCategory.AI_LAB, StabilityLevel.EXPERIMENTAL, ReleaseGate.AI_LAB_ENABLED, "ai-lab", "optimizer experiment", "AI lab gate"),
    "v5": RouteGovernance("v5", ApiCategory.AI_LAB, StabilityLevel.EXPERIMENTAL, ReleaseGate.AI_LAB_ENABLED, "ai-lab", "learning experiment", "AI lab gate"),
    "expert_ai": RouteGovernance("expert_ai", ApiCategory.AI_LAB, StabilityLevel.EXPERIMENTAL, ReleaseGate.AI_LAB_ENABLED, "ai-lab", "experimental training layer", "AI lab gate"),
    "arena": RouteGovernance("arena", ApiCategory.AI_LAB, StabilityLevel.EXPERIMENTAL, ReleaseGate.AI_LAB_ENABLED, "ai-lab", "agent arena", "AI lab gate"),
    "lifecycle": RouteGovernance("lifecycle", ApiCategory.AI_LAB, StabilityLevel.EXPERIMENTAL, ReleaseGate.AI_LAB_ENABLED, "ai-lab", "lifecycle simulation", "AI lab gate"),
    "rule_v2": RouteGovernance("rule_v2", ApiCategory.AI_LAB, StabilityLevel.EXPERIMENTAL, ReleaseGate.AI_LAB_ENABLED, "ai-lab", "rule evolution", "AI lab gate"),
    "cognitive_os": RouteGovernance("cognitive_os", ApiCategory.AI_LAB, StabilityLevel.EXPERIMENTAL, ReleaseGate.AI_LAB_ENABLED, "ai-lab", "cognitive experiment", "AI lab gate"),
    "ontology_runtime": RouteGovernance(
        "ontology_runtime",
        ApiCategory.INFRASTRUCTURE,
        StabilityLevel.BETA,
        ReleaseGate.INFRASTRUCTURE_ENABLED,
        "platform",
        "governance/evidence layer",
        "contract + replay",
    ),
}

APP_ENDPOINT_GOVERNANCE: dict[str, RouteGovernance] = {
    "auth_session": RouteGovernance("auth_session", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "session auth", "core smoke"),
    "health": RouteGovernance("health", ApiCategory.INFRASTRUCTURE, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "platform", "health check", "deployment gate"),
    "metrics": RouteGovernance("metrics", ApiCategory.INFRASTRUCTURE, StabilityLevel.BETA, ReleaseGate.INFRASTRUCTURE_ENABLED, "platform", "runtime metrics", "ops review"),
    "static_pages": RouteGovernance("static_pages", ApiCategory.CORE_PRODUCT, StabilityLevel.GA, ReleaseGate.ALWAYS_ON, "product", "static UI shell", "smoke"),
    "websocket": RouteGovernance("websocket", ApiCategory.INFRASTRUCTURE, StabilityLevel.BETA, ReleaseGate.INFRASTRUCTURE_ENABLED, "platform", "push channel", "ops review"),
}


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def route_enabled(meta: RouteGovernance) -> bool:
    env = os.environ.get("ENV", "development").lower()
    experimental_default = env != "production"
    experimental_enabled = _env_flag("ENABLE_EXPERIMENTAL_ROUTES", experimental_default)

    if meta.stability == StabilityLevel.EXPERIMENTAL and not experimental_enabled:
        return False
    if meta.gate == ReleaseGate.ALWAYS_ON:
        return True
    if meta.gate == ReleaseGate.COMMERCE_ENABLED:
        return _env_flag("ENABLE_COMMERCE_ROUTES", True)
    if meta.gate == ReleaseGate.INFRASTRUCTURE_ENABLED:
        return _env_flag("ENABLE_INFRASTRUCTURE_ROUTES", True)
    if meta.gate == ReleaseGate.AI_LAB_ENABLED:
        return _env_flag("ENABLE_AI_LAB_ROUTES", env != "production")
    return False


def include_governed_routers(app: FastAPI, router_bindings: list[tuple[str, Any]]) -> list[dict[str, str]]:
    included: list[dict[str, str]] = []
    for key, router in router_bindings:
        meta = API_ROUTE_GOVERNANCE[key]
        enabled = route_enabled(meta)
        if enabled:
            app.include_router(router)
        included.append(
            {
                "key": key,
                "category": meta.category.value,
                "stability": meta.stability.value,
                "gate": meta.gate.value,
                "enabled": str(enabled).lower(),
                "owner": meta.owner,
                "decision_role": meta.decision_role,
                "release_gate": meta.release_gate,
            }
        )
    return included


def governance_row(meta: RouteGovernance) -> dict[str, str]:
    return {
        "key": meta.key,
        "category": meta.category.value,
        "stability": meta.stability.value,
        "gate": meta.gate.value,
        "enabled": str(route_enabled(meta)).lower(),
        "owner": meta.owner,
        "decision_role": meta.decision_role,
        "release_gate": meta.release_gate,
    }


def governance_snapshot() -> list[dict[str, str]]:
    return [governance_row(meta) for meta in [*APP_ENDPOINT_GOVERNANCE.values(), *API_ROUTE_GOVERNANCE.values()]]


def governance_snapshot_hash(rows: list[dict[str, str]] | None = None) -> str:
    payload = json.dumps(rows or governance_snapshot(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def production_exposure_violations(rows: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    """Return enabled routes that should not be exposed in production."""
    if os.environ.get("ENV", "development").lower() != "production":
        return []
    violations: list[dict[str, str]] = []
    for row in rows or governance_snapshot():
        if row["enabled"] != "true":
            continue
        if row["category"] == ApiCategory.AI_LAB.value:
            violations.append({**row, "violation": "ai_lab_enabled_in_production"})
        elif row["stability"] == StabilityLevel.EXPERIMENTAL.value:
            violations.append({**row, "violation": "experimental_enabled_in_production"})
    return violations


def governance_release_report(rows: list[dict[str, str]] | None = None) -> dict[str, Any]:
    snapshot = rows or governance_snapshot()
    violations = production_exposure_violations(snapshot)
    return {
        "snapshot_hash": governance_snapshot_hash(snapshot),
        "route_count": len(snapshot),
        "release_status": "blocked" if violations else "pass",
        "production_exposure_violations": violations,
        "routes": snapshot,
    }
