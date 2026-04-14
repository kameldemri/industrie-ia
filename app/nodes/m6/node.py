"""
M6 total cost of ownership (TCO) calculator
inputs
M1: extracted_specs (quantity)
M4: suppliers (unit costs)
M5: negotiation (discount)
World Bank API: inflation rates (fallback included)
outputs
Excel file (.xlsx)
JSON file (.json)
10 year TCO projection
"""

from __future__ import annotations

import os
import json
import requests
import openpyxl
from datetime import datetime
from typing import Dict, Any, List
from app.state import PipelineState

# MOCK DATA (fallback layer)

MOCK_QUANTITY = 200

MOCK_UNIT_MATERIAL = 450.0
MOCK_UNIT_MANUFACTURING = 200.0
MOCK_UNIT_MAINTENANCE = 50.0

MOCK_DISCOUNT = 0.10

MOCK_INFLATION = [3.2, 3.5, 4.0, 3.8, 3.6, 3.4, 3.3, 3.5, 3.7, 3.9]


# INPUT RESOLUTION (M1 , M4 ,M5 → fallback safe)

def _read_inputs(state: PipelineState) -> Dict[str, Any]:
    specs = state.get("extracted_specs") or {}
    suppliers = state.get("suppliers") or []

    # M1 → quantity
    quantity = specs.get("quantity") or MOCK_QUANTITY

    # M4 → cost structure
    if suppliers and isinstance(suppliers[0], dict) and "unit_material_cost" in suppliers[0]:
        unit_material = suppliers[0]["unit_material_cost"]
        unit_manufacturing = suppliers[0]["unit_manufacturing_cost"]
        unit_maintenance = suppliers[0]["unit_maintenance_cost"]
    else:
        unit_material = MOCK_UNIT_MATERIAL
        unit_manufacturing = MOCK_UNIT_MANUFACTURING
        unit_maintenance = MOCK_UNIT_MAINTENANCE

    # FIX: M5 → discount (reads from negotiation_result if available, fallback to mock)
    negotiation = state.get("negotiation_result") or {}
    discount = negotiation.get("discount") or MOCK_DISCOUNT

    return {
        "quantity": quantity,
        "unit_material": unit_material,
        "unit_manufacturing": unit_manufacturing,
        "unit_maintenance": unit_maintenance,
        "discount": discount,
    }


# WORLD BANK API (inflation data)


def _fetch_inflation(years: int = 10) -> List[float]:
    url = "https://api.worldbank.org/v2/country/DZ/indicator/FP.CPI.TOTL.ZG?format=json"

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()

        data = res.json()[1]
        rates = [float(x["value"]) for x in data if x.get("value") is not None]

        # normalize to required years
        if len(rates) < years:
            rates += [rates[-1]] * (years - len(rates))

        return rates[:years]

    except Exception:
        return MOCK_INFLATION[:years]


# CORE TCO ENGINE


def _compute_tco(inputs: Dict, inflation: List[float], years: int = 10) -> Dict:
    q = inputs["quantity"]
    discount = inputs["discount"]

    base_cost = (inputs["unit_material"] + inputs["unit_manufacturing"]) * q
    production_cost = base_cost * (1 - discount)

    total = production_cost
    cumulative = 1.0
    breakdown = []

    for i in range(years):
        cumulative *= (1 + inflation[i] / 100)

        maintenance = inputs["unit_maintenance"] * q * cumulative
        total += maintenance

        breakdown.append({
            "year": i + 1,
            "inflation_rate_pct": inflation[i],
            "cumulative_factor": round(cumulative, 4),
            "maintenance_cost": round(maintenance, 2),
        })

    return {
        "quantity": q,
        "unit_material_usd": inputs["unit_material"],
        "unit_manufacturing_usd": inputs["unit_manufacturing"],
        "unit_maintenance_usd": inputs["unit_maintenance"],
        "discount_pct": discount * 100,

        "production_cost_usd": round(production_cost, 2),
        "total_tco_usd": round(total, 2),
        "tco_per_unit_usd": round(total / q, 2),

        "years": years,
        "yearly_breakdown": breakdown,
        "calculated_at": datetime.utcnow().isoformat()
    }

# EXPORT: EXCEL
# FIX: added unit cost rows so Module 7 can read them back from this file

def _export_excel(tco: Dict, path: str) -> str:
    os.makedirs("outputs", exist_ok=True)

    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "TCO Summary"

    ws.append(["Metric", "Value"])
    ws.append(["Quantity", tco["quantity"]])
    # FIX: these three rows were missing — Module 7 needs them when reading from Excel
    ws.append(["Unit Material (USD)", tco["unit_material_usd"]])
    ws.append(["Unit Manufacturing (USD)", tco["unit_manufacturing_usd"]])
    ws.append(["Unit Maintenance (USD)", tco["unit_maintenance_usd"]])
    ws.append(["Discount (%)", tco["discount_pct"]])
    # FIX: key name matches what Module 7 looks up in load_tco_from_excel()
    ws.append(["Production Cost Year 0 (USD)", tco["production_cost_usd"]])
    ws.append(["TCO per Unit (USD)", tco["tco_per_unit_usd"]])
    # FIX: key name matches what Module 7 looks up in load_tco_from_excel()
    ws.append(["TOTAL TCO 10 years (USD)", tco["total_tco_usd"]])

    ws2 = wb.create_sheet("Yearly Breakdown")
    ws2.append(["Year", "Inflation (%)", "Cumulative Factor", "Maintenance Cost (USD)"])

    for y in tco["yearly_breakdown"]:
        ws2.append([
            y["year"],
            y["inflation_rate_pct"],
            y["cumulative_factor"],
            y["maintenance_cost"],
        ])

    wb.save(path)
    return path



#  JSON


def _export_json(tco: Dict, path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tco, f, indent=2)
    return path



# LANGGRAPH NODE ENTRY POINT


def calculate_tco(state: PipelineState) -> Dict[str, Any]:
    """
    LangGraph entry node
    """

    try:
        inputs = _read_inputs(state)
        inflation = _fetch_inflation(10)
        tco = _compute_tco(inputs, inflation)

        os.makedirs("outputs", exist_ok=True)

        excel_path = _export_excel(tco, "outputs/tco_result.xlsx")
        json_path = _export_json(tco, "outputs/tco_result.json")

        return {
            "tco_data": tco,
            "tco_excel_path": excel_path,
            "tco_json_path": json_path,
            "errors": state.get("errors", [])
        }

    except Exception as e:
        return {
            "errors": state.get("errors", []) + [f"Module 6 error: {str(e)}"]
        }

# LOCAL TEST

if __name__ == "__main__":
    result = calculate_tco({})

    print("\n=== MODULE 6 RESULT ===\n")
    print(json.dumps(result["tco_data"], indent=2))
    print("\nExcel + JSON generated in /outputs")