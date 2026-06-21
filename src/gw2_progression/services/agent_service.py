"""Progression Agent — aggregated advice and weekly plan generator.

Supports optional LLM enhancement (OpenAI/Anthropic) for natural language advice.
Falls back to rule-based engine when no LLM API key is configured.
"""

import json
import logging
import os

import httpx

from ..models import ProgressionAdvice
from .build_service import get_recommendations
from .progression_service import CURATED_TEMPLATES, generate_goal_plan
from .tp_strategy_service import generate_signals

LLM_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
LLM_PROVIDER = "openai" if os.environ.get("OPENAI_API_KEY") else ("anthropic" if os.environ.get("ANTHROPIC_API_KEY") else None)

logger = logging.getLogger("gw2.agent")

AGENT_PROMPT = """You are GW2 Progression Advisor, a Guild Wars 2 account progression assistant.
Analyze the account data below and provide personalized advice.

Account Data:
- Name: {account_name}
- Wallet Gold: {wallet_gold}g
- Characters: {character_count}
- Total Skins Unlocked: {skin_count}

Goals (progress toward legendary/ascended items):
{goals_summary}

Trading Post Signals (sell/buy candidates, warnings):
{tp_signals}

Build Readiness (best build matches):
{builds_summary}

Respond with a JSON object (no markdown, no code fences) containing:
1. "summary": A 2-sentence overview of the account
2. "recommended_actions": Array of objects with "action", "target", "reason", "cost" (in copper)
3. "weekly_plan": Array of 7 objects with "day" ("Monday" through "Sunday") and "tasks" (array of strings)

Keep recommendations practical. Prioritize goals with highest completion percentage.
"""


async def _call_llm(prompt: str) -> dict | None:
    """Call the configured LLM provider with the prompt. Returns parsed JSON or None."""
    if not LLM_API_KEY:
        logger.info("No LLM API key configured, skipping LLM call")
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if LLM_PROVIDER == "openai":
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    },
                )
                if resp.status_code != 200:
                    logger.warning("OpenAI API error %d: %s", resp.status_code, resp.text[:200])
                    return None
                content = resp.json()["choices"][0]["message"]["content"]
            elif LLM_PROVIDER == "anthropic":
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": LLM_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "claude-3-5-haiku-latest",
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Anthropic API error %d: %s", resp.status_code, resp.text[:200])
                    return None
                content = resp.json()["content"][0]["text"]
            else:
                return None

        return _parse_llm_response(content)
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        return None


