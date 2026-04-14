"""
NODE M4 — Source Suppliers
APIs utilisées (100% gratuites, SANS clé) :
  1. UN Comtrade public/v1/preview  → pays exportateurs par code HS
  2. Wikidata SPARQL                → entreprises industrielles par matériau
"""

import requests
import json
import os
import time
from typing import Dict, Any, List, Tuple
from datetime import datetime

# ─────────────────────────────────────────
# AUCUNE CLÉ REQUISE — tout est public
# ─────────────────────────────────────────

HEADERS_COMTRADE = {
    "User-Agent": "industrie-ia-agent/1.0",
}

HEADERS_WIKIDATA = {
    "User-Agent": "industrie-ia-agent/1.0 (contact: votre@email.com)",
    "Accept":     "application/sparql-results+json",
}

# ─────────────────────────────────────────
# MATERIAL → HS CODE
# ─────────────────────────────────────────
HS_MAP = {
    "carbon steel":    "7208",
    "steel":           "7208",
    "stainless steel": "7219",
    "cast iron":       "7201",
    "inconel":         "7502",
    "cf3m":            "7219",
    "cf8m":            "7219",
    "wcb":             "7208",
}

# ─────────────────────────────────────────
# MATERIAL → MOT-CLÉ WIKIDATA
# ─────────────────────────────────────────
WIKIDATA_KEYWORDS = {
    "carbon steel":    "steel",
    "steel":           "steel",
    "stainless steel": "stainless steel",
    "cast iron":       "cast iron",
    "inconel":         "nickel alloy",
    "cf3m":            "stainless steel",
    "cf8m":            "stainless steel",
    "wcb":             "carbon steel",
}

# ─────────────────────────────────────────
# REPORTER CODES → noms de pays
# ─────────────────────────────────────────
REPORTER_CODES = [
    156,   # China
    276,   # Germany
    392,   # Japan
    410,   # South Korea
    356,   # India
    840,   # USA
    643,   # Russia
    380,   # Italy
    76,    # Brazil
    704,   # Vietnam
    124,   # Canada
    36,    # Australia
    528,   # Netherlands
    203,   # Czech Republic
    616,   # Poland
]

COUNTRY_NAMES = {
    156: "China",
    276: "Germany",
    392: "Japan",
    410: "South Korea",
    356: "India",
    840: "USA",
    643: "Russia",
    380: "Italy",
    76:  "Brazil",
    704: "Vietnam",
    124: "Canada",
    36:  "Australia",
    528: "Netherlands",
    203: "Czech Republic",
    616: "Poland",
}

# ─────────────────────────────────────────
# EXTRACT MATERIALS FROM STATE
# ─────────────────────────────────────────
def extract_materials(state: Dict[str, Any]) -> List[str]:
    try:
        return state["M1_result"]["specs"]["materials"]
    except Exception as e:
        print(f"[M4] extract_materials error: {e}")
        return []

# ─────────────────────────────────────────
# API 1 — UN COMTRADE public/v1/preview
# Sans clé, sans compte, 100% gratuit
# ─────────────────────────────────────────
def get_export_data(hs_code: str) -> List[Dict]:
    results = []

    for reporter_code in REPORTER_CODES:
        try:
            url = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
            params = {
                "cmdCode":      hs_code,
                "flowCode":     "X",
                "period":       "2022",
                "reporterCode": reporter_code,
                "partnerCode":  0,
            }

            r = requests.get(
                url, params=params,
                headers=HEADERS_COMTRADE,
                timeout=15
            )
            r.raise_for_status()
            data = r.json()

            items = data.get("data", [])
            if items:
                val = items[0].get("primaryValue", 0) or 0
                if val > 0:
                    results.append({
                        "country":      COUNTRY_NAMES.get(reporter_code, str(reporter_code)),
                        "export_value": val,
                    })

            time.sleep(0.3)

        except Exception:
            time.sleep(0.3)
            continue

    results.sort(key=lambda x: x["export_value"], reverse=True)

    if results:
        print(f"  [Comtrade ✓] {len(results)} pays trouvés pour HS {hs_code}")
    else:
        print(f"  [Comtrade ⚠] Aucune donnée pour HS {hs_code}")

    return results[:10]

# ─────────────────────────────────────────
# API 2 — WIKIDATA SPARQL
# Sans clé, sans compte, 100% gratuit
# ─────────────────────────────────────────
def get_wikidata_companies(keyword: str) -> List[Dict]:
    sparql_query = f"""
SELECT DISTINCT ?company ?companyLabel ?countryLabel ?employees WHERE {{
  ?company wdt:P31 wd:Q4830453 .
  ?company rdfs:label ?label .
  FILTER(LANG(?label) = "en")
  FILTER(CONTAINS(LCASE(STR(?label)), "{keyword.lower()}"))
  OPTIONAL {{ ?company wdt:P17 ?country . }}
  OPTIONAL {{ ?company wdt:P1128 ?employees . }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
  }}
}}
LIMIT 8
"""
    try:
        url = "https://query.wikidata.org/sparql"
        params = {"query": sparql_query, "format": "json"}
        time.sleep(1)

        r = requests.get(
            url, params=params,
            headers=HEADERS_WIKIDATA,
            timeout=30
        )
        r.raise_for_status()
        data = r.json()

        results = []
        seen = set()
        for binding in data.get("results", {}).get("bindings", []):
            name    = binding.get("companyLabel", {}).get("value", "")
            country = binding.get("countryLabel", {}).get("value", "")
            emp_str = binding.get("employees",    {}).get("value", "")

            if not name or name in seen or len(name) < 3:
                continue
            seen.add(name)

            results.append({
                "name":      name,
                "country":   country,
                "employees": int(emp_str) if emp_str.isdigit() else None,
            })

        if results:
            print(f"  [Wikidata ✓] {len(results)} entreprises pour '{keyword}'")
        else:
            print(f"  [Wikidata ⚠] Aucun résultat pour '{keyword}'")
        return results

    except requests.exceptions.HTTPError as e:
        print(f"  [Wikidata ✗] HTTP {e.response.status_code}")
        return []
    except Exception as e:
        print(f"  [Wikidata ✗] {e}")
        return []

