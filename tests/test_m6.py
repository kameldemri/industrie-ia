# Module 6 TCO Calculator   |   run pytest tests/test_m6.py -v

import pytest
from unittest.mock import patch
from app.nodes.m6.node import (
    _read_inputs,
    _fetch_inflation,
    _compute_tco,
    _export_excel,
    calculate_tco,
    MOCK_QUANTITY,
    MOCK_UNIT_MATERIAL,
    MOCK_UNIT_MANUFACTURING,
    MOCK_UNIT_MAINTENANCE,
    MOCK_NEGOTIATED_DISCOUNT,
    MOCK_INFLATION_RATES,
)

# read inputs

def test_read_inputs_all_mocks_when_state_empty():
    """use mock data """
    result = _read_inputs({})
    assert result["quantity"] == MOCK_QUANTITY
    assert result["unit_material"] == MOCK_UNIT_MATERIAL
    assert result["unit_manufacturing"]== MOCK_UNIT_MANUFACTURING
    assert result["unit_maintenance"]== MOCK_UNIT_MAINTENANCE
    assert result["discount"] == MOCK_NEGOTIATED_DISCOUNT


""" M1 is ready quantity comes from extracted_specs"""
def test_read_inputs_quantity_from_m1():
    state = {"extracted_specs": {"quantity": 500}}
    result = _read_inputs(state)
    assert result["quantity"] == 500

"""M4 is ready costs come from suppliers[0]"""
def test_read_inputs_costs_from_m4():
    state = {
        "suppliers": [{
            "unit_material_cost": 300.0,
            "unit_manufacturing_cost": 100.0,
            "unit_maintenance_cost": 20.0,
        }]
    }
    result = _read_inputs(state)
    assert result["unit_material"]      == 300.0
    assert result["unit_manufacturing"] == 100.0
    assert result["unit_maintenance"]   == 20.0


"""Supplier exists but has no cost keys → still uses mock"""
def test_read_inputs_supplier_without_cost_uses_mock():
    state = {"suppliers": [{"name": "SupplierX"}]}
    result = _read_inputs(state)
    assert result["unit_material"] == MOCK_UNIT_MATERIAL


# 
# fetchin flation
"""Valid API response → parsed correctly"""
def test_fetch_inflation_api_success():
    fake = [
        {"page": 1},
        [{"value": 3.2}, {"value": 3.5}, {"value": 4.0},
         {"value": 3.8}, {"value": 3.6}, {"value": 3.4},
         {"value": 3.3}, {"value": 3.5}, {"value": 3.7}, {"value": 3.9}]
    ]
    with patch("app.nodes.m6.node.requests.get") as mock_get:
        mock_get.return_value.json.return_value = fake
        mock_get.return_value.raise_for_status.return_value = None
        rates = _fetch_inflation(years=10)

    assert len(rates) == 10
    assert rates[0] == 3.2
    assert all(isinstance(r, float) for r in rates)

"""API failure returns MOCK_INFLATION_RATES, no crash."""
def test_fetch_inflation_api_failure_uses_mock():
    with patch("app.nodes.m6.node.requests.get") as mock_get:
        mock_get.side_effect = Exception("timeout")
        rates = _fetch_inflation(years=10)

    assert rates == MOCK_INFLATION_RATES[:10]

"""None values in API response are skipped."""
def test_fetch_inflation_skips_none_values():
    fake = [
        {"page": 1},
        [{"value": 3.2}, {"value": None}, {"value": 4.0},
         {"value": 3.8}, {"value": 3.6}, {"value": 3.4},
         {"value": 3.3}, {"value": 3.5}, {"value": 3.7}, {"value": 3.9}]
    ]
    with patch("app.nodes.m6.node.requests.get") as mock_get:
        mock_get.return_value.json.return_value = fake
        mock_get.return_value.raise_for_status.return_value = None
        rates = _fetch_inflation(years=10)

    assert None not in rates
    assert len(rates) == 10  # padded with last value


# _compute_tco

def test_compute_tco_production_cost():
    """production_cost = (material + manufacturing) * quantity * (1 - discount)"""
    inputs = {
        "quantity": 200,
        "unit_material": 450.0,
        "unit_manufacturing": 200.0,
        "unit_maintenance": 50.0,
        "discount": 0.10,
    }
    result = _compute_tco(inputs, [3.0] * 10)
    # (450 + 200) * 200 * 0.9 = 117,000
    assert result["production_cost_usd"] == pytest.approx(117_000.0, rel=0.01)


