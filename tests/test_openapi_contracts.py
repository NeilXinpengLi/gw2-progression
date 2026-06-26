"""OpenAPI contract tests for professional GW2 workflows."""

from gw2_progression.api.main import app

DIRECT_RESPONSE_MODELS = [
    ("/value/items/locations", "get", "ItemLocationResponse"),
    ("/value/items/{item_id}/detail", "get", "ItemDetailResponse"),
    ("/crafting/calculate", "post", "CraftingResponse"),
    ("/crafting/calculate/cheapest", "post", "CraftingResponse"),
    ("/crafting/plan", "post", "CraftingPlanResult"),
    ("/crafting/optimize", "post", "RecipeOptimizationResult"),
    ("/builds/templates/{build_id}", "get", "BuildTemplate"),
    ("/builds/readiness/{build_id}", "post", "AccountBuildReadiness"),
    ("/agent/progression/advice", "post", "ProgressionAdvice"),
    ("/agent/coach-plan", "post", "CoachPlanResponse"),
]


ARRAY_RESPONSE_MODELS = [
    ("/value/items/search", "get", "ItemSearchResult"),
    ("/value/items/high-value", "get", "ItemSearchResult"),
    ("/value/items/unpriced", "get", "ItemSearchResult"),
    ("/value/items/account-bound", "get", "ItemSearchResult"),
    ("/value/top-gainers", "get", "ItemValueDelta"),
    ("/value/top-decliners", "get", "ItemValueDelta"),
    ("/builds/templates", "get", "BuildTemplate"),
    ("/builds/recommendations", "post", "AccountBuildReadiness"),
]


UNION_RESPONSE_MODELS = [
    ("/value/listings/{item_id}", "get", ["ListingDepthResponse", "ListingUnavailableResponse"]),
]


MAP_RESPONSE_MODELS = [
    ("/value/listings/batch", "post", "ListingDepthResponse"),
]


def _json_schema_for(path: str, method: str) -> dict:
    openapi = app.openapi()
    return openapi["paths"][path][method]["responses"]["200"]["content"]["application/json"]["schema"]


def test_direct_response_models_are_declared():
    components = app.openapi()["components"]["schemas"]

    for path, method, model_name in DIRECT_RESPONSE_MODELS:
        schema = _json_schema_for(path, method)

        assert model_name in components
        assert schema == {"$ref": f"#/components/schemas/{model_name}"}


def test_array_response_models_are_declared():
    components = app.openapi()["components"]["schemas"]

    for path, method, model_name in ARRAY_RESPONSE_MODELS:
        schema = _json_schema_for(path, method)

        assert model_name in components
        assert schema["type"] == "array"
        assert schema["items"] == {"$ref": f"#/components/schemas/{model_name}"}


def test_union_response_models_are_declared():
    components = app.openapi()["components"]["schemas"]

    for path, method, model_names in UNION_RESPONSE_MODELS:
        schema = _json_schema_for(path, method)
        refs = [entry["$ref"] for entry in schema["anyOf"]]

        for model_name in model_names:
            assert model_name in components
            assert f"#/components/schemas/{model_name}" in refs


def test_map_response_models_are_declared():
    components = app.openapi()["components"]["schemas"]

    for path, method, model_name in MAP_RESPONSE_MODELS:
        schema = _json_schema_for(path, method)

        assert model_name in components
        assert schema["type"] == "object"
        assert schema["additionalProperties"] == {"$ref": f"#/components/schemas/{model_name}"}


def test_value_confidence_fields_are_exposed():
    components = app.openapi()["components"]["schemas"]
    confidence_fields = {
        "confidence",
        "data_sources",
        "price_timestamp",
        "liquidity_reason",
        "risk_reason",
    }

    for model_name in ("ItemHolding", "TopItem", "ItemSearchResult"):
        properties = components[model_name]["properties"]
        assert confidence_fields.issubset(properties)

    summary_properties = components["ValueSummary"]["properties"]
    assert {"confidence", "data_sources", "price_timestamp", "risk_reason"}.issubset(summary_properties)


def test_recommendation_confidence_fields_are_exposed():
    components = app.openapi()["components"]["schemas"]
    confidence_fields = {"confidence", "data_sources", "risk_reason"}

    for model_name in ("ProgressionAdvice", "CoachAction", "CoachPlanResponse", "PlanAction", "AccountBuildReadiness"):
        properties = components[model_name]["properties"]
        assert confidence_fields.issubset(properties)
