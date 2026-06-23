from pydantic import BaseModel


class PriceData(BaseModel):
    item_id: int
    buy_unit_price: int = 0
    buy_quantity: int = 0
    sell_unit_price: int = 0
    sell_quantity: int = 0
    fetched_at: str = ""


class ItemHolding(BaseModel):
    item_id: int
    count: int
    location_type: str
    location_ref: str | None = None
    binding_status: str | None = None
    tradable: bool = True
    vendor_value: int = 0
    price_buy: int = 0
    price_sell: int = 0
    value_buy: int = 0
    value_sell: int = 0
    valuation_status: str = "pending"
    quality_status: str = "unknown"
    buy_quantity: int = 0
    sell_quantity: int = 0
    spread: int = 0
    spread_ratio: float = 0.0
    liquidity_score: str = "unknown"


class ValueSummary(BaseModel):
    total_value_buy: int = 0
    total_value_sell: int = 0
    net_sell_value: int = 0
    wallet_value: int = 0
    material_value_buy: int = 0
    material_value_sell: int = 0
    bank_value_buy: int = 0
    bank_value_sell: int = 0
    character_inventory_value_buy: int = 0
    character_inventory_value_sell: int = 0
    shared_inventory_value_buy: int = 0
    shared_inventory_value_sell: int = 0
    tradingpost_value: int = 0
    tradingpost_buy_value: int = 0
    tradingpost_sell_value: int = 0
    priced_item_count: int = 0
    unpriced_item_count: int = 0
    account_bound_count: int = 0
    reliable_value: int = 0
    risky_value: int = 0
    low_liquidity_count: int = 0
    stale_price_count: int = 0
    snapshot_id: int | None = None
    snapshot_time: str = ""


class LocationBreakdown(BaseModel):
    location: str
    label: str
    value_buy: int
    value_sell: int
    percentage: float = 0.0


class StatusBreakdown(BaseModel):
    status: str
    count: int
    value_buy: int = 0


class ValueBreakdown(BaseModel):
    by_location: list[LocationBreakdown] = []
    by_status: list[StatusBreakdown] = []


class TopItem(BaseModel):
    item_id: int
    count: int
    location_type: str
    location_ref: str | None = None
    price_buy: int = 0
    price_sell: int = 0
    value_buy: int = 0
    value_sell: int = 0
    tradable: bool = True
    valuation_status: str = "pending"


class ValueHistoryEntry(BaseModel):
    snapshot_time: str
    total_value_buy: int
    total_value_sell: int
    wallet_value: int
    material_value: int
    bank_value: int
    inventory_value: int
    tradingpost_value: int


class ValuationWarningModel(BaseModel):
    warning_type: str
    message: str
    item_id: int | None = None


class ValuationResult(BaseModel):
    summary: ValueSummary
    breakdown: ValueBreakdown
    top_items: list[TopItem] = []
    warnings: list[ValuationWarningModel] = []
    holdings: list[ItemHolding] = []
    snapshot_id: int | None = None


class ValueAnalyzeResponse(BaseModel):
    summary: ValueSummary
    breakdown: ValueBreakdown
    top_items: list[TopItem]
    holdings: list[ItemHolding] = []
    warnings: list[ValuationWarningModel]
    history: list[ValueHistoryEntry]


class ItemSearchResult(BaseModel):
    item_id: int
    count: int
    location_type: str
    location_ref: str | None = None
    binding_status: str | None = None
    tradable: bool = True
    price_buy: int = 0
    price_sell: int = 0
    value_buy: int = 0
    value_sell: int = 0
    valuation_status: str = "pending"
    snapshot_time: str = ""


class ItemLocationResponse(BaseModel):
    item_id: int
    total_count: int
    locations: list[ItemSearchResult]


class CraftIngredient(BaseModel):
    item_id: int
    count: int
    owned: int = 0
    missing: int = 0
    buy_unit_price: int = 0
    total_buy_cost: int = 0
    has_recipe: bool = False
    sub_tree: list["CraftIngredient"] = []


