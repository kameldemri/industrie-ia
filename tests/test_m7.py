import pytest
from app.nodes.m7.node import (
    _load_tco,
    _build_plan,
    _export_excel,
    _export_pdf,
    generate_business_plan
)

MOCK_TCO = {
    "quantity": 200,
    "unit_material_usd": 450,
    "unit_manufacturing_usd": 200,
    "production_cost_usd": 117000,
    "total_tco_usd": 255000,
}

MOCK_SUPPLIERS = [{"name": "Supplier A"}, {"name": "Supplier B"}]


# TCO LOADER


def test_load_tco_fallback():
    tco = _load_tco({})
    assert tco["quantity"] == 200
    assert "unit_material_usd" in tco
    assert "unit_manufacturing_usd" in tco


# BUILD PLAN


def test_build_plan_financials():
    plan = _build_plan(MOCK_TCO, {"product_name": "Valve X"}, MOCK_SUPPLIERS)
    assert "npv" in plan["financials"]
    assert "roi_3yr" in plan["financials"]


def test_build_plan_roi_is_float():
    plan = _build_plan(MOCK_TCO, {"product_name": "Valve X"}, MOCK_SUPPLIERS)
    assert isinstance(plan["financials"]["roi_3yr"], float)


def test_build_plan_product_name():
    plan = _build_plan(MOCK_TCO, {"product_name": "Valve X"}, MOCK_SUPPLIERS)
    assert plan["product"] == "Valve X"


def test_build_plan_unit_cost_uses_usd_keys():
   #Ensure _build_plan correctly reads unit_material_usd and unit_manufacturing_usd
    plan = _build_plan(MOCK_TCO, {"product_name": "Valve X"}, MOCK_SUPPLIERS)
    expected_base = (450 + 200) * 0.95
    assert plan["financials"]["unit_cost"] == pytest.approx(expected_base, rel=0.01)


def test_build_plan_has_3_projections():
    plan = _build_plan(MOCK_TCO, {"product_name": "Valve X"}, MOCK_SUPPLIERS)
    assert len(plan["projections"]) == 3


def test_build_plan_npv_is_numeric():
    plan = _build_plan(MOCK_TCO, {"product_name": "Valve X"}, MOCK_SUPPLIERS)
    assert isinstance(plan["financials"]["npv"], float)

# EXPORT TESTS


def test_export_excel_creates_file(tmp_path):
    plan = _build_plan(MOCK_TCO, {"product_name": "Valve X"}, MOCK_SUPPLIERS)
    path = _export_excel(plan, str(tmp_path / "bp.xlsx"))
    assert path.endswith(".xlsx")


def test_export_pdf_creates_file(tmp_path):
    plan = _build_plan(MOCK_TCO, {"product_name": "Valve X"}, MOCK_SUPPLIERS)
    path = _export_pdf(plan, str(tmp_path / "bp.pdf"))
    assert path.endswith(".pdf")

# FULL PIPELINE


def test_generate_business_plan_full_flow():
    state = {
        "tco_data": MOCK_TCO,
        "extracted_specs": {"product_name": "Valve X"},
        "suppliers": MOCK_SUPPLIERS
    }

    result = generate_business_plan(state)

    assert "business_plan_summary" in result
    assert result["business_plan_summary"]["npv"] is not None


def test_generate_business_plan_fallback():
    result = generate_business_plan({})

    assert "plan" in result
    assert result["plan"]["quantity"] == 200


# FIX: test that Module 7 returns business_plan_paths as a dict
def test_generate_business_plan_paths_structure():
    state = {
        "tco_data": MOCK_TCO,
        "extracted_specs": {"product_name": "Valve X"},
        "suppliers": MOCK_SUPPLIERS
    }

    result = generate_business_plan(state)

    assert isinstance(result["business_plan_paths"], dict)
    assert "json" in result["business_plan_paths"]
    assert "excel" in result["business_plan_paths"]
    assert "pdf" in result["business_plan_paths"]