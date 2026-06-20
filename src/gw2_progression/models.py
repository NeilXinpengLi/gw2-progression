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
