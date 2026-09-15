"""Build Knowledge Base and Recommendation Engine."""

import logging
from typing import Any

from ..models import AccountBuildReadiness, BuildGearRequirement, BuildTemplate
from ..ontology import object_store as ontology_store
from ..ontology.build_trust import evaluate_build_source_freshness, get_build_recommendation_confidence

logger = logging.getLogger("gw2.builds")

CURATED_BUILDS: list[BuildTemplate] = [
    BuildTemplate(
        build_id="sc_dh",
        source="snowcrows",
        name="Dragonhunter (Power)",
        profession="Guardian",
        elite_specialization="Dragonhunter",
        game_mode="raid",
        role="dps",
        difficulty="easy",
        patch_version="2025.06",
        gear=[
            BuildGearRequirement(slot="Greatsword", item_type="Weapon", stat_combo="Berserker"),
            BuildGearRequirement(slot="Sword/Focus", item_type="Weapon", stat_combo="Berserker"),
            BuildGearRequirement(slot="Helm", item_type="Armor", stat_combo="Berserker"),
            BuildGearRequirement(slot="Shoulders", item_type="Armor", stat_combo="Berserker"),
            BuildGearRequirement(slot="Coat", item_type="Armor", stat_combo="Berserker"),
        ],
    ),
    BuildTemplate(
        build_id="sc_hfb",
        source="snowcrows",
        name="Firebrand (Heal)",
        profession="Guardian",
        elite_specialization="Firebrand",
        game_mode="strike",
        role="heal",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Mace/Shield", item_type="Weapon", stat_combo="Harrier"), BuildGearRequirement(slot="Staff", item_type="Weapon", stat_combo="Harrier")],
    ),
    BuildTemplate(
        build_id="sc_chrono",
        source="snowcrows",
        name="Chronomancer (BoonDPS)",
        profession="Mesmer",
        elite_specialization="Chronomancer",
        game_mode="raid",
        role="boon_dps",
        difficulty="hard",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Sword/Sword", item_type="Weapon", stat_combo="Berserker"), BuildGearRequirement(slot="Staff", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="mb_mech",
        source="metabattle",
        name="Mechanist (Power)",
        profession="Engineer",
        elite_specialization="Mechanist",
        game_mode="open_world",
        role="dps",
        difficulty="easy",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Rifle", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="sc_virt",
        source="snowcrows",
        name="Virtuoso (Power)",
        profession="Mesmer",
        elite_specialization="Virtuoso",
        game_mode="raid",
        role="dps",
        difficulty="easy",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Dagger/Dagger", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="sc_herald",
        source="snowcrows",
        name="Herald (Power)",
        profession="Revenant",
        elite_specialization="Herald",
        game_mode="raid",
        role="boon_dps",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Sword/Sword", item_type="Weapon", stat_combo="Berserker"), BuildGearRequirement(slot="Staff", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="mb_ren",
        source="metabattle",
        name="Renegade (Condi)",
        profession="Revenant",
        elite_specialization="Renegade",
        game_mode="fractal",
        role="alac",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Shortbow", item_type="Weapon", stat_combo="Viper")],
    ),
    BuildTemplate(
        build_id="sc_weaver",
        source="snowcrows",
        name="Weaver (Power)",
        profession="Elementalist",
        elite_specialization="Weaver",
        game_mode="raid",
        role="dps",
        difficulty="hard",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Sword/Dagger", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="sc_cata",
        source="snowcrows",
        name="Catalyst (Power)",
        profession="Elementalist",
        elite_specialization="Catalyst",
        game_mode="strike",
        role="dps",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Hammer", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="sc_daredevil",
        source="snowcrows",
        name="Daredevil (Power)",
        profession="Thief",
        elite_specialization="Daredevil",
        game_mode="raid",
        role="dps",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Staff", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="mb_specter",
        source="metabattle",
        name="Specter (Alacrity)",
        profession="Thief",
        elite_specialization="Specter",
        game_mode="fractal",
        role="alac",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Pistol/Dagger", item_type="Weapon", stat_combo="Viper")],
    ),
    BuildTemplate(
        build_id="sc_berserker",
        source="snowcrows",
        name="Berserker (Power)",
        profession="Warrior",
        elite_specialization="Berserker",
        game_mode="raid",
        role="dps",
        difficulty="easy",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Greatsword", item_type="Weapon", stat_combo="Berserker"), BuildGearRequirement(slot="Axe/Axe", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="sc_bladesworn",
        source="snowcrows",
        name="Bladesworn (Power)",
        profession="Warrior",
        elite_specialization="Bladesworn",
        game_mode="strike",
        role="dps",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Gunsaber", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="sc_soulbeast",
        source="snowcrows",
        name="Soulbeast (Power)",
        profession="Ranger",
        elite_specialization="Soulbeast",
        game_mode="raid",
        role="dps",
        difficulty="easy",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Longbow", item_type="Weapon", stat_combo="Berserker"), BuildGearRequirement(slot="Axe/Axe", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="mb_untamed",
        source="metabattle",
        name="Untamed (Power)",
        profession="Ranger",
        elite_specialization="Untamed",
        game_mode="open_world",
        role="dps",
        difficulty="easy",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Greatsword", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="sc_scourge",
        source="snowcrows",
        name="Scourge (Condi)",
        profession="Necromancer",
        elite_specialization="Scourge",
        game_mode="raid",
        role="dps",
        difficulty="easy",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Scepter/Dagger", item_type="Weapon", stat_combo="Viper"), BuildGearRequirement(slot="Staff", item_type="Weapon", stat_combo="Viper")],
    ),
    BuildTemplate(
        build_id="sc_harbinger",
        source="snowcrows",
        name="Harbinger (Condi)",
        profession="Necromancer",
        elite_specialization="Harbinger",
        game_mode="strike",
        role="dps",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Pistol/Dagger", item_type="Weapon", stat_combo="Viper")],
    ),
    BuildTemplate(
        build_id="sc_spellbreaker",
        source="snowcrows",
        name="Spellbreaker (Power)",
        profession="Warrior",
        elite_specialization="Spellbreaker",
        game_mode="raid",
        role="dps",
        difficulty="medium",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Dagger/Axe", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="mb_willbender",
        source="metabattle",
        name="Willbender (Power)",
        profession="Guardian",
        elite_specialization="Willbender",
        game_mode="open_world",
        role="dps",
        difficulty="easy",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Sword/Sword", item_type="Weapon", stat_combo="Berserker")],
    ),
    BuildTemplate(
        build_id="sc_mirage",
        source="snowcrows",
        name="Mirage (Condi)",
        profession="Mesmer",
        elite_specialization="Mirage",
        game_mode="raid",
        role="dps",
        difficulty="hard",
        patch_version="2025.06",
        gear=[BuildGearRequirement(slot="Axe/Axe", item_type="Weapon", stat_combo="Viper")],
    ),
]


