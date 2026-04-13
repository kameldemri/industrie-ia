"""Module 6: Calculate 10 years Total Cost of Ownership"""

import os
import requests
import openpyxl
from datetime import datetime
from typing import Dict, Any
from app.llm import get_llm  # ✅ Added: project convention import
from app.state import PipelineState

# MOCK DATA aka fake data will be replaced when m1/m4/m5 are ready
# m1 will provide--> quantity via state["extracted_specs"]["quantity"]
# M4 will provide--> costs via state["suppliers"]
# M5 will provide--> discount via state["negotiation_transcript"]

#temp values
MOCK_QUANTITY            = 200
MOCK_UNIT_MATERIAL       = 450.0
MOCK_UNIT_MANUFACTURING  = 200.0
MOCK_UNIT_MAINTENANCE    = 50.0
MOCK_NEGOTIATED_DISCOUNT = 0.10

MOCK_INFLATION_RATES = [3.2, 3.5, 4.0, 3.8, 3.6, 3.4, 3.3, 3.5, 3.7, 3.9]



# read inputs from state (fallback to mock if missing)

def _read_inputs(state: PipelineState) -> Dict[str, Any]:
   #get all th esepcs and suplies is missing empty fallback
    specs= state.get("extracted_specs") or {}
    suppliers =state.get("suppliers") or []

    # quantity of m1 if avilable else use fake quantity= 200
    quantity = specs.get("quantity") or MOCK_QUANTITY

    #if m4 ready use real data else use fake data
    if suppliers and "unit_material_cost" in suppliers[0]:
        unit_material      = suppliers[0]["unit_material_cost"]
        unit_manufacturing = suppliers[0]["unit_manufacturing_cost"]
        unit_maintenance   = suppliers[0]["unit_maintenance_cost"]
    else:
        unit_material      = MOCK_UNIT_MATERIAL
        unit_manufacturing = MOCK_UNIT_MANUFACTURING
        unit_maintenance   = MOCK_UNIT_MAINTENANCE

    #if m5 ready use real data else use fake data
    discount = MOCK_NEGOTIATED_DISCOUNT
#print all the data
    return {
        "quantity": quantity,
        "unit_material": unit_material,
        "unit_manufacturing": unit_manufacturing,
        "unit_maintenance": unit_maintenance,
        "discount": discount,
    }


#fetch inflation from worls bank of algeria (bootcamp public api)


def _fetch_inflation(years: int = 10) -> list:#takes 10 years of data
    url = ("https://api.worldbank.org/v2/country/DZ/indicator/FP.CPI.TOTL.ZG?format=json")
    try:
        r = requests.get(url, timeout=8)#sends a req to the api wait 8 sec max
        r.raise_for_status()#if req failed show 404 error goes to  exept
        records = r.json()[1]#convert response to json where [1]---> actual data | [0] -->metdata
        rates = [float(x["value"]) for x in records if x.get("value") is not None] # loop over the records, take value ,ignore none, convert each value to value to float & store them in list rates
        if len(rates) < years:#if we got less then years needed
            rates += [rates[-1]] * (years - len(rates)) #data augmentation by repeating the last values of the data unitl we reach the required length
        print(f"[Module 6] world bank API OK — {len(rates)} values fetched") #chekk the fetched values
        return rates[:years]
    except Exception as e:#error handeler
        print(f"[Module 6] WORLD BANK API FAILED! ({e}) — using fallback")
        return MOCK_INFLATION_RATES[:years]



# calculate TCO
#input -> costes
#inflation_rates ->list of inflation per year
#years = 10 default is 10 years
#output return the tco value

def _compute_tco(inputs: Dict, inflation_rates: list, years: int = 10) -> Dict:
    q = inputs["quantity"]#nb units to produce 200
    disc= inputs["discount"]# negtiated discount (0-100%)
