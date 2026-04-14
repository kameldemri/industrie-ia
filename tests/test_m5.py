"""Tests for Module 5: Simulated AI Negotiation"""
import pytest
from unittest.mock import patch, MagicMock
import json
from app.nodes.m5.node import simulate_negotiation, MOCK_SUPPLIERS

def test_negotiation_success():
    """LLM returns valid JSON → parsed correctly, keys returned."""
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "transcript": [{"role": "buyer", "message": "Hello"}, {"role": "supplier", "name": "A", "message": "Hi"}],
        "final_prices": {"SupplierAlpha_DZ": 405.0},
        "selected_supplier": "SupplierAlpha_DZ",
        "discount_pct": 10
    })
    with patch("app.nodes.m5.node.get_llm") as mock_llm:
        mock_llm.return_value.invoke.return_value = mock_response
        result = simulate_negotiation({
            "extracted_specs": {"part_name": "Valve", "material": "SS316L", "quantity": 200},
            "suppliers": MOCK_SUPPLIERS,
            "errors": []
        })
    assert "negotiation_transcript" in result
    assert len(result["negotiation_transcript"]) >= 2
    assert result["selected_supplier"] == "SupplierAlpha_DZ"
    assert result["negotiated_discount"] == 0.10
    assert len(result["errors"]) == 0

def test_negotiation_missing_suppliers_fallback():
    """No suppliers in state → uses mocks, logs warning."""
    result = simulate_negotiation({"extracted_specs": {}, "errors": []})
    assert "negotiation_transcript" in result
    assert any("No suppliers in state" in e for e in result["errors"])
    assert isinstance(result["negotiated_discount"], (int, float))
    assert 0 <= result["negotiated_discount"] <= 1.0

def test_negotiation_llm_failure_fallback():
    """LLM crashes or returns invalid JSON → graceful fallback."""
    with patch("app.nodes.m5.node.get_llm") as mock_llm:
        mock_llm.return_value.invoke.side_effect = Exception("Connection timeout")
        result = simulate_negotiation({"suppliers": MOCK_SUPPLIERS, "errors": []})
    assert "negotiation_transcript" in result
    assert any("Negotiation failed" in e for e in result["errors"])
    assert isinstance(result["negotiated_prices"], dict)
    assert result["negotiated_discount"] == 0.10  # Fallback value
