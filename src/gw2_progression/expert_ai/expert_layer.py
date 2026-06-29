"""Read-only expert reasoning layer for GW2 Expert AI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class LLMProviderConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMProviderConfig":
        config = cls(
            api_key=os.getenv("EXPERT_AI_LLM_API_KEY", ""),
            base_url=os.getenv("EXPERT_AI_LLM_BASE_URL", ""),
            model=os.getenv("EXPERT_AI_LLM_MODEL", "gpt-4o-mini"),
            timeout_seconds=float(os.getenv("EXPERT_AI_LLM_TIMEOUT", "30")),
        )
        key_file = os.getenv("EXPERT_AI_LLM_KEY_FILE", "")
        return config.with_key_file(key_file) if key_file else config

    def with_key_file(self, path: str | Path) -> "LLMProviderConfig":
        values = _read_key_file(path)
        return LLMProviderConfig(
            api_key=values.get("api_key", self.api_key),
            base_url=values.get("base_url", self.base_url),
            model=values.get("model", self.model),
            timeout_seconds=self.timeout_seconds,
        )

    def redacted(self) -> dict[str, Any]:
        return {"configured": bool(self.api_key and self.base_url), "base_url": self.base_url, "model": self.model, "api_key": _redact_key(self.api_key)}


class LLMExpertLayer:
    """Deterministic provider-compatible expert layer.

    The class intentionally does not mutate runtime state. A future hosted LLM
    provider can replace the deterministic text generation behind this facade.
    """

    def __init__(self, config: LLMProviderConfig | None = None, client: Any | None = None) -> None:
        self.config = config or LLMProviderConfig.from_env()
        self.client = client

    def provider_status(self) -> dict[str, Any]:
        return self.config.redacted()

    def explain_decision(self, decision: dict[str, Any], context: dict[str, Any] | None = None, use_provider: bool = False) -> dict[str, Any]:
        context = context or {}
        if use_provider and self.config.api_key and self.config.base_url:
            try:
                response = self._chat([
                    {"role": "system", "content": "You are a Guild Wars 2 progression expert. Explain decisions without mutating state."},
                    {"role": "user", "content": f"Decision: {decision}\nContext: {context}\nReturn concise JSON-like guidance."},
                ])
                return {"provider": "openai_compatible", "mode": "read_only", "explanation": response, "config": self.config.redacted()}
            except Exception as exc:
                fallback = self._deterministic_explanation(decision, context)
                return {
                    "provider": "openai_compatible",
                    "mode": "read_only_fallback",
                    "error": {"type": type(exc).__name__, "detail": str(exc)},
                    "explanation": fallback,
                    "config": self.config.redacted(),
                }
        return {"provider": "deterministic_expert", "mode": "read_only", "explanation": self._deterministic_explanation(decision, context)}

    def _deterministic_explanation(self, decision: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        factors = decision.get("factors", [])
        strongest = sorted(factors, key=lambda factor: abs(float(factor.get("value", 0)) * float(factor.get("weight", 1))), reverse=True)[:3]
        return {
            "decision": decision.get("decision", "REVIEW"),
            "summary": decision.get("reason", "Decision requires expert review."),
            "key_factors": [factor.get("name", "factor") for factor in strongest],
            "context_keys": sorted(context.keys()),
        }

    def generate_counterfactuals(self, decision: dict[str, Any], limit: int = 3) -> dict[str, Any]:
        factors = decision.get("factors", [])[:limit]
        counterfactuals = []
        for factor in factors:
            impact = factor.get("impact", "")
            direction = "reduce" if impact == "negative" else "increase"
            counterfactuals.append({
                "factor": factor.get("name", "factor"),
                "change": f"{direction} signal strength",
                "expected_effect": "decision confidence improves",
            })
        return {"counterfactuals": counterfactuals, "mutates_state": False}

    def interpret_graph(self, graph: dict[str, Any]) -> dict[str, Any]:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        relation_counts: dict[str, int] = {}
        for edge in edges:
            relation_counts[edge.get("relation_type", "related_to")] = relation_counts.get(edge.get("relation_type", "related_to"), 0) + 1
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "relation_counts": relation_counts,
            "summary": f"Graph contains {len(nodes)} entities and {len(edges)} relations.",
            "mutates_state": False,
        }

    def simulate_expert_thinking(self, prompt: str, graph: dict[str, Any] | None = None) -> dict[str, Any]:
        graph_summary = self.interpret_graph(graph or {"nodes": [], "edges": []})
        return {
            "prompt": prompt,
            "reasoning_style": "guild_wars_2_progression_expert",
            "steps": [
                "Identify account state and goal constraints.",
                "Check wealth, liquidity, build readiness, and blocking risks.",
                "Prefer reversible, high-confidence progression actions.",
            ],
            "graph_summary": graph_summary,
            "mutates_state": False,
        }

    def _chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        url = self.config.base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        client = self.client or httpx.Client(timeout=self.config.timeout_seconds)
        try:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"},
                json={"model": self.config.model, "messages": messages, "temperature": 0.2},
            )
            response.raise_for_status()
            payload = response.json()
            content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"content": content, "raw_model": payload.get("model", self.config.model)}
        finally:
            if self.client is None and hasattr(client, "close"):
                client.close()


def _read_key_file(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        normalized = key.lower().replace(" ", "_")
        if normalized in {"api_key", "api", "key", "api_key_"} or "api" in normalized and "key" in normalized:
            values["api_key"] = value
        elif normalized in {"base_url", "base"} or "base" in normalized and "url" in normalized:
            values["base_url"] = value
        elif normalized == "model":
            values["model"] = value
    return values


def _redact_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"
