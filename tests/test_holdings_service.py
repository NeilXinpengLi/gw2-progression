"""Tests for holdings extraction — normalizing raw GW2 API data into ItemHolding."""

from gw2_progression.models import ItemHolding
from gw2_progression.services.holdings_service import (
    extract_bank_holdings,
    extract_character_holdings,
    extract_material_holdings,
    extract_shared_inventory_holdings,
    extract_tradingpost_holdings,
    extract_wallet_holdings,
)


class TestExtractWallet:
    def test_empty(self):
        assert extract_wallet_holdings(None) == []
        assert extract_wallet_holdings([]) == []

    def test_gold_only(self):
        result = extract_wallet_holdings([{"id": 1, "value": 500000}])
        assert len(result) == 1
        assert result[0].item_id == 1
        assert result[0].count == 500000
        assert result[0].location_type == "wallet"

    def test_skips_non_gold_currencies(self):
        result = extract_wallet_holdings([
            {"id": 1, "value": 100000},
            {"id": 2, "value": 5000},  # karma
            {"id": 4, "value": 200},   # gems
        ])
        assert len(result) == 1
        assert result[0].item_id == 1

    def test_zero_gold_skipped(self):
        result = extract_wallet_holdings([{"id": 1, "value": 0}])
        assert result == []

    def test_malformed_entries_skipped(self):
        result = extract_wallet_holdings([None, "string", {"id": 1, "value": 100}])
        assert len(result) == 1


class TestExtractMaterials:
    def test_empty(self):
        assert extract_material_holdings(None) == []
        assert extract_material_holdings([]) == []

    def test_extracts_with_category(self):
        mats = [{"id": 19976, "count": 120, "category": 5}]
        result = extract_material_holdings(mats)
        assert len(result) == 1
        assert result[0].item_id == 19976
        assert result[0].count == 120
        assert result[0].location_type == "material_storage"
        assert result[0].location_ref == "5"

    def test_skips_zero_count(self):
        mats = [{"id": 19976, "count": 0, "category": 5}]
        assert extract_material_holdings(mats) == []

    def test_handles_null_category(self):
        mats = [{"id": 19976, "count": 10, "category": None}]
        result = extract_material_holdings(mats)
        assert result[0].location_ref is None

    def test_skips_malformed_entries(self):
        mats = [None, {"id": None, "count": 5}, {"id": 19976, "count": 10}]
        result = extract_material_holdings(mats)
        assert len(result) == 1


class TestExtractBank:
    def test_empty(self):
        assert extract_bank_holdings(None) == []
        assert extract_bank_holdings([]) == []

    def test_extracts_items(self):
        bank = [{"id": 19720, "count": 250, "binding": None}]
        result = extract_bank_holdings(bank)
        assert len(result) == 1
        assert result[0].item_id == 19720
        assert result[0].count == 250
        assert result[0].location_type == "bank"

    def test_handles_character_binding(self):
        bank = [{"id": 19720, "count": 1, "binding": "Character"}]
        result = extract_bank_holdings(bank)
        assert result[0].binding_status == "Character"

    def test_skips_empty_slots(self):
        bank = [None, {"id": 19720, "count": 250}, None]
        result = extract_bank_holdings(bank)
        assert len(result) == 1


class TestExtractCharacterInventory:
    def test_empty(self):
        assert extract_character_holdings(None) == []
        assert extract_character_holdings([]) == []

    def test_extracts_bag_inventory(self):
        chars = [{
            "name": "TestChar",
            "bags": [{"inventory": [{"id": 19976, "count": 10}, None]}],
        }]
        result = extract_character_holdings(chars)
        assert len(result) == 1
        assert result[0].item_id == 19976
        assert result[0].count == 10
        assert result[0].location_type == "character"

    def test_character_without_bags(self):
        chars = [{"name": "EmptyChar"}]
        assert extract_character_holdings(chars) == []

    def test_multiple_characters(self):
        chars = [
            {"name": "A", "bags": [{"inventory": [{"id": 100, "count": 1}]}]},
            {"name": "B", "bags": [{"inventory": [{"id": 200, "count": 2}]}]},
        ]
        result = extract_character_holdings(chars)
        assert len(result) == 2

    def test_skips_empty_inventory_slots(self):
        chars = [{"name": "C", "bags": [{"inventory": [None, {"id": 1, "count": 5}]}]}]
        result = extract_character_holdings(chars)
        assert len(result) == 1


class TestExtractSharedInventory:
    def test_empty(self):
        assert extract_shared_inventory_holdings(None) == []
        assert extract_shared_inventory_holdings([]) == []

    def test_extracts_inventory_slots(self):
        data = [None, {"id": 19976, "count": 5}, {"id": 19720, "count": 2}]
        result = extract_shared_inventory_holdings(data)
        assert len(result) == 2
        assert result[0].location_type == "shared_inventory"

    def test_skips_empty_slots(self):
        data = [None, None, {"id": 1, "count": 1}]
        result = extract_shared_inventory_holdings(data)
        assert len(result) == 1


class TestExtractTradingPost:
    def test_empty(self):
        assert extract_tradingpost_holdings(None, None) == []
        assert extract_tradingpost_holdings([], []) == []

    def test_buys_and_sells(self):
        buys = [{"item_id": 100, "price": 50000, "quantity": 5}]
        sells = [{"item_id": 200, "price": 60000, "quantity": 3}]
        result = extract_tradingpost_holdings(buys, sells)
        refs = {h.location_ref for h in result}
        assert "buy_order" in refs
        assert "sell_order" in refs

    def test_skips_malformed(self):
        buys = [None, {"item_id": 100, "price": 50000, "quantity": 5}]
        result = extract_tradingpost_holdings(buys, [])
        assert len(result) == 1
