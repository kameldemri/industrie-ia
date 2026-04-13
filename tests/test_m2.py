"""Tests for Module 2: CAD Generation"""
import os
import pytest
from app.nodes.m2.node import generate_cad


def test_generate_cad_success():
    state = {
        "extracted_specs": {
            "part_name": "Valve_DN100",
            "length_mm": 350,
            "width_mm": 210,
            "height_mm": 280,
            "material": "SS316L",
            "pressure": "40 bar"
        },
        "errors": []
    }
    result = generate_cad(state)
    assert "cad_paths" in result
    assert len(result["cad_paths"]) >= 1
    assert any(p.endswith(".dxf") for p in result["cad_paths"])
    assert len(result.get("errors", [])) == 0


def test_generate_cad_missing_specs():
    state = {"errors": []}
    result = generate_cad(state)
    assert "errors" in result
    assert any("extracted_specs missing" in e for e in result["errors"])
    assert "cad_paths" in result


def test_generate_cad_dxf_has_circles():
    """Confirm DXF contains circles (valve bore and pipes)"""
    import ezdxf
    state = {
        "extracted_specs": {
            "part_name": "Valve_DN100",
            "length_mm": 350,
            "width_mm": 210,
            "height_mm": 280,
            "material": "SS316L",
            "pressure": "40 bar"
        },
        "errors": []
    }
    result = generate_cad(state)
    dxf_path = next(p for p in result["cad_paths"] if p.endswith(".dxf"))
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    entity_types = [e.dxftype() for e in msp]
    assert "CIRCLE" in entity_types
    assert "LWPOLYLINE" in entity_types