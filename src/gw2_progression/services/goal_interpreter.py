"""Goal Interpreter — parses natural language goals into structured plans.

Maps user text like "I want to finish Bolt" or "make gold this week"
into parsed goal objects with type, target, strategy, and constraints.
"""

import logging
import re
from difflib import SequenceMatcher

from ..models import GoalType, ParsedGoal
from .progression_service import CURATED_TEMPLATES

logger = logging.getLogger("gw2.goal_interpreter")

LEGENDARY_KEYWORDS = [
    "legendary", "leg", "bolt", "twilight", "sunrise", "nevermore",
    "astralaria", "bifrost", "frostfang", "incinerator", "aurora",
    "vision", "ad infinitum", "conflux", "coalescence", "exordium",
    "chuka", "xiquatl", "howler", "rodgort", "krait", "shining blade",
    "predator", "the", "shiver", "shark", "pharus", "verdarach", "claw",
    "wunderkammer", "flames of war", "flames of peace", "kamohoali'i",
]

BUILD_KEYWORDS = [
    "build", "gear", "equip", "raid", "fractal", "strike", "wvw",
    "pvp", "open world", "heal", "dps", "alac", "quick", "support",
    "condi", "power", "boon", "serkai", "snowcrows", "metabattle",
    "hardstuck", "bench", "rotation",
]

GOLD_KEYWORDS = [
    "gold", "money", "rich", "wealth", "profit", "farm", "income",
    "liquid", "sell", "trade", "flip", "tp", "trading",
]

INVENTORY_KEYWORDS = [
    "inventory", "clean", "organize", "bank", "materials", "storage",
    "space", "sort", "clear", "junk", "salvage",
]

WEEKLY_KEYWORDS = [
    "week", "weekly", "plan", "schedule", "routine", "daily",
    "7 day", "seven day",
]

STRATEGY_KEYWORDS = {
    "cheapest": ["cheap", "cheaper", "cheapest", "frugal", "budget", "minimum", "economy"],
    "fastest": ["faster", "fastest", "rush", "asap", "immediately", "speedrun"],
    "gold_first": [],
    "build_first": [],
    "low_effort": ["lazy", "easy", "simple", "casual", "chill", "relaxed", "effortless"],
    "balanced": [],
}


def _fuzzy_match(text: str, candidates: list[str], threshold: float = 0.5) -> str | None:
    """Find best fuzzy match for a keyword in text."""
    text_lower = text.lower()
    for candidate in candidates:
        if candidate.lower() in text_lower:
            return candidate
    for candidate in candidates:
        ratio = SequenceMatcher(None, text_lower, candidate.lower()).ratio()
        if ratio >= threshold:
            return candidate
    return None