def _parse_llm_response(content: str) -> dict | None:
    """Parse LLM response, handling markdown code fences if present."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 0
        for i, line in enumerate(lines):
            if line.startswith("```"):
                start = i + 1
                break
        end = len(lines)
        for i in range(len(lines) - 1, start - 1, -1):
            if lines[i].strip().startswith("```"):
                end = i
                break
        text = "\n".join(lines[start:end]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %.200s", text)
        return None


async def generate_advice(api_key: str) -> ProgressionAdvice:
    from ..analyzer import fetch_all

    contents = await fetch_all(api_key)
    account_name = contents.account_name or "unknown"

    wallet_gold = 0
    for w in contents.wallet or []:
        if w.get("id") == 1:
            wallet_gold = w.get("value", 0)

    advice = ProgressionAdvice(
        summary=f"Account: {account_name}. Wallet: {wallet_gold // 10000}g. Analyzing goals and builds...",
    )

    actions: list[dict] = []
    weekly_plan: list[dict] = []

    # Try LLM first
    goals_summary = ""
    try:
        fastest_goal = None
        for t in CURATED_TEMPLATES[:5]:
            try:
                plan = await generate_goal_plan(api_key, t.template_id)
                if fastest_goal is None or (plan.total_completion_percent > fastest_goal.total_completion_percent and t.difficulty_level != "hard"):
                    fastest_goal = plan
            except Exception:
                continue

        if fastest_goal:
            goals_summary = (
                f"- Best goal: {fastest_goal.template_id} ({fastest_goal.total_completion_percent}% complete, "
                f"{fastest_goal.total_missing_cost // 10000}g remaining, {fastest_goal.total_owned_material_value // 10000}g owned)"
            )
    except Exception as e:
        logger.warning("Goal analysis failed: %s", e)

    tp_summary = ""
    try:
        signals = await generate_signals(account_name)
        sell_count = sum(1 for s in signals if s.signal_type == "sell_candidate")
        buy_count = sum(1 for s in signals if s.signal_type == "buy_candidate")
        warnings_count = sum(1 for s in signals if s.severity == "warning")
        tp_summary = f"- {sell_count} sell candidates, {buy_count} buy opportunities, {warnings_count} warnings"
    except Exception as e:
        logger.warning("Signal generation failed: %s", e)

    builds_summary = ""
    best_build = None
    try:
        recs = await get_recommendations(api_key)
        if recs:
            best_build = recs[0]
            builds_summary = (
                f"- Best build: {best_build.build_name} (readiness: {best_build.readiness_score:.0%}, missing: {best_build.missing_items_count} items, cost: {best_build.missing_cost // 10000}g)"
            )
    except Exception:
        pass

    prompt = AGENT_PROMPT.format(
        account_name=account_name,
        wallet_gold=wallet_gold // 10000,
        character_count=len(contents.characters or []),
        skin_count=contents.unlocked_skins_count or 0,
        goals_summary=goals_summary or "No goals analyzed",
        tp_signals=tp_summary or "No signals available",
        builds_summary=builds_summary or "No builds analyzed",
    )

    llm_result = await _call_llm(prompt)

    if llm_result and "recommended_actions" in llm_result:
        advice.summary = llm_result.get("summary", advice.summary)
        for a in llm_result.get("recommended_actions", []):
            actions.append(
                {
                    "action": a.get("action", "unknown"),
                    "target": a.get("target", ""),
                    "reason": a.get("reason", ""),
                    "cost": a.get("cost", 0),
                }
            )
        for day_entry in llm_result.get("weekly_plan", []):
            weekly_plan.append(
                {
                    "day": day_entry.get("day", "Unknown"),
                    "tasks": day_entry.get("tasks", []),
                }
            )
        logger.info("LLM advice generated for %s with %d actions", account_name, len(actions))
    else:
        # Fallback to rule-based engine
        logger.info("Using rule-based fallback for %s", account_name)
        if fastest_goal:
            actions.append(
                {
                    "action": "continue_goal",
                    "target": fastest_goal.template_id,
                    "reason": f"Goal '{fastest_goal.template_id}' is {fastest_goal.total_completion_percent}% complete, {fastest_goal.total_missing_cost // 10000}g remaining",
                    "cost": fastest_goal.total_missing_cost,
                }
            )

        try:
            signals = await generate_signals(account_name)
            sell_signals = [s for s in signals if s.signal_type == "sell_candidate" and s.quantity_owned >= 10]
            for s in sell_signals[:3]:
                actions.append(
                    {
                        "action": "sell_asset",
                        "target": str(s.item_id),
                        "reason": f"Item #{s.item_id}: {s.quantity_owned}x valued at {s.value_owned // 10000}g, not goal-protected",
                        "cost": s.value_owned,
                    }
                )
        except Exception as e:
            logger.warning("Fallback signal generation failed: %s", e)

        if best_build:
            actions.append(
                {
                    "action": "build_recommendation",
                    "target": best_build.build_id,
                    "reason": f"Best match build: {best_build.build_name} (readiness: {best_build.readiness_score:.0%}, missing: {best_build.missing_items_count} items)",
                    "cost": best_build.missing_cost,
                }
            )

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i, day in enumerate(days):
            entry = {"day": day, "tasks": []}
            if i < len(actions):
                entry["tasks"].append(actions[i]["reason"])
            if i == 0 and actions:
                entry["tasks"].append(f"Review {len(actions)} recommendations")
            weekly_plan.append(entry)

    if not actions:
        actions.append(
            {
                "action": "run_analysis",
                "target": "",
                "reason": "No actionable advice yet. Try creating a goal first.",
                "cost": 0,
            }
        )

    advice.recommended_actions = actions
    advice.weekly_plan = weekly_plan
    return advice


async def generate_weekly_plan(api_key: str) -> list[dict]:
    advice = await generate_advice(api_key)
    return advice.weekly_plan