def test_compute_tco_total_greater_than_production():
    """total TCO must exceed production cost maintenance adds on top"""
    inputs = {
        "quantity": 200, "unit_material": 450.0,
        "unit_manufacturing": 200.0, "unit_maintenance": 50.0, "discount": 0.10,
    }
    result = _compute_tco(inputs, [3.0] * 10)
    assert result["total_tco_usd"] > result["production_cost_usd"]


def test_compute_tco_per_unit():
    """tco_per_unit = total / quantity."""
    inputs = {
        "quantity": 200, "unit_material": 450.0,
        "unit_manufacturing": 200.0, "unit_maintenance": 50.0, "discount": 0.0,
    }
    result = _compute_tco(inputs, [3.0] * 10)
    assert result["tco_per_unit_usd"] == pytest.approx(
        result["total_tco_usd"] / 200, rel=0.01
    )


def test_compute_tco_breakdown_has_10_years():
    """yearly_breakdown must have exactly 10 entries."""
    inputs = {
        "quantity": 200, "unit_material": 450.0,
        "unit_manufacturing": 200.0, "unit_maintenance": 50.0, "discount": 0.10,
    }
    result = _compute_tco(inputs, [3.0] * 10)
    assert len(result["yearly_breakdown"]) == 10


def test_compute_tco_zero_discount():
    """Zero discount → production_cost = (450+200)*200 = 130,000."""
    inputs = {
        "quantity": 200, "unit_material": 450.0,
        "unit_manufacturing": 200.0, "unit_maintenance": 50.0, "discount": 0.0,
    }
    result = _compute_tco(inputs, [3.0] * 10)
    assert result["production_cost_usd"] == pytest.approx(130_000.0, rel=0.01)



# _export_excel


def test_export_excel_creates_file(tmp_path):
    fake_tco = {
        "quantity": 200, "unit_material_usd": 450.0,
        "unit_manufacturing_usd": 200.0, "unit_maintenance_usd": 50.0,
        "negotiated_discount_pct": 10.0, "production_cost_usd": 117000.0,
        "total_tco_usd": 130000.0, "tco_per_unit_usd": 650.0,
        "years": 10, "calculated_at": "2026-01-01T00:00:00",
        "yearly_breakdown": [
            {"year": i+1, "inflation_rate_pct": 3.0,
             "cumulative_factor": 1.03, "maintenance_cost_usd": 10000.0}
            for i in range(10)
        ],
    }
    path = _export_excel(fake_tco, output_dir=str(tmp_path))
    assert path.endswith("tco_result.xlsx")
    assert (tmp_path / "tco_result.xlsx").exists()





# calculate_tco (full node)


def test_calculate_tco_empty_state_returns_tco_data():
    """Empty state → runs with mocks → returns tco_data key"""
    with patch("app.nodes.m6.node._fetch_inflation", return_value=[3.0]*10), \
         patch("app.nodes.m6.node._export_excel", return_value="outputs/tco_result.xlsx"):
        result = calculate_tco({})

    assert "tco_data" in result
    assert result["tco_data"]["total_tco_usd"] > 0
    assert result["tco_data"]["quantity"] == MOCK_QUANTITY


def test_calculate_tco_uses_state_over_mock():
    """State values override mocks"""
    state = {
        "extracted_specs": {"quantity": 100},
        "suppliers": [{
            "unit_material_cost": 300.0,
            "unit_manufacturing_cost": 100.0,
            "unit_maintenance_cost": 25.0,
        }],
        "errors": [],
    }
    with patch("app.nodes.m6.node._fetch_inflation", return_value=[3.0]*10), \
         patch("app.nodes.m6.node._export_excel", return_value="outputs/tco_result.xlsx"):
        result = calculate_tco(state)

    assert result["tco_data"]["quantity"] == 100
    assert result["tco_data"]["unit_material_usd"] == 300.0


def test_calculate_tco_returns_errors_on_failure():
    """If something crashes → error is appended to state errors, no exception raised"""
    with patch("app.nodes.m6.node._fetch_inflation", side_effect=Exception("boom")):
        result = calculate_tco({"errors": []})

    assert "errors" in result
    assert any("Module 6" in e for e in result["errors"])