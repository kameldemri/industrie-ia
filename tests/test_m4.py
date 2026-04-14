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
    assert len(result["M4_result"]) == 2

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
    assert isinstance(result["M4_result"], list)
    assert len(result["M4_result"]) > 0

    item = result["M4_result"][0]
    assert "material"      in item
    assert "hs_code"       in item
    assert "suppliers"     in item
    assert "top_exporters" in item
    assert isinstance(item["suppliers"],     list)
    assert isinstance(item["top_exporters"], list)

# =========================
# 6. HS CODE CORRECT
# =========================
def test_hs_code_mapping():
    state = {
        "M1_result": {
            "specs": {
                "materials": ["carbon steel", "inconel", "cast iron"]
            }
        }
    }
    result = source_suppliers(state)
    items  = result["M4_result"]

    hs_by_material = {i["material"]: i["hs_code"] for i in items}
    assert hs_by_material["carbon steel"] == "7208"
    assert hs_by_material["inconel"]      == "7502"
    assert hs_by_material["cast iron"]    == "7201"

# =========================
# 7. SUPPLIERS STRUCTURE
# =========================
def test_suppliers_items_structure():
    state = {
        "M1_result": {
            "specs": {
                "materials": ["steel"]
            }
        }
    }
    result    = source_suppliers(state)
    suppliers = result["M4_result"][0]["suppliers"]

    for s in suppliers:
        assert "type"    in s
        assert "name"    in s
        assert "country" in s
        assert "score"   in s
        assert s["type"] in ("country_exporter", "company")
        assert isinstance(s["score"], (int, float))

# =========================
# 8. SCORE RANGE
# =========================
def test_score_range():
    state = {
        "M1_result": {
            "specs": {
                "materials": ["carbon steel"]
            }
        }
    }
    result    = source_suppliers(state)
    suppliers = result["M4_result"][0]["suppliers"]

    for s in suppliers:
        assert 0.0 <= s["score"] <= 10.0