"""Tests for Module 2: CAD Generation"""
import pytest
from app.nodes.m2.node import generate_cad

def test_generate_cad_success():
    state = {
        "extracted_specs": {"part_name": "Valve_DN100", "length_mm": 350, "width_mm": 210, "height_mm": 280, "material": "SS316L"},
        "errors": []
    }
    result = generate_cad(state)
    assert "cad_paths" in result
    assert len(result["cad_paths"]) >= 1
    assert len(result.get("errors", [])) == 0

def test_generate_cad_missing_specs():
    state = {"errors": []}
    result = generate_cad(state)
    assert "errors" in result
    assert any("extracted_specs missing" in e for e in result["errors"])
    assert "cad_paths" in result  # Fallback to defaults should still generate files
