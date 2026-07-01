"""Tests for the ontology runtime smoke script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load_smoke_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "ontology_runtime_smoke.py"
    spec = importlib.util.spec_from_file_location("ontology_runtime_smoke", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_ontology_runtime_smoke_validates_full_runtime_flow(monkeypatch):
    module = _load_smoke_module()
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append((method, path, payload))
        if path == "/ontology/runtime/reset":
            return {"status": "reset"}
        if path == "/ontology/runtime/ingest":
            return {"entity_count": 2, "relation_count": 1}
        if path == "/ontology/runtime/scheduler/execute":
            return {"execution": {"executed": 1}}
        if path == "/ontology/runtime/simulate":
            return {"time": 1}
        if path == "/ontology/runtime/lineage":
            return {"lineage": [{"step": step} for step in range(1, 6)]}
        if path == "/ontology/runtime/replay":
            return {"deterministic": True, "state": {"entities": {"account:Smoke.1234": {}, "asset:1": {}}}}
        if path == "/ontology/runtime/trace/account:Smoke.1234":
            return {"steps": [{"from": "account:Smoke.1234", "to": "asset:1"}]}
        raise AssertionError(path)

    monkeypatch.setattr(module, "request_json", fake_request_json)

    result = module.run_smoke("http://example.test")

    assert result["status"] == "passed"
    assert result["lineage_count"] == 5
    assert result["replay_entity_count"] == 2
    assert [path for _, path, _ in calls] == [
        "/ontology/runtime/reset",
        "/ontology/runtime/ingest",
        "/ontology/runtime/scheduler/execute",
        "/ontology/runtime/simulate",
        "/ontology/runtime/lineage",
        "/ontology/runtime/replay",
        "/ontology/runtime/trace/account:Smoke.1234",
    ]
