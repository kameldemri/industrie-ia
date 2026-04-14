"""
Tests — Module 8: Digital Twin + Predictive Maintenance
========================================================
Kaggle AI4I 2020 dataset version

Run all:        pytest tests/test_m8.py -v
Run runner:     pytest tests/test_m8.py -v -s -k "runner"
"""

import json
import os
import pytest

from app.nodes.m8.node import (
    build_catalog,
    _detect_anomalies,
    _load_kaggle_dataset,
    _simulate_ai4i_schema,
    _compute_health_status,
    _compute_risk_score,
    _maintenance_recommendation,
    _get_thresholds,
    DEFAULT_THRESHOLDS,
    KAGGLE_CSV_PATH,
)


# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def full_state():
    return {
        "extracted_specs": {
            "product_name": "Vanne DN100 PN40",
            "quantity":     200,
            "material":     "Inox 316L",
            "pressure":     "PN40",
        },
        "tco_data": {
            "total_tco_usd":       87_500,
            "production_cost_usd": 52_000,
        },
        "plan": {
            "financials": {
                "npv":     34_200,
                "roi_3yr": 28.5,
            }
        },
        "errors": [],
    }


@pytest.fixture
def thresholds():
    return DEFAULT_THRESHOLDS.copy()


# ═══════════════════════════════════════════════════════════════════
# 1 — BASIC CONTRACT
# ═══════════════════════════════════════════════════════════════════

def test_m8_fallback_empty_state():
    result = build_catalog({})
    assert "catalog_data" in result
    assert "cad_paths"    in result
    assert "errors"       in result
    assert result["errors"] == []


def test_m8_output_keys_present():
    catalog = build_catalog({})["catalog_data"]
    for key in ("product", "quantity", "material", "digital_twin",
                "maintenance", "cad_files", "tco_summary",
                "business_intelligence", "metadata"):
        assert key in catalog, f"Missing key: {key}"


def test_m8_cad_paths_count():
    assert len(build_catalog({})["cad_paths"]) == 3


def test_m8_metadata_pipeline():
    meta = build_catalog({})["catalog_data"]["metadata"]
    assert meta["pipeline"] == "INDUSTRIE IA — OpenIndustry Algérie"
    assert "Kaggle" in meta["schema"]


# ═══════════════════════════════════════════════════════════════════
# 2 — PRODUCT / SPECS PROPAGATION
# ═══════════════════════════════════════════════════════════════════

def test_m8_product_name():
    state = {"extracted_specs": {"product_name": "Vanne DN100 PN40"}}
    assert build_catalog(state)["catalog_data"]["product"] == "Vanne DN100 PN40"


def test_m8_quantity():
    state = {"extracted_specs": {"product_name": "X", "quantity": 500}}
    assert build_catalog(state)["catalog_data"]["quantity"] == 500


def test_m8_material():
    state = {"extracted_specs": {"product_name": "X", "material": "Inox 316L"}}
    assert build_catalog(state)["catalog_data"]["material"] == "Inox 316L"


def test_m8_default_product_name():
    assert build_catalog({})["catalog_data"]["product"] == "industrial_part"


# ═══════════════════════════════════════════════════════════════════
# 3 — THRESHOLD RESOLVER (M1 spec-aware)
# ═══════════════════════════════════════════════════════════════════

def test_thresholds_valve_temp():
    t = _get_thresholds({"product_name": "vanne DN100", "pressure": "PN40"})
    assert t["temp_high"] == 120.0


def test_thresholds_pump_temp():
    t = _get_thresholds({"product_name": "pompe centrifuge"})
    assert t["temp_high"] == 90.0


def test_thresholds_pressure_from_pn():
    t = _get_thresholds({"product_name": "vanne", "pressure": "PN40"})
    assert t["pressure_high"] == round(40 * 1.10, 1)
    assert t["pressure_medium"] == round(40 * 0.95, 1)


def test_thresholds_generic_fallback():
    t = _get_thresholds({})
    assert t["temp_high"] == DEFAULT_THRESHOLDS["temp_high"]


def test_thresholds_in_catalog(full_state):
    catalog = build_catalog(full_state)["catalog_data"]
    dt = catalog["digital_twin"]
    assert "thresholds" in dt
    # Valve PN40 → temp_high should be 120
    assert dt["thresholds"]["temp_high"] == 120.0


