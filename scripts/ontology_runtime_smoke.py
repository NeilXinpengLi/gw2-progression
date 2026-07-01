"""Smoke test a running Ontology Runtime service.

Usage:
    python scripts/ontology_runtime_smoke.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc


def run_smoke(base_url: str) -> dict[str, Any]:
    reset = request_json(base_url, "POST", "/ontology/runtime/reset", {})
    _assert(reset.get("status") == "reset", "reset endpoint did not reset runtime")

    ingest = request_json(
        base_url,
        "POST",
        "/ontology/runtime/ingest",
        {
            "raw": {
                "account": {"name": "Smoke.1234"},
                "snapshot_id": "smoke-snapshot",
                "assets": [{"item_id": 19721, "count": 2, "category": "material_storage", "total_value": 8}],
            }
        },
    )
    _assert(ingest.get("entity_count") == 2, "ingest did not create account + asset entities")
    _assert(ingest.get("relation_count") == 1, "ingest did not create ownership relation")

    execute = request_json(
        base_url,
        "POST",
        "/ontology/runtime/scheduler/execute",
        {
            "actions": [
                {
                    "node_id": "smoke-update",
                    "type": "update_entity",
                    "entity_id": "asset:Smoke.1234:material_storage:19721:0",
                    "patch": {"count": 3},
                }
            ]
        },
    )
    _assert(execute.get("execution", {}).get("executed") == 1, "scheduler endpoint did not execute one DAG node")

    simulate = request_json(
        base_url,
        "POST",
        "/ontology/runtime/simulate",
        {
            "ticks": 1,
            "steps": [
                {
                    "type": "update_entity",
                    "entity_id": "asset:Smoke.1234:material_storage:19721:0",
                    "patch": {"count": 4},
                }
            ],
        },
    )
    _assert(simulate.get("time") == 1, "simulate endpoint did not advance one tick")

    lineage = request_json(base_url, "GET", "/ontology/runtime/lineage")
    _assert(len(lineage.get("lineage", [])) >= 5, "lineage endpoint did not record full flow")

    replay = request_json(base_url, "POST", "/ontology/runtime/replay", {})
    _assert(replay.get("deterministic") is True, "replay endpoint did not reproduce deterministic state")

    trace = request_json(base_url, "GET", "/ontology/runtime/trace/account:Smoke.1234")
    _assert(len(trace.get("steps", [])) == 1, "trace endpoint did not return ownership edge")

    return {
        "status": "passed",
        "base_url": base_url,
        "replay_entity_count": len(replay.get("state", {}).get("entities", {})),
        "lineage_count": len(lineage.get("lineage", [])),
    }


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test GW2 Ontology Runtime MVP endpoints.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    try:
        result = run_smoke(args.base_url)
    except RuntimeError as exc:
        print(f"ontology_runtime_smoke=failed error={exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
