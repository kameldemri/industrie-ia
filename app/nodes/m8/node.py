"""
Module 8: Digital Twin + Predictive Maintenance
================================================
Project: INDUSTRIE IA — OpenIndustry Algérie

Data source:
    Kaggle / UCI — AI4I 2020 Predictive Maintenance Dataset (public domain)
    https://www.kaggle.com/datasets/stephanmatzka/predictive-maintenance-dataset-ai4i-2020
    Expected file: data/sensors/ai4i2020.csv

    Columns used:
        UDI                      — unique cycle ID
        Air temperature [K]      → converted to °C
        Process temperature [K]  → converted to °C
        Rotational speed [rpm]
        Torque [Nm]
        Tool wear [min]
        Machine failure          — ground truth label
        TWF / HDF / PWF / OSF    — failure mode flags

Fallback:
    If CSV is not found, generates a faithful simulation of the same schema
    so the pipeline never crashes.

Pipeline integrations:
    ← M1 : extracted_specs  (product_name, quantity, material, pressure)
    ← M5 : suppliers
    ← M6 : tco_data         (total_tco_usd, production_cost_usd)
    ← M7 : plan             (financials.npv, financials.roi_3yr)
    → M9 : catalog_data, cad_paths

Outputs:
    outputs/m8/catalog.json
    outputs/m8/sensor_data.json
    outputs/m8/alerts.json
    outputs/m8/maintenance.json
    outputs/cad/<product>_*.{step,stl,dxf}
"""

from __future__ import annotations

import os
import random
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.state import PipelineState

# pandas is a standard dep (already in requirements.txt via openpyxl ecosystem)
try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False


# ══════════════════════════════════════════════════════════════════════════════
# DATASET PATH
# ══════════════════════════════════════════════════════════════════════════════

KAGGLE_CSV_PATH = "data/sensors/ai4i2020.csv"

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# Default thresholds (generic — overridden by _get_thresholds() when M1 data available)
DEFAULT_THRESHOLDS = {
    "temp_high":          85.0,   # °C
    "temp_medium":        80.0,   # °C
    "vibration_high":     0.8,    # g  (proxy: torque deviation)
    "vibration_medium":   0.5,    # g
    "pressure_high":      38.0,   # bar
    "tool_wear_high":     200,    # min (AI4I 2020 failure zone)
    "tool_wear_medium":   150,    # min
}

DEFAULT_TIMESTEPS = 20
CAD_FORMATS       = ["model.step", "model.stl", "model.dxf"]

MAINTENANCE_WINDOW = {
    "CRITICAL": "Immediate shutdown recommended",
    "UNSTABLE": "Schedule maintenance within 48h",
    "STABLE":   "Next scheduled inspection in 30 days",
}


# ══════════════════════════════════════════════════════════════════════════════
# THRESHOLD RESOLVER  — uses M1 specs when available
# ══════════════════════════════════════════════════════════════════════════════

def _get_thresholds(specs: dict) -> dict:
    """
    Adjusts alarm thresholds based on real product specs extracted by M1.
    Falls back to generic defaults if specs are missing.
    """
    thresholds = DEFAULT_THRESHOLDS.copy()

    product_name = str(specs.get("product_name", "")).lower()
    pressure_raw = str(specs.get("pressure", "")).replace("PN", "").strip()

    # Product-type detection
    is_valve = any(w in product_name for w in ["vanne", "valve", "robinet"])
    is_pump  = any(w in product_name for w in ["pompe", "pump"])

    if is_valve:
        thresholds["temp_high"]   = 120.0  # valves tolerate higher temps
        thresholds["temp_medium"] = 100.0
    elif is_pump:
        thresholds["temp_high"]   = 90.0
        thresholds["temp_medium"] = 80.0

    # Pressure rating from PDF (PN16, PN40, etc.)
    if pressure_raw.isdigit():
        pn = float(pressure_raw)
        thresholds["pressure_high"]   = round(pn * 1.10, 1)  # 10% over rated
        thresholds["pressure_medium"] = round(pn * 0.95, 1)  # 95% of rated

    return thresholds