# ═══════════════════════════════════════════════════════════════════
# 4 — KAGGLE DATASET LOADING
# ═══════════════════════════════════════════════════════════════════

def test_dataset_loads_without_crash():
    rows, label = _load_kaggle_dataset(20)
    assert isinstance(rows, list)
    assert len(rows) == 20
    assert isinstance(label, str)


def test_dataset_source_label():
    _, label = _load_kaggle_dataset(5)
    assert "Kaggle" in label or "simulated" in label.lower()


def test_dataset_row_schema():
    """Every row must have the AI4I 2020 columns."""
    rows, _ = _load_kaggle_dataset(5)
    for row in rows:
        for field in ("cycle", "time", "temperature", "rpm",
                      "torque_nm", "tool_wear_min",
                      "machine_failure", "failure_flags"):
            assert field in row, f"Missing field: {field}"


def test_dataset_failure_flags_structure():
    rows, _ = _load_kaggle_dataset(5)
    for row in rows:
        flags = row["failure_flags"]
        for flag in ("TWF", "HDF", "PWF", "OSF", "RNF"):
            assert flag in flags


def test_dataset_cycle_positive():
    rows, _ = _load_kaggle_dataset(5)
    for row in rows:
        assert row["cycle"] > 0


def test_dataset_custom_length():
    rows, _ = _load_kaggle_dataset(10)
    assert len(rows) == 10


def test_simulation_schema_matches_real():
    """Simulated data must have same schema as real CSV loader."""
    rows = _simulate_ai4i_schema(5)
    for row in rows:
        for field in ("cycle", "time", "temperature", "rpm",
                      "torque_nm", "tool_wear_min",
                      "machine_failure", "failure_flags"):
            assert field in row


def test_real_csv_loaded_if_present():
    """If real CSV exists, dataset_file should not say 'simulated'."""
    if not os.path.exists(KAGGLE_CSV_PATH):
        pytest.skip("Real CSV not present — testing simulation only")
    catalog = build_catalog({})["catalog_data"]
    assert catalog["digital_twin"]["dataset_file"] == KAGGLE_CSV_PATH


# ═══════════════════════════════════════════════════════════════════
# 5 — ANOMALY DETECTION  (AI4I logic)
# ═══════════════════════════════════════════════════════════════════

def test_anomaly_machine_failure_flag(thresholds):
    data = [{
        "cycle": 1, "time": 0,
        "machine_failure": 1,
        "temperature": 30.0, "tool_wear_min": 10,
        "rpm": 1500, "torque_nm": 40,
        "failure_flags": {"TWF": 1, "HDF": 0, "PWF": 0, "OSF": 0, "RNF": 0},
    }]
    alerts = _detect_anomalies(data, thresholds)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "HIGH"
    assert "Tool Wear Failure" in alerts[0]["failure_mode"]


def test_anomaly_high_tool_wear(thresholds):
    data = [{
        "cycle": 1, "time": 0,
        "machine_failure": 0,
        "temperature": 30.0, "tool_wear_min": 210,
        "rpm": 1500, "torque_nm": 40,
        "failure_flags": {"TWF": 0, "HDF": 0, "PWF": 0, "OSF": 0, "RNF": 0},
    }]
    alerts = _detect_anomalies(data, thresholds)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "HIGH"


def test_anomaly_medium_tool_wear(thresholds):
    data = [{
        "cycle": 1, "time": 0,
        "machine_failure": 0,
        "temperature": 30.0, "tool_wear_min": 160,
        "rpm": 1500, "torque_nm": 40,
        "failure_flags": {"TWF": 0, "HDF": 0, "PWF": 0, "OSF": 0, "RNF": 0},
    }]
    alerts = _detect_anomalies(data, thresholds)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "MEDIUM"


def test_anomaly_high_temperature(thresholds):
    data = [{
        "cycle": 1, "time": 0,
        "machine_failure": 0,
        "temperature": 90.0, "tool_wear_min": 10,
        "rpm": 1500, "torque_nm": 40,
        "failure_flags": {"TWF": 0, "HDF": 0, "PWF": 0, "OSF": 0, "RNF": 0},
    }]
    alerts = _detect_anomalies(data, thresholds)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "HIGH"