class CraftStep(BaseModel):
    recipe_id: int
    output_item_id: int
    output_count: int
    disciplines: list[str] = []
    min_rating: int = 0
    ingredients: list[CraftIngredient] = []
    craft_cost: int = 0


class CraftingRequest(BaseModel):
    api_key: str
    target_item_id: int
    quantity: int = 1
    use_owned: bool = True


class ItemValueDelta(BaseModel):
    item_id: int
    old_count: int = 0
    new_count: int = 0
    count_delta: int = 0
    old_price_buy: int = 0
    new_price_buy: int = 0
    price_delta: int = 0
    old_value_buy: int = 0
    new_value_buy: int = 0
    value_delta: int = 0
    primary_cause: str = "quantity_change"  # quantity_change | price_change | new_item | removed_item | location_change


class AccountValueDelta(BaseModel):
    account_name: str
    from_snapshot_id: int
    to_snapshot_id: int
    from_time: str = ""
    to_time: str = ""
    total_delta_buy: int = 0
    total_delta_sell: int = 0
    wallet_delta: int = 0
    material_delta: int = 0
    bank_delta: int = 0
    inventory_delta: int = 0
    tradingpost_delta: int = 0
    price_effect_delta: int = 0
    quantity_effect_delta: int = 0
    top_gainers: list[ItemValueDelta] = []
    top_decliners: list[ItemValueDelta] = []


class ProgressionGoalTemplate(BaseModel):
    template_id: str = ""
    goal_type: str = "legendary_weapon"  # legendary_weapon | legendary_armor | legendary_trinket | ascended_weapon | ascended_armor
    name: str = ""
    target_item_id: int = 0
    expansion: str = ""
    category: str = ""
    difficulty_level: str = "medium"
    estimated_time_class: str = "long"
    enabled: bool = True


class GoalRequirement(BaseModel):
    requirement_id: str = ""
    template_id: str = ""
    requirement_type: str = "item"  # item | currency | achievement | mastery | collection | account_unlock
    ref_id: int = 0
    ref_name: str = ""
    required_count: int = 0
    time_gated: bool = False
    optional_group_id: str = ""
    notes: str = ""


class GoalRequirementStatus(BaseModel):
    requirement_id: str = ""
    template_id: str = ""
    requirement_type: str = "item"
    ref_id: int = 0
    ref_name: str = ""
    required_count: int = 0
    owned_count: int = 0
    missing_count: int = 0
    completion_percent: float = 0.0
    estimated_cost_buy: int = 0
    status: str = "missing"  # complete | partial | missing | blocked


class GoalPlan(BaseModel):
    goal_id: str = ""
    account_name: str = ""
    template_id: str = ""
    target_count: int = 1
    total_completion_percent: float = 0.0
    total_missing_cost: int = 0
    total_owned_material_value: int = 0
    time_gated_count: int = 0
    blocked_requirement_count: int = 0
    requirements: list[GoalRequirementStatus] = []
    created_at: str = ""
    updated_at: str = ""


class TrackedGoal(BaseModel):
    goal_id: str = ""
    account_name: str = ""
    target_item_id: int = 0
    target_count: int = 1
    status: str = "active"  # active | completed | paused
    priority: str = "normal"  # high | normal | low
    completion_percent: float = 0.0
    owned_material_value: int = 0
    missing_material_value: int = 0
    missing_item_count: int = 0
    estimated_remaining_cost: int = 0
    created_at: str = ""
    updated_at: str = ""


class RecipeDecision(BaseModel):
    item_id: int
    decision: str = "unknown"  # buy | craft | use_owned | vendor | blocked
    reason: str = ""
    cost_buy: int = 0
    cost_craft: int = 0
    owned_count: int = 0
    missing_count: int = 0