# ══════════════════════════════════════════════════════════════════════════════
# DATASET LOADER — real Kaggle CSV with simulation fallback
# ══════════════════════════════════════════════════════════════════════════════

def _load_kaggle_dataset(n_samples: int = DEFAULT_TIMESTEPS) -> tuple[List[Dict], str]:
    """
    Loads real AI4I 2020 Kaggle dataset if available.
    Falls back to faithful simulation of the same schema.

    Returns:
        (rows, source_label)
    """
    if PANDAS_OK and os.path.exists(KAGGLE_CSV_PATH):
        return _load_from_csv(n_samples), "Kaggle AI4I 2020 — real dataset"
    else:
        return _simulate_ai4i_schema(n_samples), "Kaggle AI4I 2020 — simulated schema (place real CSV at data/sensors/ai4i2020.csv)"


def _load_from_csv(n_samples: int) -> List[Dict]:
    """
    Reads the real Kaggle CSV and converts to our internal schema.
    Samples n_samples rows evenly across the dataset (to cover full lifecycle).
    """
    df = pd.read_csv(KAGGLE_CSV_PATH)

    # Sample evenly across the dataset (captures full degradation curve)
    step  = max(1, len(df) // n_samples)
    df    = df.iloc[::step].head(n_samples).reset_index(drop=True)

    rows = []
    for i, row in df.iterrows():
        # Convert Kelvin → Celsius
        air_temp  = round(row["Air temperature [K]"]     - 273.15, 2)
        proc_temp = round(row["Process temperature [K]"] - 273.15, 2)

        rows.append({
            "cycle":         int(row["UDI"]),
            "time":          i,
            "product_type":  str(row.get("Type", "N/A")),
            "temperature":   proc_temp,          # process temp is the critical one
            "air_temperature": air_temp,
            "rpm":           int(row["Rotational speed [rpm]"]),
            "torque_nm":     float(row["Torque [Nm]"]),
            "tool_wear_min": int(row["Tool wear [min]"]),
            "machine_failure": int(row["Machine failure"]),
            "failure_flags": {
                "TWF": int(row.get("TWF", 0)),   # Tool Wear Failure
                "HDF": int(row.get("HDF", 0)),   # Heat Dissipation Failure
                "PWF": int(row.get("PWF", 0)),   # Power Failure
                "OSF": int(row.get("OSF", 0)),   # Overstrain Failure
                "RNF": int(row.get("RNF", 0)),   # Random Failure
            },
        })

    return rows


def _simulate_ai4i_schema(n_samples: int) -> List[Dict]:
    """
    Faithful simulation of the AI4I 2020 schema.
    Used as fallback when the real CSV is not present.
    Same columns, same degradation physics.
    """
    rows = []
    for i in range(n_samples):
        t = i / max(n_samples - 1, 1)  # 0→1 normalized time

        air_temp  = round(298.0 + t * 4.0  + random.gauss(0, 0.5), 1)
        proc_temp = round(air_temp + 10.0  + t * 2.0 + random.gauss(0, 0.3), 1)
        rpm       = int(1500 - t * 200 + random.gauss(0, 50))
        torque    = round(40.0 + t * 20.0 + random.gauss(0, 2), 1)
        tool_wear = int(t * 250 + abs(random.gauss(0, 3)))

        pwf = 1 if (rpm * torque < 3500 * 9) else 0
        osf = 1 if (tool_wear > 200 and torque > 55) else 0
        twf = 1 if (200 <= tool_wear <= 240) else 0
        hdf = 1 if (air_temp - proc_temp < -8.6 and rpm < 1380) else 0
        rnf = 1 if random.random() < 0.001 else 0
        mf  = 1 if (twf or hdf or pwf or osf or rnf) else 0

        rows.append({
            "cycle":           i + 1,
            "time":            i,
            "product_type":    random.choice(["L", "M", "H"]),
            "temperature":     round(proc_temp - 273.15, 2),
            "air_temperature": round(air_temp  - 273.15, 2),
            "rpm":             rpm,
            "torque_nm":       torque,
            "tool_wear_min":   tool_wear,
            "machine_failure": mf,
            "failure_flags":   {"TWF": twf, "HDF": hdf, "PWF": pwf, "OSF": osf, "RNF": rnf},
        })

    return rows


# ══════════════════════════════════════════════════════════════════════════════
# PREDICTIVE MAINTENANCE — anomaly detection on AI4I schema
# ══════════════════════════════════════════════════════════════════════════════

_FAILURE_FLAG_NAMES = {
    "TWF": "Tool Wear Failure",
    "HDF": "Heat Dissipation Failure",
    "PWF": "Power Failure",
    "OSF": "Overstrain Failure",
    "RNF": "Random Failure",
}


def _detect_anomalies(sensor_data: List[Dict], thresholds: dict) -> List[Dict]:
    """
    Anomaly detection using AI4I 2020 failure logic + threshold rules.

    Priority:
    1. machine_failure == 1 from real dataset → HIGH (ground truth)
    2. tool_wear > threshold                  → HIGH or MEDIUM
    3. temperature > threshold                → HIGH or MEDIUM
    """
    alerts = []

    for d in sensor_data:
        triggered    = []
        severity     = None
        failure_mode = []

        # ── Ground truth from Kaggle dataset ───────────────────────────────
        if d.get("machine_failure") == 1:
            severity = "HIGH"
            flags    = d.get("failure_flags", {})
            failure_mode = [_FAILURE_FLAG_NAMES[k] for k, v in flags.items() if v == 1]
            triggered.append("machine_failure=1")

        else:
            # ── Tool wear (AI4I primary failure indicator) ─────────────────
            tw = d.get("tool_wear_min", 0)
            if tw >= thresholds["tool_wear_high"]:
                triggered.append(f"tool_wear={tw}min")
                severity = "HIGH"
            elif tw >= thresholds["tool_wear_medium"]:
                triggered.append(f"tool_wear={tw}min")
                severity = "MEDIUM"

            # ── Temperature ────────────────────────────────────────────────
            temp = d.get("temperature", 0)
            if temp > thresholds["temp_high"]:
                triggered.append(f"temp={temp}°C")
                severity = "HIGH"
            elif temp > thresholds["temp_medium"] and severity != "HIGH":
                triggered.append(f"temp={temp}°C")
                severity = "MEDIUM"

        if severity and triggered:
            alerts.append({
                "cycle":        d["cycle"],
                "time":         d["time"],
                "severity":     severity,
                "message":      "Critical failure risk" if severity == "HIGH" else "Degradation warning",
                "triggered":    triggered,
                "failure_mode": failure_mode,
                "temperature":  d.get("temperature"),
                "tool_wear":    d.get("tool_wear_min"),
                "rpm":          d.get("rpm"),
                "torque_nm":    d.get("torque_nm"),
            })

    return alerts


def _compute_health_status(alerts: List[Dict]) -> str:
    if not alerts:
        return "STABLE"
    return "CRITICAL" if any(a["severity"] == "HIGH" for a in alerts) else "UNSTABLE"


def _compute_risk_score(alerts: List[Dict], sensor_data: List[Dict]) -> float:
    if not sensor_data:
        return 0.0
    return round(len(alerts) / len(sensor_data), 2)


def _maintenance_recommendation(health: str, risk: float, thresholds: dict) -> Dict:
    return {
        "action":         MAINTENANCE_WINDOW[health],
        "urgency":        health,
        "risk_score":     risk,
        "estimated_rul":  max(0, round((1.0 - risk) * DEFAULT_TIMESTEPS)),
        "data_source":    "Kaggle AI4I 2020 Predictive Maintenance Dataset",
        "thresholds_used": {
            "temp_high_c":      thresholds["temp_high"],
            "tool_wear_high_min": thresholds["tool_wear_high"],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# CAD GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _generate_cad(product_name: str, output_dir: str = "outputs/cad") -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    safe  = product_name.lower().replace(" ", "_")
    paths = []
    for fmt in CAD_FORMATS:
        path = os.path.join(output_dir, f"{safe}_{fmt}").replace("\\", "/")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# CAD placeholder — {product_name} — {fmt}\n")
            f.write(f"# Generated by Module 8 at {datetime.utcnow().isoformat()}\n")
        paths.append(path)
    return paths


# ══════════════════════════════════════════════════════════════════════════════
# INPUT READER
# ══════════════════════════════════════════════════════════════════════════════

def _read_inputs(state: PipelineState) -> Dict[str, Any]:
    specs         = state.get("extracted_specs")  or {}
    tco           = state.get("tco_data")         or {}
    suppliers     = state.get("suppliers")         or []
    business_plan = state.get("plan") or state.get("business_plan") or {}

    return {
        "product_name":  specs.get("product_name") or "industrial_part",
        "quantity":      specs.get("quantity", 200),
        "material":      specs.get("material", "N/A"),
        "specs":         specs,
        "tco":           tco,
        "suppliers":     suppliers,
        "business_plan": business_plan,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CORE BUILD
# ══════════════════════════════════════════════════════════════════════════════

def _build_catalog(inputs: Dict[str, Any]) -> Dict[str, Any]:
    thresholds              = _get_thresholds(inputs["specs"])
    sensor_data, src_label  = _load_kaggle_dataset()
    alerts                  = _detect_anomalies(sensor_data, thresholds)
    cad_files               = _generate_cad(inputs["product_name"])

    tco        = inputs["tco"]
    bp         = inputs["business_plan"]
    financials = bp.get("financials", {}) if isinstance(bp, dict) else {}

    health     = _compute_health_status(alerts)
    risk       = _compute_risk_score(alerts, sensor_data)
    maintenance = _maintenance_recommendation(health, risk, thresholds)

    high_count   = sum(1 for a in alerts if a["severity"] == "HIGH")
    medium_count = sum(1 for a in alerts if a["severity"] == "MEDIUM")

    return {
        "product":  inputs["product_name"],
        "quantity": inputs["quantity"],
        "material": inputs["material"],

        # ── Digital Twin ───────────────────────────────────────────────────
        "digital_twin": {
            "data_source":           src_label,
            "dataset_file":          KAGGLE_CSV_PATH if os.path.exists(KAGGLE_CSV_PATH) else "simulated",
            "sensor_dataset":        sensor_data,
            "sensor_count":          len(sensor_data),
            "alerts":                alerts,
            "alert_count":           len(alerts),
            "high_severity_count":   high_count,
            "medium_severity_count": medium_count,
            "health_status":         health,
            "risk_score":            risk,
            "thresholds":            thresholds,
        },

        # ── Predictive Maintenance ─────────────────────────────────────────
        "maintenance": maintenance,

        # ── CAD ────────────────────────────────────────────────────────────
        "cad_files": cad_files,

        # ── TCO (M6) ───────────────────────────────────────────────────────
        "tco_summary": {
            "total_tco":       tco.get("total_tco_usd", 0),
            "production_cost": tco.get("production_cost_usd", 0),
        },

        # ── Business Intelligence (M7) ─────────────────────────────────────
        "business_intelligence": {
            "npv":     financials.get("npv"),
            "roi_3yr": financials.get("roi_3yr"),
        },

        # ── Metadata ───────────────────────────────────────────────────────
        "metadata": {
            "module":       "M8 — Digital Twin",
            "generated_at": datetime.utcnow().isoformat(),
            "schema":       "Kaggle AI4I 2020 Predictive Maintenance",
            "pipeline":     "INDUSTRIE IA — OpenIndustry Algérie",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def build_catalog(state: PipelineState) -> Dict[str, Any]:
    """LangGraph node entry point for Module 8."""
    errors = list(state.get("errors", []))

    try:
        inputs  = _read_inputs(state)
        catalog = _build_catalog(inputs)

        return {
            "catalog_data": catalog,
            "cad_paths":    catalog["cad_files"],
            "errors":       errors,
        }

    except Exception as e:
        errors.append(f"Module 8 error: {str(e)}")
        return {
            "catalog_data": {},
            "cad_paths":    [],
            "errors":       errors,
        }