def test_anomaly_no_alert_healthy(thresholds):
    data = [{
        "cycle": 1, "time": 0,
        "machine_failure": 0,
        "temperature": 30.0, "tool_wear_min": 10,
        "rpm": 1500, "torque_nm": 40,
        "failure_flags": {"TWF": 0, "HDF": 0, "PWF": 0, "OSF": 0, "RNF": 0},
    }]
    assert _detect_anomalies(data, thresholds) == []


def test_anomaly_triggered_field(thresholds):
    data = [{
        "cycle": 1, "time": 0,
        "machine_failure": 0,
        "temperature": 30.0, "tool_wear_min": 210,
        "rpm": 1500, "torque_nm": 40,
        "failure_flags": {"TWF": 0, "HDF": 0, "PWF": 0, "OSF": 0, "RNF": 0},
    }]
    alerts = _detect_anomalies(data, thresholds)
    assert "triggered" in alerts[0]
    assert len(alerts[0]["triggered"]) > 0


def test_anomaly_empty_dataset(thresholds):
    assert _detect_anomalies([], thresholds) == []


# ═══════════════════════════════════════════════════════════════════
# 6 — HEALTH STATUS & RISK SCORE
# ═══════════════════════════════════════════════════════════════════

def test_health_stable():
    assert _compute_health_status([]) == "STABLE"


def test_health_unstable():
    assert _compute_health_status([{"severity": "MEDIUM"}]) == "UNSTABLE"


def test_health_critical():
    assert _compute_health_status([{"severity": "HIGH"}]) == "CRITICAL"


def test_health_critical_beats_medium():
    alerts = [{"severity": "MEDIUM"}, {"severity": "HIGH"}]
    assert _compute_health_status(alerts) == "CRITICAL"


def test_health_always_valid():
    status = build_catalog({})["catalog_data"]["digital_twin"]["health_status"]
    assert status in ("STABLE", "UNSTABLE", "CRITICAL")


def test_risk_score_bounds():
    score = build_catalog({})["catalog_data"]["digital_twin"]["risk_score"]
    assert 0.0 <= score <= 1.0


def test_risk_score_zero_on_empty():
    assert _compute_risk_score([], []) == 0.0


# ═══════════════════════════════════════════════════════════════════
# 7 — MAINTENANCE RECOMMENDATION
# ═══════════════════════════════════════════════════════════════════

def test_maintenance_keys(thresholds):
    rec = _maintenance_recommendation("STABLE", 0.0, thresholds)
    for key in ("action", "urgency", "risk_score",
                "estimated_rul", "data_source", "thresholds_used"):
        assert key in rec


def test_maintenance_kaggle_label(thresholds):
    rec = _maintenance_recommendation("STABLE", 0.0, thresholds)
    assert "Kaggle" in rec["data_source"]


def test_maintenance_critical(thresholds):
    rec = _maintenance_recommendation("CRITICAL", 0.9, thresholds)
    assert "shutdown" in rec["action"].lower() or "immediate" in rec["action"].lower()


def test_maintenance_rul_decreases(thresholds):
    rul_low  = _maintenance_recommendation("STABLE",   0.1, thresholds)["estimated_rul"]
    rul_high = _maintenance_recommendation("CRITICAL", 0.9, thresholds)["estimated_rul"]
    assert rul_high < rul_low


def test_maintenance_thresholds_used(thresholds):
    rec = _maintenance_recommendation("STABLE", 0.0, thresholds)
    assert "temp_high_c" in rec["thresholds_used"]


# ═══════════════════════════════════════════════════════════════════
# 8 — CAD FILES
# ═══════════════════════════════════════════════════════════════════

def test_cad_files_exist():
    for path in build_catalog({})["cad_paths"]:
        assert os.path.exists(path)


def test_cad_product_in_filename():
    state = {"extracted_specs": {"product_name": "Pompe A"}}
    for path in build_catalog(state)["cad_paths"]:
        assert "pompe_a" in path.lower()


def test_cad_extensions():
    exts = {os.path.splitext(p)[1] for p in build_catalog({})["cad_paths"]}
    assert exts == {".step", ".stl", ".dxf"}


def test_cad_no_backslash():
    for path in build_catalog({})["cad_paths"]:
        assert "\\" not in path


# ═══════════════════════════════════════════════════════════════════
# 9 — TCO (M6)
# ═══════════════════════════════════════════════════════════════════

