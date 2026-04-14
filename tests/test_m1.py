import pytest
import os
from app.nodes.m1.node import extract_specs

# =========================
# 1. PROMPT SIMPLE
# =========================
def test_m1_with_prompt():
    state = {
        "input_file":   None,
        "input_prompt": "Butterfly valve DN100 PN16 stainless steel water 120°C"
    }
    result = extract_specs(state)
    assert "M1_result" in result

    m1    = result["M1_result"]
    specs = m1.get("specs", {})

    assert isinstance(specs, dict)
    assert "diameters"    in specs
    assert "materials"    in specs
    assert "temperatures" in specs
    assert any("dn100" in d.lower() for d in specs["diameters"])
    assert any("stainless" in m     for m in specs["materials"])

# =========================
# 2. VIDE
# =========================
def test_m1_empty():
    state = {
        "input_file":   None,
        "input_prompt": ""
    }
    result = extract_specs(state)
    assert "M1_result" in result
    assert isinstance(result["M1_result"], dict)

# =========================
# 3. STRUCTURE COMPLÈTE
# =========================
def test_m1_structure():
    state = {
        "input_file":   None,
        "input_prompt": "Valve DN50 PN10 carbon steel oil 200°C API 600"
    }
    result = extract_specs(state)

    m1    = result["M1_result"]
    assert "specs"    in m1
    assert "metadata" in m1

    specs = m1["specs"]
    for key in ["diameters", "pressures", "materials",
                "temperatures", "fluids", "certifications", "valve_types"]:
        assert key in specs

# =========================
# 4. ERREUR STATE VIDE
# =========================
def test_m1_empty_state():
    state = {}
    result = extract_specs(state)
    assert "M1_result" in result

# =========================
# 5. OUTPUT FILE SAUVEGARDÉ
# =========================
def test_m1_output_file_saved():
    state = {
        "input_file":   None,
        "input_prompt": "Valve DN200 PN25 carbon steel steam 300°C"
    }
    result = extract_specs(state)
    m1     = result["M1_result"]

    assert "output_file" in m1
    assert os.path.exists(m1["output_file"])

# =========================
# 6. METADATA PRÉSENT
# =========================
def test_m1_metadata():
    state = {
        "input_file":   None,
        "input_prompt": "Gate valve DN300 PN40 inconel gas 400°C ATEX SIL2"
    }
    result = extract_specs(state)
    m1     = result["M1_result"]

    assert "metadata" in m1
    meta = m1["metadata"]
    assert "source"     in meta
    assert "confidence" in meta

# =========================
# 7. PDF EXISTANT
# =========================
def test_m1_with_pdf():
    pdf_path = "data/sample.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip("sample.pdf non disponible")

    state = {
        "input_file":   pdf_path,
        "input_prompt": ""
    }
    result = extract_specs(state)
    assert "M1_result" in result

    m1    = result["M1_result"]
    specs = m1.get("specs", {})
    assert isinstance(specs, dict)
    assert m1.get("text_length", 0) > 0

# =========================
# 8. PDF INEXISTANT
# =========================
def test_m1_with_missing_pdf():
    state = {
        "input_file":   "data/fichier_inexistant.pdf",
        "input_prompt": ""
    }
    result = extract_specs(state)
    assert "M1_result" in result

# =========================
# 9. TEXT LENGTH PRÉSENT
# =========================
def test_m1_text_length():
    state = {
        "input_file":   None,
        "input_prompt": "Butterfly valve DN150 PN16 cast iron water 80°C ISO 5752"
    }
    result = extract_specs(state)
    m1     = result["M1_result"]

    assert "text_length" in m1
    assert isinstance(m1["text_length"], int)
    assert m1["text_length"] > 0

# =========================
# 10. NORMALISATION DES SPECS
# =========================
def test_m1_normalization():
    state = {
        "input_file":   None,
        "input_prompt": "Valve DN 100 PN 16 Carbon Steel Water 120 °C"
    }
    result = extract_specs(state)
    specs  = result["M1_result"].get("specs", {})

    # Les diameters doivent être normalisés en "dn100" (sans espace)
    diameters = [d.lower() for d in specs.get("diameters", [])]
    assert any("dn100" in d for d in diameters)

    # Les pressures doivent être normalisées en "pn16"
    pressures = [p.lower() for p in specs.get("pressures", [])]
    assert any("pn16" in p for p in pressures)