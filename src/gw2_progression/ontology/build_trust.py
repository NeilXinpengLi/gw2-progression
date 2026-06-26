"""Build Fit Trust — source freshness, patch staleness, recommendation strength.

Every build recommendation must cite its source (SnowCrows, MetaBattle, etc.),
check patch freshness, and be downgraded when the source is stale or unreviewed.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from ..models import BuildTemplate

logger = logging.getLogger("gw2.ontology.build")

STALE_PATCH_DAYS = 120
WEAK_PATCH_DAYS = 60


def parse_patch_version(patch_version: str) -> datetime | None:
    parts = patch_version.split(".")
    if len(parts) >= 2:
        try:
            year = int(parts[0])
            month = int(parts[1])
            return datetime(year, month, 1, tzinfo=timezone.utc)
        except (ValueError, IndexError):
            pass
    try:
        return datetime.fromisoformat(patch_version.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def evaluate_build_source_freshness(build: BuildTemplate) -> dict[str, Any]:
    freshness = {
        "build_id": build.build_id,
        "source": build.source,
        "name": build.name,
        "patch_version": build.patch_version,
        "review_status": build.review_status,
        "days_old": None,
        "is_stale": False,
        "is_weak": False,
        "trust_level": "high",
        "recommendation_strength": "strong",
    }

    if build.review_status != "reviewed":
        freshness["trust_level"] = "low"
        freshness["recommendation_strength"] = "none"
        freshness["is_weak"] = True
        return freshness

    patch_dt = parse_patch_version(build.patch_version)
    if patch_dt is None:
        freshness["trust_level"] = "unknown"
        freshness["recommendation_strength"] = "weak"
        return freshness

    now = datetime.now(timezone.utc)
    days_old = (now - patch_dt).days
    freshness["days_old"] = days_old

    if days_old > STALE_PATCH_DAYS:
        freshness["is_stale"] = True
        freshness["trust_level"] = "low"
        freshness["recommendation_strength"] = "none"
    elif days_old > WEAK_PATCH_DAYS:
        freshness["is_weak"] = True
        freshness["trust_level"] = "medium"
        freshness["recommendation_strength"] = "weak"
    else:
        freshness["trust_level"] = "high"
        freshness["recommendation_strength"] = "strong"

    return freshness


def filter_recommendations_by_freshness(
    builds: list[BuildTemplate],
    max_results: int = 5,
) -> list[dict[str, Any]]:
    evaluated = []
    for build in builds:
        freshness = evaluate_build_source_freshness(build)
        evaluated.append(freshness)

    sorted_recs = sorted(
        evaluated,
        key=lambda r: (
            0 if r["recommendation_strength"] == "strong" else
            1 if r["recommendation_strength"] == "weak" else
            2
        ),
    )

    strong = [r for r in sorted_recs if r["recommendation_strength"] == "strong"]
    weak = [r for r in sorted_recs if r["recommendation_strength"] == "weak"]
    none_recs = [r for r in sorted_recs if r["recommendation_strength"] == "none"]

    result = strong[:max_results]
    remaining = max_results - len(result)
    if remaining > 0:
        result.extend(weak[:remaining])
    if len(result) < max_results:
        result.extend(none_recs[:max_results - len(result)])

    return result


def get_build_recommendation_confidence(build: BuildTemplate) -> float:
    freshness = evaluate_build_source_freshness(build)
    strength = freshness["recommendation_strength"]
    if strength == "strong":
        return 0.85
    elif strength == "weak":
        return 0.50
    return 0.0