def test_tco_total():
    state = {"tco_data": {"total_tco_usd": 50_000, "production_cost_usd": 30_000}}
    tco   = build_catalog(state)["catalog_data"]["tco_summary"]
    assert tco["total_tco"] == 50_000


def test_tco_production():
    state = {"tco_data": {"total_tco_usd": 50_000, "production_cost_usd": 30_000}}
    tco   = build_catalog(state)["catalog_data"]["tco_summary"]
    assert tco["production_cost"] == 30_000


def test_tco_defaults_zero():
    tco = build_catalog({})["catalog_data"]["tco_summary"]
    assert tco["total_tco"] == 0


# ═══════════════════════════════════════════════════════════════════
# 10 — BUSINESS INTELLIGENCE (M7)
# ═══════════════════════════════════════════════════════════════════

def test_bi_npv():
    state = {"plan": {"financials": {"npv": 34_200, "roi_3yr": 28.5}}}
    bi    = build_catalog(state)["catalog_data"]["business_intelligence"]
    assert bi["npv"] == 34_200


def test_bi_roi():
    state = {"plan": {"financials": {"npv": 34_200, "roi_3yr": 28.5}}}
    bi    = build_catalog(state)["catalog_data"]["business_intelligence"]
    assert bi["roi_3yr"] == 28.5


def test_bi_plan_alias():
    state = {"business_plan": {"financials": {"npv": 500, "roi_3yr": 10}}}
    bi    = build_catalog(state)["catalog_data"]["business_intelligence"]
    assert bi["npv"] == 500


def test_bi_none_when_missing():
    bi = build_catalog({})["catalog_data"]["business_intelligence"]
    assert bi["npv"]     is None
    assert bi["roi_3yr"] is None


# ═══════════════════════════════════════════════════════════════════
# 11 — FULL PIPELINE INTEGRATION
# ═══════════════════════════════════════════════════════════════════

def test_full_pipeline(full_state):
    result  = build_catalog(full_state)
    catalog = result["catalog_data"]

    assert result["errors"] == []
    assert catalog["product"]  == "Vanne DN100 PN40"
    assert catalog["quantity"] == 200
    assert catalog["material"] == "Inox 316L"
    assert catalog["tco_summary"]["total_tco"]     == 87_500
    assert catalog["business_intelligence"]["npv"] == 34_200
    assert len(result["cad_paths"]) == 3
    assert "digital_twin" in catalog
    assert "maintenance"  in catalog
    # Valve PN40 → thresholds adapted from M1
    assert catalog["digital_twin"]["thresholds"]["temp_high"] == 120.0


# ═══════════════════════════════════════════════════════════════════
# 12 — ERROR RESILIENCE
# ═══════════════════════════════════════════════════════════════════

def test_none_specs_no_crash():
    assert "catalog_data" in build_catalog({"extracted_specs": None})


def test_none_tco_no_crash():
    assert build_catalog({"tco_data": None})["catalog_data"]["tco_summary"]["total_tco"] == 0


def test_none_plan_no_crash():
    assert build_catalog({"plan": None})["catalog_data"]["business_intelligence"]["npv"] is None


def test_upstream_errors_propagated():
    result = build_catalog({"errors": ["M6 error: timeout"]})
    assert "M6 error: timeout" in result["errors"]


# ═══════════════════════════════════════════════════════════════════
# 13 — INTEGRATION RUNNER
#      pytest tests/test_m8.py -v -s -k "runner"
# ═══════════════════════════════════════════════════════════════════

MOCK_STATE = {
    "extracted_specs": {
        "product_name": "Vanne DN100 PN40",
        "quantity":     200,
        "material":     "Inox 316L",
        "pressure":     "PN40",
    },
    "tco_data": {
        "total_tco_usd":       87_500,
        "production_cost_usd": 52_000,
    },
    "plan": {
        "financials": {
            "npv":     34_200,
            "roi_3yr": 28.5,
        }
    },
    "errors": [],
}


