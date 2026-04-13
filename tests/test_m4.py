import pytest
from app.nodes.m4.node import source_suppliers


# =========================
# 1. BASIC TEST
# =========================
def test_source_suppliers_basic():
    state = {
        "M1_result": {
            "specs": {
                "materials": ["stainless steel"]
            }
        }
    }

    result = source_suppliers(state)

    assert "M4_result" in result
    assert isinstance(result["M4_result"], list)


# =========================
# 2. MULTIPLE MATERIALS
# =========================
def test_multiple_materials():
    state = {
        "M1_result": {
            "specs": {
                "materials": ["cf3m", "wcb"]
            }
        }
    }

    result = source_suppliers(state)

    assert "M4_result" in result
    assert isinstance(result["M4_result"], list)


# =========================
# 3. NO MATERIALS
# =========================
def test_no_materials():
    state = {
        "M1_result": {
            "specs": {}
        }
    }

    result = source_suppliers(state)

    assert "M4_result" in result
    assert "error" in result["M4_result"]


# =========================
# 4. EMPTY STATE
# =========================
def test_empty_state():
    state = {}

    result = source_suppliers(state)

    assert "M4_result" in result
    assert "error" in result["M4_result"]


# =========================
# 5. STRUCTURE VALIDATION
# =========================
def test_output_structure():
    state = {
        "M1_result": {
            "specs": {
                "materials": ["carbon steel"]
            }
        }
    }

    result = source_suppliers(state)

    if isinstance(result["M4_result"], list) and len(result["M4_result"]) > 0:
        item = result["M4_result"][0]

        assert "material" in item
        assert "suppliers" in item
        assert "top_exporters" in item