def _extract_item_name(text: str) -> str:
    """Extract a potential item name from goal text."""
    # Match patterns like "finish Bolt", "make Twilight", "craft Sunrise"
    patterns = [
        r"(?:finish|make|craft|build|complete|get|work on|want)\s+(?:a|an|the|my|)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"(?:finish|make|craft|build|complete)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"(?:i want\s+(?:a|an|the)\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            name = m.group(1).strip()
            if len(name) > 2:
                return name
    return ""


def _detect_goal_type(text: str) -> GoalType:
    """Detect the goal type from text."""
    t = text.lower()
    # Gold detection first: "make gold", "farm gold", "earn money"
    if any(kw in t for kw in GOLD_KEYWORDS) and not any(kw in t for kw in ["finish", "complete", "craft", "work on"] + LEGENDARY_KEYWORDS):
        return GoalType.MAKE_GOLD
    # Weekly plan detection
    if any(kw in t for kw in WEEKLY_KEYWORDS):
        return GoalType.WEEKLY_PLAN
    # Legendary / craft detection
    if any(kw in t for kw in ["finish", "complete", "craft", "make", "work on"]):
        if any(kw in t for kw in ["legendary", "leg"] + [kw for kw in LEGENDARY_KEYWORDS if kw not in ["the", "leg"] if len(kw) > 3]):
            return GoalType.FINISH_LEGENDARY
        return GoalType.CRAFT_ITEM
    if any(kw in t for kw in BUILD_KEYWORDS):
        return GoalType.PREPARE_BUILD
    if any(kw in t for kw in INVENTORY_KEYWORDS):
        return GoalType.OPTIMIZE_INVENTORY
    return GoalType.GENERIC


def _detect_strategy(text: str) -> str:
    """Detect user's preferred strategy from text."""
    t = text.lower()
    for strategy, keywords in STRATEGY_KEYWORDS.items():
        if not keywords:
            continue
        if any(kw in t for kw in keywords):
            return strategy
    return "balanced"


def _detect_constraints(text: str) -> tuple[int, int, list[str]]:
    """Extract time budget (min), gold budget (copper), and exclusions."""
    t = text.lower()
    time_minutes = 0
    gold_copper = 0
    exclusions: list[str] = []

    # Time budget
    time_patterns = [
        (r"(\d+)\s*hour", 60),
        (r"(\d+)\s*hr", 60),
        (r"(\d+)\s*min", 1),
        (r"(\d+)\s*m", 1),
    ]
    for pat, mult in time_patterns:
        m = re.search(pat, t)
        if m:
            time_minutes = int(m.group(1)) * mult
            break

    # Gold budget
    gold_match = re.search(r"(\d+)\s*g", t)
    if gold_match:
        gold_copper = int(gold_match.group(1)) * 10000

    # Exclusions
    exclude_patterns = [
        (r"(?:no|without|avoid|skip|ignore|exclude)\s+(\w+)", 1),
        (r"(?:don't|dont|do not)\s+(?:want|like|do)\s+(\w+)", 1),
    ]
    for pat, _ in exclude_patterns:
        for m in re.finditer(pat, t):
            exclusions.append(m.group(1).lower())

    return time_minutes, gold_copper, exclusions


def _match_template(text: str) -> tuple[str, int]:
    """Match text against known progression templates.
    Only triggers when text is clearly about finishing/crafting a specific item.
    """
    t = text.lower()

    # Check common legendary/item names (exact word match)
    common_items = {
        "bolt": ("Bolt", 46765), "twilight": ("Twilight", 30684),
        "sunrise": ("Sunrise", 30703), "nevermore": ("Nevermore", 76158),
        "astralaria": ("Astralaria", 72066), "bifrost": ("The Bifrost", 30705),
        "frostfang": ("Frostfang", 30709), "incinerator": ("Incinerator", 30713),
        "aurora": ("Aurora", 84767), "vision": ("Vision", 93031),
        "ad infinitum": ("Ad Infinitum", 79906),
    }
    for key, (name, iid) in common_items.items():
        if key in t:
            return name, iid

    # Full template name match — only exact name appears in text
    for template in CURATED_TEMPLATES:
        name_lower = template.name.lower()
        # Extract just the item name (before parenthesis)
        simple_name = name_lower.split("(")[0].strip()
        if simple_name in t and len(simple_name) > 3:
            return template.name, template.target_item_id

    return "", 0


def _detect_game_mode(text: str) -> str:
    """Detect game mode from text."""
    t = text.lower()
    if any(kw in t for kw in ["fractal", "t4", "t3", "t2", "t1", "recs"]):
        return "fractal"
    if any(kw in t for kw in ["raid", "wing", "boss", "weekly raid"]):
        return "raid"
    if any(kw in t for kw in ["wvw", "world vs world", "guild", "ebg"]):
        return "wvw"
    if any(kw in t for kw in ["pvp", "pvp", "conquest", "ranked", "unranked"]):
        return "pvp"
    if any(kw in t for kw in ["strike", "strike mission", "eod strike"]):
        return "strike"
    if any(kw in t for kw in ["open world", "ow", "world boss", "meta", "map"]):
        return "open_world"
    return ""


async def interpret_goal(goal_text: str) -> ParsedGoal:
    """Parse a natural language goal into a structured ParsedGoal."""
    if not goal_text or not goal_text.strip():
        return ParsedGoal(raw_text=goal_text, confidence=0.0)

    text = goal_text.strip()
    goal_type = _detect_goal_type(text)
    strategy = _detect_strategy(text)
    time_min, gold_copper, exclusions = _detect_constraints(text)
    game_mode = _detect_game_mode(text)

    # Only match items for craft/legendary goals
    item_name = ""
    item_id = 0
    if goal_type in (GoalType.FINISH_LEGENDARY, GoalType.CRAFT_ITEM):
        item_name, item_id = _match_template(text)
        if not item_name:
            item_name = _extract_item_name(text)

    confidence_parts = 1.0
    if goal_type != GoalType.GENERIC:
        confidence_parts += 0.3
    if strategy != "balanced":
        confidence_parts += 0.2
    if item_id > 0:
        confidence_parts += 0.3
    if time_min > 0 or gold_copper > 0:
        confidence_parts += 0.1
    if game_mode:
        confidence_parts += 0.1
    confidence = min(confidence_parts, 1.0)

    return ParsedGoal(
        raw_text=text,
        goal_type=goal_type,
        target_item_name=item_name,
        target_item_id=item_id,
        strategy=strategy,
        time_budget_minutes=time_min,
        gold_budget_copper=gold_copper,
        game_mode=game_mode,
        excluded_content=exclusions,
        confidence=round(confidence, 2),
    )


async def generate_alternatives(parsed: ParsedGoal) -> list[ParsedGoal]:
    """Generate alternative interpretations for user to choose from."""
    alternatives = [parsed]

    if parsed.strategy != "fastest":
        alt = parsed.model_copy(deep=True)
        alt.strategy = "fastest"
        alt.confidence = round(parsed.confidence * 0.7, 2)
        alternatives.append(alt)

    if parsed.strategy != "cheapest":
        alt = parsed.model_copy(deep=True)
        alt.strategy = "cheapest"
        alt.confidence = round(parsed.confidence * 0.7, 2)
        alternatives.append(alt)

    if parsed.strategy != "low_effort":
        alt = parsed.model_copy(deep=True)
        alt.strategy = "low_effort"
        alt.confidence = round(parsed.confidence * 0.5, 2)
        alternatives.append(alt)

    return alternatives