def _save_outputs(catalog: dict):
    os.makedirs("outputs/m8", exist_ok=True)

    def jdump(data, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  ✔  {path}")

    jdump(catalog,                                        "outputs/m8/catalog.json")
    jdump(catalog["digital_twin"]["sensor_dataset"],      "outputs/m8/sensor_data.json")
    jdump(catalog["digital_twin"]["alerts"],              "outputs/m8/alerts.json")
    jdump(catalog["maintenance"],                         "outputs/m8/maintenance.json")


def _print_report(catalog: dict, cad_paths: list):
    dt    = catalog["digital_twin"]
    tco   = catalog["tco_summary"]
    bi    = catalog["business_intelligence"]
    maint = catalog["maintenance"]
    thr   = dt["thresholds"]
    icon  = {"HIGH": "🔴", "MEDIUM": "🟡"}

    print("\n" + "=" * 64)
    print("  MODULE 8 — DIGITAL TWIN REPORT")
    print(f"  {catalog['metadata']['pipeline']}")
    print(f"  Dataset : {dt['data_source']}")
    print("=" * 64)

    print(f"\n  Product  : {catalog['product']}")
    print(f"  Material : {catalog['material']}")
    print(f"  Quantity : {catalog['quantity']} units")

    print(f"\n── THRESHOLDS (from M1 specs) ──────────────────────────────")
    print(f"  Temp HIGH       : {thr['temp_high']}°C")
    print(f"  Temp MEDIUM     : {thr['temp_medium']}°C")
    print(f"  Tool Wear HIGH  : {thr['tool_wear_high']} min")
    print(f"  Pressure HIGH   : {thr['pressure_high']} bar")

    print(f"\n── DIGITAL TWIN STATUS ─────────────────────────────────────")
    print(f"  Health     : {dt['health_status']}")
    print(f"  Risk Score : {dt['risk_score']} / 1.00")
    print(f"  Cycles     : {dt['sensor_count']}")
    print(f"  Alerts     : {dt['alert_count']}  "
          f"(🔴 HIGH={dt['high_severity_count']}  "
          f"🟡 MEDIUM={dt['medium_severity_count']})")

    print(f"\n── PREDICTIVE MAINTENANCE ──────────────────────────────────")
    print(f"  Action   : {maint['action']}")
    print(f"  Est. RUL : {maint['estimated_rul']} cycles remaining")
    print(f"  Source   : {maint['data_source']}")

    if dt["alerts"]:
        print(f"\n── ALERTS ──────────────────────────────────────────────────")
        for a in dt["alerts"][:10]:
            triggered = ", ".join(a.get("triggered", []))
            modes     = ", ".join(a.get("failure_mode", [])) or "—"
            print(f"  {icon.get(a['severity'], '⚪')} cycle={a['cycle']:>3}  "
                  f"[{a['severity']:<6}]  {triggered}  | modes: {modes}")
        if len(dt["alerts"]) > 10:
            print(f"  ... and {len(dt['alerts']) - 10} more")

    print(f"\n── TCO (M6) ────────────────────────────────────────────────")
    print(f"  Total TCO       : ${tco['total_tco']:,.0f}")
    print(f"  Production Cost : ${tco['production_cost']:,.0f}")

    print(f"\n── BUSINESS INTELLIGENCE (M7) ──────────────────────────────")
    print(f"  NPV     : ${bi['npv']:,.0f}"  if bi["npv"]     is not None else "  NPV     : N/A")
    print(f"  ROI 3yr : {bi['roi_3yr']}%"  if bi["roi_3yr"] is not None else "  ROI 3yr : N/A")

    print(f"\n── CAD FILES ───────────────────────────────────────────────")
    for p in cad_paths:
        print(f"  📐 {p}")

    print("\n" + "=" * 64)


def test_m8_runner_and_save_outputs():
    """
    Full integration run — prints report and saves outputs/m8/*.json
    Run: pytest tests/test_m8.py -v -s -k "runner"
    """
    result    = build_catalog(MOCK_STATE)
    assert not result["errors"], f"Errors: {result['errors']}"

    catalog   = result["catalog_data"]
    cad_paths = result["cad_paths"]

    _print_report(catalog, cad_paths)
    _save_outputs(catalog)

    print("\n💾  Outputs saved:")
    for f in ("outputs/m8/catalog.json", "outputs/m8/sensor_data.json",
              "outputs/m8/alerts.json",  "outputs/m8/maintenance.json"):
        assert os.path.exists(f), f"Missing: {f}"

    dt = catalog["digital_twin"]
    print(f"\n✅  M8 complete — {dt['sensor_count']} cycles, "
          f"{dt['alert_count']} alerts, "
          f"health={dt['health_status']}, "
          f"RUL={catalog['maintenance']['estimated_rul']} cycles")
    print(f"    Dataset: {dt['data_source']}\n")