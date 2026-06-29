"""GW2 Expert AI bootstrap CLI: 1 API key -> training pipeline (10-step flow).

Usage:
  # Offline warm-start (synthetic data, no API key needed)
  python scripts/bootstrap_expert_ai.py --mode synthetic --rounds 3

  # Online (real API key -> real seed -> synthetic expansion)
  python scripts/bootstrap_expert_ai.py --mode online --api-key YOUR_KEY --rounds 10

  # Docker backend + online
  python scripts/bootstrap_expert_ai.py --mode online --api-key YOUR_KEY --docker
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent))


def color(text: str, code: str = "92") -> str:
    return f"\033[{code}m{text}\033[0m"


def banner() -> None:
    print(color("=" * 64, "96"))
    print(color("  GW2 Expert AI — Bootstrap Pipeline v1.0", "96"))
    print(color("  10-step flow: 1 key -> synthetic expansion -> model", "96"))
    print(color("=" * 64, "96"))


def step_label(n: int, label: str) -> str:
    return color(f"  STEP {n:>2}/10  {label}", "93")


def invoke(system: Any, method: str, *args, **kwargs) -> dict[str, Any]:
    fn = getattr(system, method, None)
    if fn:
        return fn(*args, **kwargs)
    raise AttributeError(f"ExpertAISystem has no method {method}")


def run_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    from gw2_progression.expert_ai.core import ExpertAISystem

    system = ExpertAISystem()

    summary: dict[str, Any] = {"steps": {}, "models": [], "artifacts": []}
    api_key = args.api_key or os.environ.get("GW2_API_KEY", "")
    account_name = args.account_name or "bootstrap_seed"

    total_start = time.time()

    # ── Step 1: Fetch API (real or synthetic) ──────────────────────────
    print(f"\n{step_label(1, 'FETCH — seed data acquisition')}")
    if args.mode == "online" and api_key:
        try:
            import asyncio

            from gw2_progression.analyzer import fetch_all
            from gw2_progression.expert_ai.adapters import account_contents_to_runtime_payload

            contents = asyncio.run(fetch_all(api_key))
            payload = account_contents_to_runtime_payload(contents, item_limit=200)
            for entity in payload["entities"]:
                system.runtime.add_entity(entity)
            for relation in payload["relations"]:
                system.runtime.add_relation(relation)
            snapshot = system.runtime.snapshot()
            print(f"    [ok] Real account: {contents.account_name} ({payload['summary']['entities']} entities, {payload['summary']['relations']} relations)")
            result = {"snapshot_id": snapshot.id, "summary": payload["summary"]}
        except Exception as e:
            print(f"    [!] API fetch failed: {e}")
            result = _seed_synthetic(system, account_name)
    else:
        result = _seed_synthetic(system, account_name)
    summary["steps"]["1_fetch"] = {"result": result.get("summary", {})}
    print(f"    -> {result.get('snapshot_id', 'ok')}")

    # ── Step 2: Build DGSK Graph ──────────────────────────────────────
    print(f"\n{step_label(2, 'DGSK — domain graph compilation')}")
    dgsk = system.compile_graph(file_path=str(Path.cwd() / "domain_graph.yaml"))
    print(f"    [ok] Compiled: {len(dgsk['dgsk']['nodes'])} node types, {len(dgsk['dgsk']['edges'])} edge types")
    errors = dgsk.get("errors", [])
    if errors:
        for e in errors:
            print(f"    [!]  {e}")
    summary["steps"]["2_dgsk"] = {"graph_id": dgsk["id"], "errors": errors}

    # ── Step 3: Initialize OOSK World ─────────────────────────────────
    print(f"\n{step_label(3, 'OOSK — runtime world initialization')}")
    snapshot = system.runtime.snapshot()
    system.persistence.persist_snapshot(snapshot)
    print(f"    [ok] Runtime: {len(snapshot.entities)} entities, {len(snapshot.relations)} relations")
    summary["steps"]["3_oosk"] = {"snapshot_id": snapshot.id}

    # ── Step 4: Spawn Synthetic Agents ────────────────────────────────
    print(f"\n{step_label(4, 'AGENTS — synthetic player spawning')}")
    agents_result = system.simulation.spawn_agents(
        count=args.agent_count,
        styles=["trader", "crafter", "flipper", "raider", "collector"],
    )
    print(f"    [ok] Spawned {agents_result.get('count', args.agent_count)} agents")
    summary["steps"]["4_agents"] = {"count": agents_result.get("count")}

    # ── Step 5: Simulate Interactions ──────────────────────────────────
    print(f"\n{step_label(5, 'SIMULATION — world interactions')}")
    system.simulation.run(ticks=args.sim_ticks)
    sim_world = system.simulation.snapshot()
    interactions = sim_world.get("interaction_count", 0)
    print(f"    [ok] {args.sim_ticks} ticks, {interactions} interactions")
    summary["steps"]["5_simulation"] = {"ticks": args.sim_ticks, "interactions": interactions}

    # ── Step 6: Economy Dynamics ──────────────────────────────────────
    print(f"\n{step_label(6, 'ECONOMY — price evolution')}")
    economy_labels = system.simulation.generate_labels()
    label_count = len(economy_labels)
    print(f"    [ok] {label_count} economy labels generated")
    summary["steps"]["6_economy"] = {"labels": label_count}

    # ── Step 7: BORS Labeling ─────────────────────────────────────────
    print(f"\n{step_label(7, 'BORS — decision labeling')}")
    reasoning = system.simulation.build_reasoning()
    reasoning_count = len(reasoning)
    print(f"    [ok] {reasoning_count} reasoning chains built")
    summary["steps"]["7_bors"] = {"reasoning_chains": reasoning_count}

    # ── Step 8: Build Reasoning Graphs ────────────────────────────────
    print(f"\n{step_label(8, 'REASONING — graph generation')}")
    sim_dataset = system.simulation.export_dataset()
    dataset_version = sim_dataset.get("version", sim_dataset.get("dataset", {}).get("version", "unknown"))
    print(f"    [ok] Dataset v{dataset_version}")
    summary["steps"]["8_reasoning"] = {"version": dataset_version}

    # ── Step 9 & 10: Train + Repeat Loop ──────────────────────────────
    rounds = args.rounds
    trained = []
    for rnd in range(1, rounds + 1):
        print(f"\n{step_label(9 if rnd == 1 else 10, f'TRAINING — model round {rnd}/{rounds}')}")
        train_body = {
            "model_type": args.model_type,
            "dataset_type": args.dataset_type,
            "graph": sim_dataset,
            "simulation_steps": [{"type": "noop"}],
            "risk_score": max(0.1, 0.5 - rnd * 0.05),
        }
        train_result = system.run_training_pipeline(train_body)
        artifact = train_result.get("model", train_result.get("artifact", {}))
        metrics = train_result.get("metrics", {})
        status = artifact.get("status", "unknown")
        model_id = artifact.get("id", "?")
        qual = metrics.get("estimated_quality", 0)
        print(f"    {'[ok]' if status == 'trained' else '[!]'} Round {rnd}: model={model_id[:12]} quality={qual:.3f} status={status}")
        trained.append({"round": rnd, "id": model_id, "quality": qual, "status": status})

        if rnd < rounds:
            print("    -> Re-seeding simulation for next round...")
            system.simulation.reset(seed=rnd + 1)
            system.simulation.spawn_agents(count=args.agent_count)
            system.simulation.run(ticks=max(1, args.sim_ticks // rounds))

    elapsed = time.time() - total_start
    summary["models"] = trained
    summary["elapsed_seconds"] = round(elapsed, 2)
    summary["final_quality"] = max((m["quality"] for m in trained), default=0)
    summary["model_count"] = len(trained)

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{color('=' * 64, '96')}")
    print(color(f"  BOOTSTRAP COMPLETE  —  {elapsed:.1f}s", "92"))
    print(color(f"  Models trained: {len(trained)}", "92"))
    print(color(f"  Best quality:   {summary['final_quality']:.3f}", "92"))
    print(color(f"  Dataset ver:    {dataset_version}", "92"))
    print(color("=" * 64, "96"))

    _write_report(summary, args)
    return summary


def _seed_synthetic(system: Any, account_name: str) -> dict[str, Any]:
    """Seed the runtime with synthetic data when no real API key is available."""
    account_id = f"account:{account_name}"
    seed_entities = [
        {"id": account_id, "type": "account_snapshot", "properties": {"account_name": account_name, "age_hours": 10000, "total_items": 42}},
        {"id": "currency:gold", "type": "Currency", "properties": {"name": "Gold", "value": 500000, "gold": 500}},
        {"id": "currency:mystic_coin", "type": "Currency", "properties": {"name": "Mystic Coin", "value": 150, "gold": 0}},
        {"id": "item:ecto:0", "type": "Item", "properties": {"item_id": 19721, "count": 500, "location": "Bank", "tradable": True}},
        {"id": "item:mithril:0", "type": "Item", "properties": {"item_id": 19684, "count": 2000, "location": "Bank", "tradable": True}},
        {"id": "item:elder_wood:0", "type": "Item", "properties": {"item_id": 19700, "count": 1500, "location": "Bank", "tradable": True}},
        {"id": "character:SeedHero", "type": "Character", "properties": {"name": "SeedHero", "profession": "Guardian", "level": 80, "playtime_hours": 500}},
    ]
    seed_relations = [
        {"source": account_id, "target": "currency:gold", "relation_type": "owns", "weight": 1.0},
        {"source": account_id, "target": "currency:mystic_coin", "relation_type": "owns", "weight": 1.0},
        {"source": account_id, "target": "item:ecto:0", "relation_type": "owns", "weight": 1.0},
        {"source": account_id, "target": "item:mithril:0", "relation_type": "owns", "weight": 1.0},
        {"source": account_id, "target": "item:elder_wood:0", "relation_type": "owns", "weight": 1.0},
        {"source": account_id, "target": "character:SeedHero", "relation_type": "owns", "weight": 1.0},
    ]
    for entity in seed_entities:
        system.runtime.add_entity(entity)
    for relation in seed_relations:
        system.runtime.add_relation(relation)
    return {"summary": {"account_id": account_id, "entities": len(seed_entities), "relations": len(seed_relations)}}


def _write_report(summary: dict[str, Any], args: argparse.Namespace) -> None:
    report_dir = Path("data/bootstrap_reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"bootstrap_{ts}.json"
    path.write_text(
        json.dumps({
            "timestamp": ts,
            "mode": args.mode,
            "rounds": args.rounds,
            "account": args.account_name or "bootstrap_seed",
            "summary": summary,
        }, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"\n  Report: {path}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GW2 Expert AI Bootstrap Pipeline", formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["online", "synthetic"], default="synthetic", help="Online (real API key) or synthetic seed")
    p.add_argument("--api-key", default="", help="GW2 API key (for online mode)")
    p.add_argument("--account-name", default="bootstrap_seed", help="Account label for seed data")
    p.add_argument("--rounds", type=int, default=3, help="Number of training rounds (default: 3)")
    p.add_argument("--agent-count", type=int, default=5, help="Synthetic agents per round (default: 5)")
    p.add_argument("--sim-ticks", type=int, default=20, help="Simulation ticks per round (default: 20)")
    p.add_argument("--model-type", default="expert_reasoner", help="Model type for trainer")
    p.add_argument("--dataset-type", default="full_production", help="Dataset type version tag")
    p.add_argument("--docker", action="store_true", help="Also start Docker backend services")
    return p.parse_args(argv)


def main() -> None:
    args = _parse_args()
    banner()

    if args.docker:
        print(color("\n  -> Starting Docker backend services...", "93"))
        import subprocess
        compose_file = Path(__file__).resolve().parent.parent / "docker-compose.expert-ai.yml"
        r = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d", "--wait"],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            print(color("  [ok] Docker services started", "92"))
        else:
            print(color(f"  [!] Docker start: {r.stderr.strip() or 'see docker ps'}", "93"))

    run_bootstrap(args)


if __name__ == "__main__":
    main()
