import requests
from typing import Dict, Any, List

HEADERS = {"User-Agent": "industrie-ia"}

# =========================
# MATERIAL → HS CODE
# =========================
HS_MAP = {
    "carbon steel": "7208",
    "steel": "7208",
    "cast iron": "7201",
    "inconel": "7502",
    "cf3m": "7208",
    "cf8m": "7208",
    "wcb": "7208"
}

# =========================
# EXTRACT MATERIALS
# =========================
def extract_materials(state):
    try:
        return state["M1_result"]["specs"]["materials"]
    except:
        return []

# =========================
# UN COMTRADE (REAL EXPORT COUNTRIES)
# =========================
def get_export_data(hs_code: str):
    try:
        url = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

        params = {
            "cmdCode": hs_code,
            "flowCode": "X",
            "period": "2022",
            "partnerCode": "all",
            "reporterCode": "all"
        }

        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        data = r.json()

        results = []

        for item in data.get("data", [])[:10]:
            results.append({
                "country": item.get("reporterDesc"),
                "export_value": item.get("primaryValue", 0)
            })

        return results

    except:
        return []

# =========================
# OPENCORPORATES (REAL COMPANIES)
# =========================
def get_companies(query: str):
    try:
        url = "https://api.opencorporates.com/v0.4/companies/search"

        params = {
            "q": query,
            "per_page": 5
        }

        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        data = r.json()

        results = []

        for c in data.get("results", {}).get("companies", []):
            comp = c.get("company", {})
            results.append({
                "name": comp.get("name"),
                "country": comp.get("jurisdiction_code"),
                "source": "OpenCorporates"
            })

        return results

    except:
        return []

# =========================
# ECONOMIC SCORE (REAL LOGIC)
# =========================
def compute_score(export_value: float):
    # log normalization (important)
    if not export_value:
        return 0.5

    score = export_value / 1e10
    return round(min(10, max(0.5, score)), 2)

# =========================
# MERGE SUPPLIERS
# =========================
def build_suppliers(material: str, hs_code: str):

    suppliers = []

    # 1. export countries → "industrial power"
    exports = get_export_data(hs_code)

    for e in exports:
        suppliers.append({
            "type": "country_exporter",
            "name": e["country"],
            "country": e["country"],
            "score": compute_score(e["export_value"]),
            "value": e["export_value"]
        })

    # 2. real companies (industrial actors)
    companies = get_companies(material)

    for c in companies:
        suppliers.append({
            "type": "company",
            "name": c["name"],
            "country": c["country"],
            "score": 3.0,  # base score for real company existence
            "value": None
        })

    # sort best first
    suppliers = sorted(suppliers, key=lambda x: x["score"], reverse=True)

    return suppliers[:8]

# =========================
# MAIN NODE M4
# =========================
def source_suppliers(state: Dict[str, Any]):

    materials = extract_materials(state)

    results = []

    for m in materials:

        mat = m.lower().strip()
        hs = HS_MAP.get(mat, "7208")

        suppliers = build_suppliers(mat, hs)

        results.append({
            "material": m,
            "hs_code": hs,
            "suppliers": suppliers
        })

    state["M4_result"] = results
    return state

m4_node = source_suppliers