_builds_registered = False


def _register_builds_in_ontology() -> None:
    global _builds_registered
    if _builds_registered:
        return
    for b in CURATED_BUILDS:
        existing = ontology_store.get_objects_by_class("build")
        if any(o.properties.get("build_id") == b.build_id for o in existing):
            continue
        props = {
            "build_id": b.build_id,
            "source": b.source,
            "name": b.name,
            "profession": b.profession,
            "elite_specialization": b.elite_specialization,
            "game_mode": b.game_mode,
            "role": b.role,
            "difficulty": b.difficulty,
            "patch_version": b.patch_version,
            "source_url": b.source_url,
            "review_status": "reviewed",
        }
        ontology_store.register_object(
            class_name="build",
            properties=props,
            privacy_scope="shared",
        )
    _builds_registered = True


def get_all_builds() -> list[BuildTemplate]:
    _register_builds_in_ontology()
    return CURATED_BUILDS


def get_build(build_id: str) -> BuildTemplate | None:
    return next((b for b in CURATED_BUILDS if b.build_id == build_id), None)


def _get_account_professions(contents: Any) -> set[str]:
    """Extract profession names from account characters."""
    profs = set()
    for ch in contents.characters or []:
        if isinstance(ch, dict):
            profs.add(ch.get("profession", ""))
    return profs


def _parse_build_gear_items(build: BuildTemplate) -> set[int]:
    """Extract item IDs from build gear requirements."""
    return set(g.required_item_id for g in build.gear if g.required_item_id > 0)


