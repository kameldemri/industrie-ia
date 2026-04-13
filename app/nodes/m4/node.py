import requests
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
import os
import json
from datetime import datetime

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
COMTRADE_ENDPOINT = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

HEADERS = {"User-Agent": "industrie-ia/1.0"}

# =========================
# MATERIAL CLEAN
# =========================
def normalize_material(mat: str) -> str:
    mat = mat.lower()

    if "inconel" in mat:
        return "nickel alloy"
    if "cf8m" in mat or "cf3m" in mat:
        return "stainless steel"
    if "wcb" in mat:
        return "carbon steel"

    return mat.strip()


# =========================
# EXTRACT MATERIALS
# =========================
def extract_materials(state: Dict[str, Any]) -> List[str]:
    try:
        materials = state["M1_result"]["specs"]["materials"]
        return list(set([normalize_material(m) for m in materials]))
    except Exception:
        return []


# =========================
# WIKIDATA (STABLE + BIG TIMEOUT)
# =========================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def query_wikidata(material: str) -> List[Dict]:
    try:
        r = requests.get(
            WIKIDATA_ENDPOINT,
            params={
                "query": """
                SELECT ?company ?companyLabel ?countryLabel WHERE {
                  ?company wdt:P31 wd:Q783794 .
                  ?company wdt:P17 ?country .
                  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
                } LIMIT 10
                """,
                "format": "json"
            },
            headers=HEADERS,
            timeout=90   # 🔥 IMPORTANT FIX (plus stable)
        )

        r.raise_for_status()
        data = r.json()

        out = []
        for x in data.get("results", {}).get("bindings", []):
            out.append({
                "name": x.get("companyLabel", {}).get("value", ""),
                "country": x.get("countryLabel", {}).get("value", ""),
                "material": material,
                "source": "wikidata"
            })

        return out

    except Exception as e:
        print("WIKIDATA ERROR:", e)
        return []   # ❗ NO FAKE DATA


# =========================
# COMTRADE (STABLE)
# =========================
HS_MAP = {
    "stainless steel": "7219",
    "carbon steel": "7208",
    "cast iron": "7201",
    "nickel alloy": "7502"
}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def query_comtrade(material: str) -> List[Dict]:
    try:
        hs = HS_MAP.get(material)
        if not hs:
            return []

        r = requests.get(
            COMTRADE_ENDPOINT,
            params={
                "cmdCode": hs,
                "flowCode": "X",
                "period": "2022",
                "reporterCode": "all"
            },
            headers=HEADERS,
            timeout=90   # 🔥 IMPORTANT FIX
        )

        r.raise_for_status()
        data = r.json()

        return [
            {
                "country": x.get("reporterDesc", ""),
                "trade_value": x.get("primaryValue", 0),
                "material": material,
                "source": "comtrade"
            }
            for x in data.get("data", [])[:5]
        ]

    except Exception as e:
        print("COMTRADE ERROR:", e)
        return []   # ❗ NO FAKE DATA


# =========================
# SAVE OUTPUT FUNCTION
# =========================
def save_output(state: Dict[str, Any]) -> str:
    os.makedirs("outputs", exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"outputs/M4_{timestamp}.json"

    output_data = {
        "M1_result": state.get("M1_result", {}),
        "M4_result": state.get("M4_result", []),
        "status": "success"
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"💾 SAVED: {file_path}")

    return file_path


# =========================
# MAIN NODE M4 (NO CRASH VERSION)
# =========================
def source_suppliers(state: Dict[str, Any]) -> Dict[str, Any]:

    try:
        print("🔍 M4 START")

        materials = extract_materials(state)

        if not materials:
            raise ValueError("No materials extracted from M1")

        results = []

        for m in materials:
            print("➡ PROCESS:", m)

            suppliers = query_wikidata(m)
            trade = query_comtrade(m)

            results.append({
                "original_material": m,
                "normalized_material": normalize_material(m),
                "suppliers": suppliers,
                "trade_data": trade
            })

        state["M4_result"] = results

        # 🔥 SAVE FILE AUTOMATICALLY
        state["M4_output_file"] = save_output(state)

        return state

    except Exception as e:
        print("❌ M4 CRITICAL ERROR:", e)

        state["M4_result"] = []
        state["M4_error"] = str(e)
        state["M4_output_file"] = None

        return state
