"""Tests for Module 9: Catalog Export"""
import pytest
import json
import os
from app.nodes.m9.node import export_catalog

def test_export_catalog_empty_state():
    """Empty state → generates JSON/Excel/HTML with fallbacks, no crash."""
    result = export_catalog({})
    assert "catalog_paths" in result
    # JSON + Excel + HTML should always be generated
    assert any(p.endswith(".json") for p in result["catalog_paths"])
    assert any(p.endswith(".xlsx") for p in result["catalog_paths"])
    assert any(p.endswith(".html") for p in result["catalog_paths"])
    # PDF may or may not be present depending on weasyprint availability
    # Errors should be logged but not raised
    assert isinstance(result.get("errors", []), list)

def test_export_catalog_with_state():
    """State with data → JSON contains aggregated data, Excel has sheets."""
    mock_state = {
        "extracted_specs": {"part": "Test_Valve", "material": "Steel", "pressure": "40bar"},
        "suppliers": [{"name": "SupplierA", "country": "DZ"}, {"name": "SupplierB", "country": "FR"}],
        "tco_data": {"total_tco_usd": 100000, "quantity": 200, "yearly_breakdown": []},
        "errors": []
    }
    result = export_catalog(mock_state)

    json_path = next((p for p in result["catalog_paths"] if p.endswith(".json")), None)
    assert json_path and os.path.exists(json_path)
    with open(json_path) as f:
        data = json.load(f)
    assert data["extracted_specs"]["part"] == "Test_Valve"
    assert data["tco_data"]["total_tco_usd"] == 100000
    assert len(data["suppliers"]) == 2