async def calculate_readiness(api_key: str, build_id: str) -> AccountBuildReadiness:
    from ..analyzer import fetch_all

    build = get_build(build_id)
    if not build:
        raise ValueError(f"Build {build_id} not found")

    contents = await fetch_all(api_key)
    account_profs = _get_account_professions(contents)
    prof_match = build.profession in account_profs

    if not prof_match:
        return AccountBuildReadiness(
            account_name=contents.account_name or "",
            build_id=build_id,
            build_name=build.name,
            readiness_score=0.0,
            gear_completion_percent=0.0,
            trait_completion_percent=0.0,
            missing_cost=0,
            missing_items_count=0,
            profession_match=False,
            confidence=0.65,
            data_sources=["gw2_account_characters", "curated_build_templates"],
            risk_reason="Profession does not match this curated build; readiness is intentionally zero.",
        )

    owned_items: set[int] = set()
    for ch in contents.characters or []:
        if isinstance(ch, dict):
            for eq in ch.get("equipment") or []:
                if isinstance(eq, dict) and eq.get("id"):
                    owned_items.add(eq["id"])
            for bag in ch.get("bags") or []:
                if isinstance(bag, dict):
                    for slot in bag.get("inventory") or []:
                        if isinstance(slot, dict) and slot.get("id"):
                            owned_items.add(slot["id"])

    build_items = _parse_build_gear_items(build)
    matched = sum(1 for i in build_items if i in owned_items) if build_items else 1
    total = len(build_items) if build_items else 1
    gear_pct = round(matched / total * 100, 1)

    missing_cost = (total - matched) * 50000  # rough estimate per item

    score = round(0.50 * gear_pct / 100 + 0.30 * (1 if prof_match else 0) + 0.20 * (matched / max(total, 1)), 2)
    confidence = round(min(0.55 + score * 0.40, 0.95), 2)
    risk_reason = (
        "Build recommendation uses detected equipment plus curated template requirements; traits, relics, and player skill still need review."
        if total - matched
        else "Detected gear fully matches the curated build item requirements available in this template."
    )

    acct_name = contents.account_name or ""
    readiness_obj = AccountBuildReadiness(
        account_name=acct_name,
        build_id=build_id,
        build_name=build.name,
        readiness_score=min(score, 1.0),
        gear_completion_percent=gear_pct,
        trait_completion_percent=80.0 if prof_match else 0.0,
        missing_cost=missing_cost,
        missing_items_count=total - matched,
        profession_match=prof_match,
        confidence=confidence,
        data_sources=["gw2_account_characters", "gw2_account_equipment", "curated_build_templates"],
        risk_reason=risk_reason,
    )

    try:
        r_props = {
            "build_id": build_id,
            "build_name": build.name,
            "readiness_score": min(score, 1.0),
            "gear_completion": gear_pct,
            "profession_match": prof_match,
            "confidence": confidence,
            "source": build.source,
        }
        r_obj = ontology_store.register_object(
            class_name="build_readiness",
            account_name=acct_name,
            properties=r_props,
            privacy_scope="private",
        )
        build_objs = [o for o in ontology_store.get_objects_by_class("build") if o.properties.get("build_id") == build_id]
        if build_objs:
            ontology_store.register_relation(
                source_id=r_obj.object_id,
                target_id=build_objs[0].object_id,
                relation_type="evaluates",
                confidence=confidence,
            )
    except Exception as e:
        logger.warning("Ontology registration for build readiness failed (continuing): %s", e)

    return readiness_obj


async def get_recommendations(api_key: str) -> list[AccountBuildReadiness]:
    results = []
    for build in CURATED_BUILDS:
        try:
            freshness = evaluate_build_source_freshness(build)
            if freshness["recommendation_strength"] == "none":
                continue
            readiness = await calculate_readiness(api_key, build.build_id)
            if readiness.readiness_score > 0:
                confidence = get_build_recommendation_confidence(build)
                if confidence < readiness.confidence:
                    readiness.confidence = round(confidence, 2)
                freshness_info = f"source={build.source}, patch={build.patch_version}"
                if freshness.get("is_weak"):
                    freshness_info += ", stale_source"
                    readiness.risk_reason = f"{readiness.risk_reason} Build source may be stale ({freshness['days_old']} days old)."
                readiness.data_sources.append(f"build_freshness:{freshness_info}")
                results.append(readiness)
        except Exception as e:
            logger.warning("Failed to calculate readiness for %s: %s", build.build_id, e)
    results.sort(key=lambda r: r.readiness_score, reverse=True)
    return results
