"""Character Lifecycle Trajectory Training — fetch real GW2 account data,
build per-character state snapshots, run item classification,
and lifecycle reconstruction with real item-aware path generation.

Usage:
    python scripts/lifecycle_character_training.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent))

API_KEY = os.environ.get("GW2_API_KEY", "")


def fetch_account() -> dict:
    from gw2_progression.analyzer import fetch_all

    if not API_KEY:
        raise RuntimeError("GW2_API_KEY is required for lifecycle character training")
    contents = asyncio.run(fetch_all(API_KEY))
    return {
        "contents": contents,
        "account_name": contents.account_name or "unknown",
    }


def build_character_states(account_data: dict) -> list[dict]:
    """Build per-character lifecycle state dicts from real account data."""
    contents = account_data["contents"]
    wallet = {str(c.get("id", 0)): c.get("value", 0) for c in (contents.wallet or [])}
    gold = wallet.get("1", 0)
    achievements = [
        {
            "id": a.get("id"),
            "current": a.get("current", 0),
            "max": a.get("max", 0),
            "done": a.get("done", False),
        }
        for a in (contents.achievements or [])
    ]
    achievement_ids_done = [a["id"] for a in achievements if a.get("done")]

    char_states = []
    for char in (contents.characters or []):
        char_name = char.get("name", "unknown")
        profession = char.get("profession", "Unknown")
        level = char.get("level", 0)

        inventory: dict[str, int] = {}
        for bag in (char.get("bags") or char.get("equipment_packed") or char.get("inventory") or []):
            if isinstance(bag, dict):
                for slot in (bag.get("inventory") or bag.get("items") or bag.get("slots") or []):
                    if isinstance(slot, dict) and slot.get("id"):
                        iid = str(slot["id"])
                        inventory[iid] = inventory.get(iid, 0) + slot.get("count", 1)
            elif isinstance(bag, list):
                for slot in bag:
                    if isinstance(slot, dict) and slot.get("id"):
                        iid = str(slot["id"])
                        inventory[iid] = inventory.get(iid, 0) + slot.get("count", 1)

        equipment = char.get("equipment", [])
        if isinstance(equipment, list):
            for eq in equipment:
                if isinstance(eq, dict) and eq.get("id"):
                    iid = str(eq["id"])
                    inventory[iid] = inventory.get(iid, 0) + 1

        state = {
            "character": char_name,
            "profession": profession,
            "level": level,
            "inventory": inventory,
            "items": list(inventory.keys()),
            "gold": gold,
            "market": {
                cid: {"price": val}
                for cid, val in wallet.items()
            },
            "achievements": achievement_ids_done,
            "created": char.get("created", ""),
            "deaths": char.get("deaths", 0),
            "age_hours": char.get("age", ""),
        }
        char_states.append(state)

    return char_states


def run_lifecycle_reconstruction(char_states: list[dict]) -> dict:
    from gw2_progression.lifecycle.core.engine import LifecycleEngine

    engine = LifecycleEngine()
    results = {}

    for state in char_states:
        char_name = state["character"]
        profession = state["profession"]
        level = state["level"]
        inventory_count = len(state["inventory"])
        achievement_done = len(state["achievements"])

        print(f"\n  ── {char_name} ({profession} Lv.{level}) ──")
        print(f"     Items: {inventory_count} unique | Achievements done: {achievement_done}")

        lifecycle_state = {
            "inventory": state["inventory"],
            "items": state["items"],
            "market": state["market"],
            "gold": state["gold"],
            "achievements": state["achievements"],
        }

        try:
            start = time.perf_counter()
            result = engine.reconstruct(lifecycle_state, max_depth=8)
            elapsed = (time.perf_counter() - start) * 1000

            paths = result.get("paths", [])
            total_paths = result.get("total_paths", 0)
            top_path = paths[0] if paths else None

            print(f"     Trajectories found: {total_paths} in {elapsed:.0f}ms")
            if top_path:
                print(f"     Top path score: {top_path['score']}")
                print(f"     Top path steps: {top_path['step_count']}")
                print(f"     Step types: {top_path.get('step_types', [])}")
                print(f"     Probability: {top_path.get('probability', 0):.4f}")
                print(f"     Consistency: {top_path.get('rule_consistency', 0):.4f}")
                vs = top_path.get("validation_summary", {})
                if vs:
                    print(f"     Action accuracy: {vs.get('accuracy', 0):.3f} "
                          f"(valid={vs.get('valid',0)}/{vs.get('total_actions',0)})")
                    rc = vs.get("recipe_crafts", 0)
                    if rc > 0:
                        print(f"     Recipe craft accuracy: {vs.get('recipe_accuracy', 0):.3f} "
                              f"({vs.get('valid_recipe_crafts',0)}/{rc})")

            results[char_name] = {
                "character": char_name,
                "profession": profession,
                "level": level,
                "inventory_items": inventory_count,
                "achievements_done": achievement_done,
                "total_paths": total_paths,
                "elapsed_ms": round(elapsed, 1),
                "top_score": top_path["score"] if top_path else None,
                "top_steps": top_path["step_count"] if top_path else 0,
                "top_probability": top_path.get("probability", 0) if top_path else 0,
                "top_consistency": top_path.get("rule_consistency", 0) if top_path else 0,
                "step_types": top_path.get("step_types", []) if top_path else [],
                "validation_summary": top_path.get("validation_summary", {}) if top_path else {},
                "paths": paths[:3] if paths else [],
            }

        except Exception as e:
            print(f"     ERROR: {e}")
            results[char_name] = {"character": char_name, "error": str(e)}

    return results


def print_summary(results: dict, char_states: list[dict]):
    print(f"\n{'=' * 72}")
    print("  CHARACTER LIFECYCLE TRAINING — SUMMARY")
    print(f"{'=' * 72}")

    total_chars = len(results)
    total_paths = sum(
        r.get("total_paths", 0) for r in results.values() if r.get("total_paths")
    )
    avg_items = sum(
        r.get("inventory_items", 0) for r in results.values() if "inventory_items" in r
    ) / max(total_chars, 1)

    print(f"\n  Account: {char_states[0]['character'] if char_states else 'N/A'}")
    print(f"  Characters processed: {total_chars}")
    print(f"  Total trajectories found: {total_paths}")
    print(f"  Avg inventory items/char: {avg_items:.0f}")

    print(f"\n  {'Character':<20} {'Profession':<14} {'Paths':>6} {'Score':>8} {'Steps':>6} {'Prob':>6} {'Consist':>8}")
    print(f"  {'─' * 72}")
    for state in char_states:
        name = state["character"]
        r = results.get(name, {})
        if r.get("error"):
            print(f"  {name:<20} {'ERROR':<14}")
        else:
            top_score = r.get('top_score')
            score_str = f"{top_score:>8.4f}" if top_score is not None else f"{'N/A':>8}"
            print(f"  {name:<20} {r.get('profession',''):<14} {r.get('total_paths',0):>6} "
                  f"{score_str} {r.get('top_steps',0):>6} "
                  f"{r.get('top_probability', 0):>6.3f} {r.get('top_consistency', 0):>8.4f}")

    # Detailed path output for top characters
    print(f"\n{'─' * 72}")
    print("  TOP TRAJECTORIES DETAIL")
    print(f"{'─' * 72}")
    for state in char_states[:5]:
        name = state["character"]
        r = results.get(name, {})
        paths = r.get("paths", [])
        if not paths:
            continue
        print(f"\n  >>> {name} — Top Trajectories:")
        for i, p in enumerate(paths):
            types = ", ".join(p.get("step_types", []))
            vs = p.get("validation_summary", {})
            val_str = ""
            if vs:
                val_str = f" | acc={vs.get('accuracy', 0):.3f}"
                rc = vs.get("recipe_crafts", 0)
                if rc > 0:
                    val_str += f" recipe_acc={vs.get('recipe_accuracy', 0):.3f}"
            print(f"      #{i+1}: score={p['score']:.4f} prob={p.get('probability',0):.4f} "
                  f"steps={p['step_count']} [{types}]{val_str}")
            for j, step in enumerate(p.get("steps", [])[:5]):
                label = " [recipe]" if step.get("recipe_sourced") else ""
                print(f"        Step {j+1}: {step.get('type', '?')}{label} "
                      f"item={step.get('item_id', '')} "
                      f"qty={step.get('quantity', step.get('count', ''))}")
                consumes = step.get("consumes", {})
                if consumes:
                    parts = [f"{iid}×{c}" for iid, c in consumes.items()]
                    print(f"             consumes: {', '.join(parts)}")
            if len(p.get("steps", [])) > 5:
                print(f"        ... +{len(p['steps']) - 5} more steps")

    print(f"\n{'=' * 72}")
    print("  TRAINING COMPLETE")
    print(f"{'=' * 72}\n")


def main():
    print("=" * 72)
    print("  GW2 CHARACTER LIFECYCLE TRAJECTORY TRAINING")
    print("  Fetching real account data → building character states")
    print("  → running backward inference → trajectory reconstruction")
    print("=" * 72)

    print("\n[1/3] Fetching account data from GW2 API...")
    account_data = fetch_account()
    name = account_data["account_name"]
    chars = len(account_data["contents"].characters or [])
    print(f"  Account: {name}")
    print(f"  Characters: {chars}")
    print(f"  Wallet: {len(account_data['contents'].wallet or [])} currencies")
    print(f"  Achievements: {len(account_data['contents'].achievements or [])} entries")
    print(f"  Bank: {len(account_data['contents'].bank or [])} slots")

    print("\n[2/3] Building character lifecycle states...")
    char_states = build_character_states(account_data)
    for s in char_states:
        print(f"  {s['character']:<20} {s['profession']:<14} Lv.{s['level']:<3} "
              f"items={len(s['inventory']):>3}  achievement_done={len(s['achievements']):>4}")
    print(f"  Total characters: {len(char_states)}")

    print("\n[2b/3] Classifying inventory items via GW2 API (caching enabled)...")
    all_item_ids = list({int(iid) for state in char_states for iid in state["items"] if iid.isdigit()})
    print(f"  Unique item IDs to classify: {len(all_item_ids)}")
    from gw2_progression.lifecycle.core.utils.item_categorizer import get_categorizer
    categorizer = get_categorizer()
    asyncio.run(categorizer.fetch_batch(all_item_ids))
    stats = categorizer.cache_stats()
    print(f"  Cache: {stats['in_memory']} in-memory, {stats['on_disk']} on-disk")

    print("\n  Item category breakdown per character:")
    for state in char_states:
        numeric_ids = [int(iid) for iid in state["items"] if iid.isdigit()]
        classified = categorizer.classify_items(numeric_ids)
        parts = [f"{cat}={len(ids)}" for cat, ids in sorted(classified.items())]
        print(f"  {state['character']:<20} {' | '.join(parts)}")

    print("\n[2c/3] Preheating all GW2 recipes via /v2/recipes (paginated)...")
    from gw2_progression.lifecycle.core.utils.recipe_resolver import get_recipe_resolver
    recipe_resolver = get_recipe_resolver()
    preheat_result = asyncio.run(recipe_resolver.preheat_all())
    print(f"  Preheat result: {json.dumps(preheat_result, indent=2)}")

    rc_stats = recipe_resolver.cache_stats()
    print(f"  Recipe cache: {rc_stats['in_memory']} in-memory, {rc_stats['on_disk']} on-disk")

    equipment_upgrade_ids = set()
    for state in char_states:
        numeric_ids = [int(iid) for iid in state["items"] if iid.isdigit()]
        classified = categorizer.classify_items(numeric_ids)
        for cat in ("equipment", "upgrade"):
            equipment_upgrade_ids.update(classified.get(cat, []))
    eq_ids = list(equipment_upgrade_ids)
    has_recipes = sum(1 for iid in eq_ids if recipe_resolver.has_recipe(iid))
    print(f"  Character items with recipes: {has_recipes} / {len(eq_ids)}")

    from gw2_progression.lifecycle.core.backward.dependency_solver import DependencySolver
    solver = DependencySolver()
    solver.register_account_dependencies()
    registered = solver.register_real_recipes_from_resolver(recipe_resolver, eq_ids)
    print(f"  Real recipes registered into DependencySolver: {registered}")

    print("\n[3/3] Running lifecycle reconstruction (backward inference + trajectory)...")
    results = run_lifecycle_reconstruction(char_states)

    print_summary(results, char_states)

    categorizer.close_sync()
    recipe_resolver.close_sync()


if __name__ == "__main__":
    main()
