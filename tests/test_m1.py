import pytest
from app.nodes.m1.node import extract_specs


# =========================
# TEST 1: Prompt simple
# =========================
def test_m1_with_prompt():
    state = {
        "input_file": None,
        "input_prompt": "Butterfly valve DN100 PN16 stainless steel water 120°C"
    }

    result = extract_specs(state)

    assert "M1_result" in result

    m1 = result["M1_result"]
    specs = m1.get("specs", {})

    assert isinstance(specs, dict)

    # Vérification champs
    assert "diameters" in specs
    assert "materials" in specs
    assert "temperatures" in specs

    # Vérification contenu
    assert any("dn100" in d.lower() for d in specs["diameters"])
    assert any("stainless" in m for m in specs["materials"])


# =========================
# TEST 2: Vide
# =========================
def test_m1_empty():
    state = {
        "input_file": None,
        "input_prompt": ""
    }

    result = extract_specs(state)

    assert "M1_result" in result
    assert isinstance(result["M1_result"], dict)


# =========================
# TEST 3: Structure complète
# =========================
def test_m1_structure():
    state = {
        "input_file": None,
        "input_prompt": "Valve DN50 PN10 carbon steel oil 200°C API 600"
    }

    result = extract_specs(state)

    m1 = result["M1_result"]

    assert "specs" in m1
    assert "metadata" in m1

    specs = m1["specs"]

    expected_keys = [
        "diameters",
        "pressures",
        "materials",
        "temperatures",
        "fluids",
        "certifications",
        "valve_types"
    ]

    for key in expected_keys:
        assert key in specs
