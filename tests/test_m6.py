import pytest
from unittest.mock import patch

from app.nodes.m6.node import (
    _read_inputs,
    _fetch_inflation,
    _compute_tco,
    calculate_tco,
    MOCK_QUANTITY,
    MOCK_UNIT_MATERIAL,
    MOCK_UNIT_MANUFACTURING,
    MOCK_UNIT_MAINTENANCE,
    MOCK_DISCOUNT,
    MOCK_INFLATION,
)


# INPUT TESTS

def test_read_inputs_uses_mock_when_empty():
    state = {}
    result = _read_inputs(state)

    assert result["quantity"] == MOCK_QUANTITY
    assert result["unit_material"] == MOCK_UNIT_MATERIAL
    assert result["unit_manufacturing"] == MOCK_UNIT_MANUFACTURING
    assert result["unit_maintenance"] == MOCK_UNIT_MAINTENANCE
    assert result["discount"] == MOCK_DISCOUNT


def test_read_inputs_quantity_from_m1():
    state = {"extracted_specs": {"quantity": 500}}
    result = _read_inputs(state)

    assert result["quantity"] == 500


def test_read_inputs_costs_from_m4():
    state = {
        "suppliers": [{
            "unit_material_cost": 300.0,
            "unit_manufacturing_cost": 120.0,
            "unit_maintenance_cost": 25.0,
        }]
    }

    result = _read_inputs(state)

    assert result["unit_material"] == 300.0
    assert result["unit_manufacturing"] == 120.0
    assert result["unit_maintenance"] == 25.0


def test_read_inputs_invalid_supplier_falls_back():
    state = {"suppliers": [{"name": "bad_supplier"}]}
    result = _read_inputs(state)

    assert result["unit_material"] == MOCK_UNIT_MATERIAL



# INFLATION TESTS


def test_fetch_inflation_success():
    fake_api = [
        {},
        [{"value": 3.0}, {"value": 4.0}, {"value": 5.0}]
    ]

    with patch("app.nodes.m6.node.requests.get") as mock:
        mock.return_value.json.return_value = fake_api
        mock.return_value.raise_for_status.return_value = None

        result = _fetch_inflation(3)

    assert len(result) == 3
    assert all(isinstance(x, float) for x in result)


def test_fetch_inflation_failure_fallback():
    with patch("app.nodes.m6.node.requests.get", side_effect=Exception("fail")):
        result = _fetch_inflation(10)

    assert result == MOCK_INFLATION[:10]


# TCO CORE ENGINE


def test_compute_tco_production_cost():
    inputs = {
        "quantity": 200,
        "unit_material": 450,
        "unit_manufacturing": 200,
        "unit_maintenance": 50,
        "discount": 0.10,
    }

    result = _compute_tco(inputs, [3.0] * 10)

    expected = (450 + 200) * 200 * 0.9
    assert result["production_cost_usd"] == pytest.approx(expected, 0.01)


def test_compute_tco_per_unit():
    inputs = {
        "quantity": 200,
        "unit_material": 450,
        "unit_manufacturing": 200,
        "unit_maintenance": 50,
        "discount": 0.0,
    }

    result = _compute_tco(inputs, [3.0] * 10)

    assert result["tco_per_unit_usd"] == pytest.approx(
        result["total_tco_usd"] / 200,
        rel=0.01
    )


def test_compute_tco_years_length():
    inputs = {
        "quantity": 200,
        "unit_material": 450,
        "unit_manufacturing": 200,
        "unit_maintenance": 50,
        "discount": 0.1,
    }

    result = _compute_tco(inputs, [3.0] * 10)

    assert len(result["yearly_breakdown"]) == 10


def test_compute_tco_total_greater_than_production():
    inputs = {
        "quantity": 200,
        "unit_material": 450,
        "unit_manufacturing": 200,
        "unit_maintenance": 50,
        "discount": 0.1,
    }

    result = _compute_tco(inputs, [3.0] * 10)

    assert result["total_tco_usd"] > result["production_cost_usd"]


# node test

def test_calculate_tco_empty_state():
    with patch("app.nodes.m6.node._fetch_inflation", return_value=[3.0]*10), \
         patch("app.nodes.m6.node._export_excel", return_value="outputs/tco_result.xlsx"), \
         patch("app.nodes.m6.node._export_json", return_value="outputs/tco_result.json"):

        result = calculate_tco({})

    assert "tco_data" in result
    assert result["tco_data"]["quantity"] == MOCK_QUANTITY


def test_calculate_tco_with_state_override():
    state = {
        "extracted_specs": {"quantity": 100},
        "suppliers": [{
            "unit_material_cost": 300.0,
            "unit_manufacturing_cost": 100.0,
            "unit_maintenance_cost": 20.0,
        }],
        "errors": []
    }

    with patch("app.nodes.m6.node._fetch_inflation", return_value=[3.0]*10), \
         patch("app.nodes.m6.node._export_excel", return_value="outputs/tco_result.xlsx"), \
         patch("app.nodes.m6.node._export_json", return_value="outputs/tco_result.json"):

        result = calculate_tco(state)

    assert result["tco_data"]["quantity"] == 100
    assert result["tco_data"]["unit_material_usd"] == 300.0


def test_calculate_tco_error_handling():
    with patch("app.nodes.m6.node._fetch_inflation", side_effect=Exception("boom")):

        result = calculate_tco({"errors": []})

    assert "errors" in result
    assert any("Module 6" in e for e in result["errors"])