# ─────────────────────────────────────────
# ECONOMIC SCORE (0.5 → 10)
# ─────────────────────────────────────────
def compute_score(export_value: float) -> float:
    if not export_value:
        return 0.5
    score = (export_value / 1e10) * 10
    return round(min(10.0, max(0.5, score)), 1)

# ─────────────────────────────────────────
# BUILD SUPPLIERS LIST
# ─────────────────────────────────────────
def build_suppliers(material: str, hs_code: str) -> Tuple[List[Dict], List[Dict]]:
    suppliers = []
    mat_key   = material.lower().strip()

    # --- Pays exportateurs (Comtrade) ---
    top_exporters = get_export_data(hs_code)
    for e in top_exporters:
        suppliers.append({
            "type":    "country_exporter",
            "name":    e["country"],
            "country": e["country"],
            "score":   compute_score(e["export_value"]),
            "value":   e["export_value"],
        })

    # --- Entreprises industrielles (Wikidata) ---
    keyword = WIKIDATA_KEYWORDS.get(mat_key, material)
    for c in get_wikidata_companies(keyword):
        score = 3.0
        if c["employees"] and c["employees"] > 10000:
            score = 4.5
        elif c["employees"] and c["employees"] > 1000:
            score = 3.5

        suppliers.append({
            "type":      "company",
            "name":      c["name"],
            "country":   c["country"],
            "employees": c["employees"],
            "score":     score,
            "value":     None,
        })

    suppliers.sort(key=lambda x: x["score"], reverse=True)
    return suppliers[:8], top_exporters

# ─────────────────────────────────────────
# SAVE OUTPUT → dossier outputs/ existant
# ─────────────────────────────────────────
def save_output(state: Dict[str, Any], output_dir: str = "outputs") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath  = os.path.join(output_dir, f"M4_result_{timestamp}.json")

    payload = {
        "generated_at": datetime.now().isoformat(),
        "node":         "M4 - Source Suppliers",
        "apis_used":    [
            "UN Comtrade public/v1/preview (gratuit, sans clé)",
            "Wikidata SPARQL (gratuit, sans clé)",
        ],
        "M4_result": state.get("M4_result", []),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Output sauvegardé → {filepath}")
    return filepath

# ─────────────────────────────────────────
# MAIN NODE M4
# ─────────────────────────────────────────
def source_suppliers(state: Dict[str, Any]) -> Dict[str, Any]:
    print("\n" + "="*55)
    print("🔍 NODE M4 — Source Suppliers")
    print("   APIs: Comtrade public + Wikidata (0 clé requise)")
    print("="*55)

    # Cas erreur : state vide ou M1_result manquant
    if not state or "M1_result" not in state:
        state["M4_result"] = {"error": "M1_result manquant dans le state"}
        return state

    materials = extract_materials(state)

    # Cas erreur : pas de matériaux
    if not materials:
        state["M4_result"] = {"error": "Aucun matériau trouvé dans M1_result.specs"}
        return state

    results = []
    for m in materials:
        mat = m.lower().strip()
        hs  = HS_MAP.get(mat, "7208")

        print(f"\n📦 Matériau : {m}  |  HS : {hs}")
        suppliers, top_exporters = build_suppliers(mat, hs)
        print(f"  → {len(suppliers)} fournisseurs trouvés")

        results.append({
            "material":      m,
            "hs_code":       hs,
            "suppliers":     suppliers,
            "top_exporters": top_exporters,
        })

    state["M4_result"] = results

    # Sauvegarde dans outputs/
    try:
        save_output(state)
    except Exception as e:
        print(f"[M4] save_output error: {e}")

    return state


# Alias LangGraph
m4_node = source_suppliers


# ─────────────────────────────────────────
# TEST STANDALONE
# ─────────────────────────────────────────
if __name__ == "__main__":
    test_state = {
        "M1_result": {
            "specs": {
                "materials": [
                    "carbon steel",
                    "cast iron",
                    "inconel",
                    "cf3m",
                    "cf8m",
                    "steel",
                    "wcb",
                ]
            }
        }
    }

    result = source_suppliers(test_state)
    print("\n" + "="*55)
    print("📊 RÉSULTAT FINAL M4_result")
    print("="*55)
    print(json.dumps(result["M4_result"], indent=2, ensure_ascii=False))