class RecipeOptimizationResult(BaseModel):
    result_id: str = ""
    target_item_id: int
    target_count: int = 1
    strategy: str = "cheapest"
    total_cost: int = 0
    owned_value_used: int = 0
    missing_cost: int = 0
    direct_buy_cost: int = 0
    craft_vs_buy_delta: int = 0
    decisions: list[RecipeDecision] = []
    shopping_list: list[dict] = []
    crafting_steps: list[dict] = []
    required_disciplines: list[str] = []
    created_at: str = ""


class TradingPostSignal(BaseModel):
    item_id: int
    signal_type: str = ""  # sell_candidate | buy_candidate | low_liquidity | high_spread | price_anomaly
    severity: str = "info"  # info | warning | critical
    reason: str = ""
    current_buy_price: int = 0
    current_sell_price: int = 0
    spread_ratio: float = 0.0
    quantity_owned: int = 0
    value_owned: int = 0
    linked_goal_id: str = ""


class ProtectedAsset(BaseModel):
    account_name: str = ""
    item_id: int = 0
    protected_count: int = 0
    reason: str = "tracked_goal"
    linked_goal_id: str = ""


class BuildGearRequirement(BaseModel):
    slot: str = ""
    item_type: str = ""
    stat_combo: str = ""
    required_item_id: int = 0
    alternatives: list[int] = []
    priority: int = 0


class BuildTraitRequirement(BaseModel):
    specialization_id: int = 0
    trait_ids: list[int] = []


class BuildSkillRequirement(BaseModel):
    skill_ids: list[int] = []


class BuildTemplate(BaseModel):
    build_id: str = ""
    source: str = ""
    name: str = ""
    profession: str = ""
    elite_specialization: str = ""
    game_mode: str = ""
    role: str = ""
    difficulty: str = "medium"
    patch_version: str = ""
    source_url: str = ""
    gear: list[BuildGearRequirement] = []
    traits: list[BuildTraitRequirement] = []
    skills: list[int] = []


class AccountBuildReadiness(BaseModel):
    account_name: str = ""
    build_id: str = ""
    build_name: str = ""
    readiness_score: float = 0.0
    gear_completion_percent: float = 0.0
    trait_completion_percent: float = 0.0
    missing_cost: int = 0
    missing_items_count: int = 0
    profession_match: bool = False


class ProgressionAdvice(BaseModel):
    summary: str = ""
    recommended_actions: list[dict] = []
    weekly_plan: list[dict] = []


class CraftingPlanLine(BaseModel):
    item_id: int
    required_count: int
    owned_count: int = 0
    used_owned_count: int = 0
    missing_count: int = 0
    unit_buy_price: int = 0
    unit_sell_price: int = 0
    missing_buy_cost: int = 0
    source: str = "missing"  # material_storage | bank | inventory | missing | vendor


class CraftingPlanResult(BaseModel):
    plan_id: str = ""
    target_item_id: int
    target_count: int
    total_market_buy_cost: int = 0
    total_market_sell_cost: int = 0
    owned_material_value_used: int = 0
    missing_material_cost: int = 0
    direct_buy_price: int = 0
    craft_vs_buy_delta: int = 0
    lines: list[CraftingPlanLine] = []
    created_at: str = ""


class CraftingResponse(BaseModel):
    target_item_id: int
    target_count: int
    total_buy_cost: int = 0
    total_craft_cost: int = 0
    owned_used: int = 0
    missing_items: list[dict] = []
    shopping_list: list[dict] = []
    crafting_steps: list[dict] = []
    recipe_tree: CraftStep | None = None
    alternative_recipes: list[dict] = []


class AccountReport(BaseModel):
    report_id: int = 0
    account_name: str
    report_type: str  # full | value | goals | builds
    title: str = ""
    summary: str = ""
    total_value_buy: int = 0
    total_value_sell: int = 0
    wallet_gold: int = 0
    character_count: int = 0
    goal_count: int = 0
    goal_progress_pct: float = 0.0
    build_readiness_pct: float = 0.0
    top_items: list[dict] = []
    goal_details: list[dict] = []
    build_details: list[dict] = []
    recommendations: list[str] = []
    snapshot_time: str = ""
    created_at: str = ""
