"""Collect a bounded GW2 recipe sample and produce craft-vs-buy reports."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

from gw2_progression.advice import PlayerAdviceEngine
from gw2_progression.data_acquisition.contract import DataExpansionRecord
from gw2_progression.data_acquisition.expansion.horizontal import HorizontalExpander
from gw2_progression.data_acquisition.expansion.vertical import VerticalExpander
from gw2_progression.data_acquisition.opportunities import CraftProfitRanker
from gw2_progression.data_acquisition.persistence import DataExpansionStore
from gw2_progression.data_acquisition.registry.source_registry import SourceConfig, SourcePriority, SourceType


def main() -> int:
    args = _parse_args()
    result = run(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def run(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    store_path = out_dir / f"knowledge_ingest_{args.recipe_limit}_{run_id}.sqlite3"
    store = DataExpansionStore(store_path)
    source = SourceConfig(
        id=f"knowledge{args.recipe_limit}_recipes",
        type=SourceType.API,
        priority=SourcePriority.HIGH,
        frequency="manual",
        endpoint="/v2/recipes",
        metadata={"entity_type": "recipe"},
    )

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=args.timeout) as client:
        recipe_ids = _fetch_recipe_ids(client, args.recipe_limit)
        recipes = _fetch_id_chunks(client, "/v2/recipes", recipe_ids, args.chunk_size, args.rate_limit_seconds)
        item_ids = _collect_item_ids(recipes)
        items = _fetch_id_chunks(client, "/v2/items", sorted(item_ids), args.chunk_size, args.rate_limit_seconds)
        prices = _fetch_id_chunks(client, "/v2/commerce/prices", sorted(item_ids), args.chunk_size, args.rate_limit_seconds)
        listings = _fetch_id_chunks(client, "/v2/commerce/listings", sorted(item_ids), args.chunk_size, args.rate_limit_seconds)

    normalized = _normalized_payload(source.id, recipes, items, prices)
    vertical = VerticalExpander().expand(normalized, source)
    horizontal = HorizontalExpander().expand(vertical, source)
    records = _records_from_entities(horizontal["entities"], source=source, observed_at=time.time())
    store_result = store.write_records(records)
    ranking = CraftProfitRanker().rank(records, limit=args.ranking_limit, profitable_only=False)
    account_report = _account_feasibility_report(
        ranking=[row.to_dict() for row in ranking],
        base_report=horizontal,
        account_snapshot_path=Path(args.account_snapshot),
        run_id=run_id,
        recipe_limit=args.recipe_limit,
    )
    quality = _quality_report(
        run_id=run_id,
        recipe_limit=args.recipe_limit,
        recipes=recipes,
        item_ids=item_ids,
        items=items,
        prices=prices,
        listings=listings,
        records=records,
        ranking=[row.to_dict() for row in ranking],
        account_report=account_report,
        store_result=store_result,
    )

    ranking_path = out_dir / f"craft_vs_buy_ranking_{args.recipe_limit}_{run_id}.json"
    feasibility_path = out_dir / f"account_craft_feasibility_{args.recipe_limit}_{run_id}.json"
    quality_path = out_dir / f"coverage_quality_{args.recipe_limit}_{run_id}.json"
    ingest_path = out_dir / f"knowledge_ingest_{args.recipe_limit}_{run_id}.json"
    _write_json(ranking_path, _ranking_report(run_id, args.recipe_limit, item_ids, ranking, quality))
    _write_json(feasibility_path, account_report)
    _write_json(quality_path, quality)
    _write_json(
        ingest_path,
        {
            "run_id": run_id,
            "store_path": str(store_path),
            "ranking_path": str(ranking_path),
            "account_ranking_path": str(feasibility_path),
            "quality_path": str(quality_path),
            "account_snapshot_path": args.account_snapshot,
            "recipe_limit": args.recipe_limit,
            "recipe_ids": recipe_ids,
            "record_count": len(records),
            "store_result": store_result,
        },
    )

    advice = PlayerAdviceEngine().from_file(
        feasibility_path,
        context={
            "player_goal": args.player_goal,
            "account_stage": args.account_stage,
            "include_explanations": True,
            "report_language": "en",
            "llm_explanation_layer": "deterministic_template",
        },
    )
    advice_paths = advice.write(out_dir)

    return {
        "run_id": run_id,
        "recipe_limit": args.recipe_limit,
        "ranking_path": str(ranking_path),
        "feasibility_path": str(feasibility_path),
        "quality_path": str(quality_path),
        "ingest_path": str(ingest_path),
        "advice_paths": advice_paths,
        "quality_summary": quality["summary"],
    }


def _fetch_recipe_ids(client: httpx.Client, limit: int) -> list[int]:
    response = client.get("/v2/recipes")
    response.raise_for_status()
    ids = response.json()
    if not isinstance(ids, list):
        raise RuntimeError("/v2/recipes did not return an id list")
    return [int(item_id) for item_id in ids[:limit]]


def _fetch_id_chunks(client: httpx.Client, endpoint: str, ids: list[int], chunk_size: int, delay: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for start in range(0, len(ids), max(1, chunk_size)):
        chunk = ids[start : start + chunk_size]
        if not chunk:
            continue
        response = client.get(endpoint, params={"ids": ",".join(str(item_id) for item_id in chunk)})
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            rows.extend(row for row in payload if isinstance(row, dict))
        elif isinstance(payload, dict):
            rows.append(payload)
        if delay > 0:
            time.sleep(delay)
    return rows


def _collect_item_ids(recipes: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for recipe in recipes:
        output = recipe.get("output_item_id")
        if output:
            ids.add(int(output))
        for ingredient in recipe.get("ingredients", []):
            if isinstance(ingredient, dict) and ingredient.get("item_id"):
                ids.add(int(ingredient["item_id"]))
    return ids


def _normalized_payload(source_id: str, recipes: list[dict[str, Any]], items: list[dict[str, Any]], prices: list[dict[str, Any]]) -> dict[str, Any]:
    item_by_id = {int(item["id"]): item for item in items if item.get("id") is not None}
    price_by_id = {int(price["id"]): price for price in prices if price.get("id") is not None}
    entities: list[dict[str, Any]] = []
    for recipe in recipes:
        recipe_id = int(recipe["id"])
        output_id = int(recipe.get("output_item_id") or 0)
        item = item_by_id.get(output_id, {})
        entities.append({
            "id": f"{source_id}:{recipe_id}",
            "type": "recipe",
            "name": item.get("name") or f"Recipe {recipe_id}",
            "properties": {
                "native_id": recipe_id,
                "output_item_id": output_id,
                "output_item_count": int(recipe.get("output_item_count") or 1),
                "disciplines": recipe.get("disciplines", []),
                "min_rating": recipe.get("min_rating", 0),
                "flags": recipe.get("flags", []),
                "ingredients": recipe.get("ingredients", []),
            },
            "source": source_id,
            "confidence": 0.95,
            "lineage": [source_id, "gw2_api_recipes"],
        })
    for item_id, item in item_by_id.items():
        entities.append({
            "id": f"item:{item_id}",
            "type": "item",
            "name": item.get("name", str(item_id)),
            "properties": {"native_id": item_id, **item},
            "source": "gw2_api_items",
            "confidence": 0.95,
            "lineage": ["gw2_api_items"],
        })
    for item_id, price in price_by_id.items():
        entities.append({
            "id": f"price:{item_id}",
            "type": "market_price_snapshot",
            "name": f"Price {item_id}",
            "properties": {"native_id": item_id, **price},
            "source": "gw2_api_commerce_prices",
            "confidence": 0.9,
            "lineage": ["gw2_api_commerce_prices"],
        })
    return {"entities": entities, "relations": [], "source": source_id, "observed_at": time.time()}


def _records_from_entities(entities: list[dict[str, Any]], *, source: SourceConfig, observed_at: float) -> list[DataExpansionRecord]:
    return [
        DataExpansionRecord.from_entity(
            entity,
            source_id=source.id,
            source_type=source.type.value,
            collected_at=observed_at,
            observed_at=float(entity.get("timestamp", observed_at) or observed_at),
            confidence=source.confidence_default,
            privacy_scope="public",
        )
        for entity in entities
        if isinstance(entity, dict) and entity.get("id")
    ]


def _account_feasibility_report(
    *,
    ranking: list[dict[str, Any]],
    base_report: dict[str, Any],
    account_snapshot_path: Path,
    run_id: str,
    recipe_limit: int,
) -> dict[str, Any]:
    holdings = _owned_item_counts(account_snapshot_path)
    opportunities = []
    opportunity_by_entity = {entity.get("id"): entity for entity in base_report.get("entities", []) if entity.get("type") == "craft_profit_opportunity"}
    for row in ranking:
        entity = opportunity_by_entity.get(row["entity_id"], {})
        props = entity.get("properties", {}) if isinstance(entity, dict) else {}
        opportunity = dict(row)
        opportunity.update({
            "output_item_name": row.get("name", ""),
            "recipe_native_id": props.get("recipe_native_id"),
            "craft_revenue_sell": props.get("craft_revenue_sell", 0),
            "tp_fee_adjusted_revenue": props.get("tp_fee_adjusted_revenue", 0),
            "profitable": int(row.get("net_profit", 0)) > 0,
            "base_score": row.get("score", 0),
            "account_feasibility": _feasibility(props.get("ingredient_item_ids", []), _recipe_requirements(base_report, props.get("recipe_id")), holdings),
        })
        opportunity["account_executable_score"] = _account_score(opportunity)
        opportunities.append(opportunity)
    executable = [row for row in opportunities if row["account_feasibility"]["craftable_now"] > 0]
    profitable = [row for row in opportunities if row.get("profitable")]
    executable_profitable = [row for row in executable if row.get("profitable")]
    blocked_profitable = [row for row in profitable if row["account_feasibility"]["craftable_now"] <= 0]
    return {
        "run_id": run_id,
        "account_name": _account_name(account_snapshot_path),
        "source_snapshot": str(account_snapshot_path),
        "recipe_limit": recipe_limit,
        "opportunity_count": len(opportunities),
        "profitable_count": len(profitable),
        "executable_count": len(executable),
        "executable_profitable_count": len(executable_profitable),
        "holding_summary": {"unique_item_ids": len(holdings), "total_item_count": sum(holdings.values())},
        "top_all": sorted(opportunities, key=lambda row: (row["base_score"], row["net_profit"]), reverse=True)[:100],
        "top_executable": sorted(executable, key=lambda row: (row["account_executable_score"], row["net_profit"]), reverse=True)[:100],
        "top_executable_profitable": sorted(executable_profitable, key=lambda row: (row["account_executable_score"], row["net_profit"]), reverse=True)[:100],
        "blocked_profitable_lowest_missing": sorted(blocked_profitable, key=lambda row: (row["account_feasibility"]["missing_total_count"], -row["net_profit"]))[:100],
    }


def _recipe_requirements(base_report: dict[str, Any], recipe_id: str | None) -> list[dict[str, Any]]:
    if not recipe_id:
        return []
    for entity in base_report.get("entities", []):
        if entity.get("id") == recipe_id:
            ingredients = entity.get("properties", {}).get("ingredients", [])
            return ingredients if isinstance(ingredients, list) else []
    return []


def _feasibility(ingredient_ids: list[Any], requirements: list[dict[str, Any]], holdings: dict[str, int]) -> dict[str, Any]:
    rows = []
    craftable_limits = []
    for requirement in requirements:
        item_id = str(requirement.get("item_id"))
        required = int(requirement.get("count") or 1)
        owned = int(holdings.get(item_id, 0))
        missing = max(0, required - owned)
        rows.append({"item_id": item_id, "required": required, "owned": owned, "missing": missing, "satisfied": missing == 0})
        if required > 0:
            craftable_limits.append(owned // required)
    missing_total = sum(row["missing"] for row in rows)
    craftable = min(craftable_limits) if craftable_limits else 0
    return {
        "craftable_now": craftable,
        "all_ingredients_satisfied": missing_total == 0 and bool(rows),
        "missing_total_count": missing_total,
        "requirements": rows,
        "ingredient_item_ids": [str(item_id) for item_id in ingredient_ids],
    }


def _owned_item_counts(path: Path) -> dict[str, int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    for section in ("materials", "bank", "commerce_current_buys", "commerce_current_sells"):
        value = raw.get(section, [])
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("id") is not None:
                    counts[str(item["id"])] += int(item.get("count", item.get("value", 0)) or 0)
    for character in raw.get("characters", []):
        if not isinstance(character, dict):
            continue
        for bag in character.get("bags", []) or []:
            if not isinstance(bag, dict):
                continue
            for item in bag.get("inventory", []) or []:
                if isinstance(item, dict) and item.get("id") is not None:
                    counts[str(item["id"])] += int(item.get("count", 1) or 0)
    return dict(counts)


def _account_name(path: Path) -> str:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return str(raw.get("account", {}).get("name") or "unknown")


def _account_score(row: dict[str, Any]) -> float:
    feasibility = row.get("account_feasibility", {})
    craftable = int(feasibility.get("craftable_now") or 0)
    missing = int(feasibility.get("missing_total_count") or 0)
    return round(float(row.get("base_score", 0)) + min(craftable, 500) * 0.05 - missing * 3.0, 4)


def _ranking_report(run_id: str, recipe_limit: int, item_ids: set[int], ranking: list[Any], quality: dict[str, Any]) -> dict[str, Any]:
    rows = [row.to_dict() for row in ranking]
    return {
        "run_id": run_id,
        "ranking_policy": "dedupe by output_item_id + recipe_native_id, sorted by net_profit + roi*100 + profit_per_output*0.25",
        "recipe_limit": recipe_limit,
        "recipe_count": quality["summary"]["recipe_count"],
        "unique_item_count": len(item_ids),
        "opportunity_count": quality["summary"]["opportunity_count"],
        "profitable_count": quality["summary"]["profitable_count"],
        "top_all": rows,
    }


def _quality_report(**kwargs: Any) -> dict[str, Any]:
    records: list[DataExpansionRecord] = kwargs["records"]
    ranking: list[dict[str, Any]] = kwargs["ranking"]
    account_report = kwargs["account_report"]
    entity_types = Counter(record.entity_type for record in records)
    missing_price_item_count = len(kwargs["item_ids"]) - len({int(row["id"]) for row in kwargs["prices"] if row.get("id") is not None})
    craft_incomplete = sum(
        1
        for record in records
        if record.entity_type == "merged_asset"
        and record.normalized_payload.get("properties", {}).get("has_recipe")
        and not record.normalized_payload.get("properties", {}).get("craft_cost_complete")
    )
    return {
        "run_id": kwargs["run_id"],
        "recipe_limit": kwargs["recipe_limit"],
        "summary": {
            "recipe_count": len(kwargs["recipes"]),
            "unique_item_count": len(kwargs["item_ids"]),
            "item_detail_count": len(kwargs["items"]),
            "price_count": len(kwargs["prices"]),
            "listing_count": len(kwargs["listings"]),
            "record_count": len(records),
            "opportunity_count": len([record for record in records if record.entity_type == "craft_profit_opportunity"]),
            "profitable_count": len([row for row in ranking if row.get("net_profit", 0) > 0]),
            "executable_profitable_count": account_report.get("executable_profitable_count", 0),
            "missing_price_item_count": max(0, missing_price_item_count),
            "craft_cost_incomplete_count": craft_incomplete,
        },
        "entity_types": dict(entity_types),
        "store_result": kwargs["store_result"],
        "recommendation": "increase sample size if missing_price_item_count and craft_cost_incomplete_count stay low; keep chunked collection for API safety",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect bounded GW2 recipe knowledge and generate craft-vs-buy reports.")
    parser.add_argument("--recipe-limit", type=int, default=500)
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--rate-limit-seconds", type=float, default=0.15)
    parser.add_argument("--ranking-limit", type=int, default=500)
    parser.add_argument("--base-url", default="https://api.guildwars2.com")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output-dir", default="data/knowledge_acquisition")
    parser.add_argument("--account-snapshot", default="data/account_snapshots/gw2-account-Netro.7195-pre_play-20260629-220210.json")
    parser.add_argument("--player-goal", default="gold_profit")
    parser.add_argument("--account-stage", default="developing")
    parser.add_argument("--run-id", default="")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