#calculate production cost (unit_material + unit_manufacturing) × quantity × (1 - discount)
    production_cost = (inputs["unit_material"] + inputs["unit_manufacturing"]) * q * (1 - disc)#(450 + 200) × 200 × 0.90 = 117,000 USD
    breakdown= [] #stores one dict per year
    cumulative= 1.0 #inflation multiplier start at 1 grows each year
    total= production_cost


    for i in range(years):
        cumulative *= (1 + inflation_rates[i] / 100)#update the inflation value each year
        yearly_maintenance = inputs["unit_maintenance"] * q * cumulative  ## inflated maintenance
        total += yearly_maintenance

        #dictionary fo each year
        breakdown.append({
            "year": i + 1,
            "inflation_rate_pct": inflation_rates[i],
            "cumulative_factor": round(cumulative, 4),
            "maintenance_cost_usd": round(yearly_maintenance, 2),
        })

    return {
        "quantity": q,
        "unit_material_usd": inputs["unit_material"],
        "unit_manufacturing_usd": inputs["unit_manufacturing"],
        "unit_maintenance_usd": inputs["unit_maintenance"],
        "negotiated_discount_pct": disc * 100,
        "production_cost_usd": round(production_cost, 2),
        "total_tco_usd": round(total, 2),
        "tco_per_unit_usd": round(total / q, 2),
        "years": years,
        "yearly_breakdown": breakdown,
        "calculated_at": datetime.now().isoformat(),
    }

# to Excel file

#turn result of the tco to excel format
#create folder  outputs non error if it already exists
# define path then create execl
#rename to TCO Summery
#fill the execl file with data
# save the excel outputs/tco_result.xlsx

def _export_excel(tco: Dict, output_dir: str = "/app/outputs") -> str:  # ✅ Changed: Docker-consistent path
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "tco_result.xlsx")

    wb  = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "TCO Summary"

    for row in [
        ["INDUSTRIE IA — TCO Report"],
        ["Generated at", tco["calculated_at"]],
        [],
        ["Quantity", tco["quantity"]],
        ["Unit Material (USD)", tco["unit_material_usd"]],
        ["Unit Manufacturing (USD)", tco["unit_manufacturing_usd"]],
        ["Unit Maintenance/yr (USD)", tco["unit_maintenance_usd"]],
        ["Discount (%)", tco["negotiated_discount_pct"]],
        [],
        ["Production Cost Year 0 (USD)", tco["production_cost_usd"]],
        ["TOTAL TCO 10 years (USD)", tco["total_tco_usd"]],
        ["TCO per Unit (USD)", tco["tco_per_unit_usd"]],
    ]:
        ws1.append(row)

    ws2 = wb.create_sheet("Yearly Breakdown")
    ws2.append(["Year", "Inflation (%)", "Cumulative Factor", "Maintenance (USD)"])
    for r in tco["yearly_breakdown"]:
        ws2.append([
            r["year"],
            r["inflation_rate_pct"],
            r["cumulative_factor"],
            r["maintenance_cost_usd"],
        ])

    wb.save(path)
    print(f"[Module 6] excel saved at {path}")
    return path


# LANGGRAPH NODE ENTRY POINT
#takes shared data betwin modules langGraph
#return dict

def calculate_tco(state: PipelineState) -> Dict[str, Any]:
    """LangGraph"""
    llm = get_llm()  # ✅ Added: project convention initialization (not used in M6 per bootcamp spec)
    print("[Module 6] TCO calculation starting")
    #print("its working !")
    #sxtract the data from m1 , m4 ,m5 ---> fetch infos or mock data
    try:
        inputs     = _read_inputs(state)
        inflation  = _fetch_inflation(years=10)
        tco        = _compute_tco(inputs, inflation, years=10)
        _export_excel(tco)

        print(f"[Module 6] TCO = ${tco['total_tco_usd']:,.2f} over 10 years")

        return {
            "tco_data": tco,
            "errors": state.get("errors", []),
        }

    except Exception as e:
        return {"errors": state.get("errors", []) + [f"Module 6: {e}"]}
