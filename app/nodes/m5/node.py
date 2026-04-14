"""Module 5: Simulated AI Negotiation with Suppliers"""
import json
from typing import Dict, Any, List
from app.llm import get_llm  # Convention import
from app.state import PipelineState

MOCK_SUPPLIERS = [
    {"name": "SupplierAlpha_DZ", "country": "Algeria", "base_price": 450.0},
    {"name": "SupplierBeta_FR", "country": "France", "base_price": 520.0},
    {"name": "SupplierGamma_CN", "country": "China", "base_price": 380.0}
]

def _build_prompt(part: str, material: str, quantity: int, suppliers: List[Dict]) -> str:
    supplier_lines = "\n".join([f"- {s['name']} ({s['country']}): ${s.get('base_price', 'N/A')}/unit" for s in suppliers[:3]])

    # Static JSON schema to avoid f-string brace escaping issues
    json_schema = """
{
  "transcript": [
    {"role": "buyer", "message": "Opening request with target price 15% below lowest bid."},
    {"role": "supplier", "name": "...", "message": "Counter-offer with volume discount."},
    {"role": "buyer", "message": "Final acceptance condition."}
  ],
  "final_prices": {"supplier_name": agreed_price_per_unit},
  "selected_supplier": "name",
  "discount_pct": number
}"""

    return f"""You are a procurement AI negotiating bulk orders for an Algerian SME.
Part: {part}
Material: {material}
Quantity: {quantity} units
Suppliers to negotiate with:
{supplier_lines}

Simulate a concise 2-turn negotiation. Output ONLY valid JSON matching this exact schema:
{json_schema}"""

def simulate_negotiation(state: PipelineState) -> Dict[str, Any]:
    """LangGraph node for Module 5."""
    llm = get_llm()  # Convention initialization
    errors = list(state.get("errors", []))
    specs = state.get("extracted_specs", {})
    suppliers = state.get("suppliers", [])

    part = specs.get("part_name", "Industrial Valve")
    material = specs.get("material", "Steel")
    quantity = specs.get("quantity", 200)

    if not suppliers:
        suppliers = MOCK_SUPPLIERS
        errors.append("M5: No suppliers in state. Using mock data.")

    try:
        prompt = _build_prompt(part, material, quantity, suppliers)
        response = llm.invoke(prompt)
        raw = response.content.strip()

        # Strip markdown JSON blocks if LLM adds them
        if raw.startswith("```json"): raw = raw.split("```json", 1)[1]
        if raw.endswith("```"): raw = raw[:-3]
        raw = raw.strip()

        result = json.loads(raw)
        discount = float(result.get("discount_pct", 10)) / 100.0

        return {
            "negotiation_transcript": result.get("transcript", []),
            "negotiated_prices": result.get("final_prices", {}),
            "selected_supplier": result.get("selected_supplier", suppliers[0]["name"]),
            "negotiated_discount": discount,
            "errors": errors
        }
    except Exception as e:
        errors.append(f"M5: Negotiation failed. Applying fallback discount. Error: {str(e)}")
        fallback_discount = 0.10
        return {
            "negotiation_transcript": [{"role": "system", "message": "AI negotiation unavailable. Fallback discount applied."}],
            "negotiated_prices": {s["name"]: s.get("base_price", 0) * (1 - fallback_discount) for s in suppliers},
            "selected_supplier": suppliers[0]["name"] if suppliers else "MockSupplier",
            "negotiated_discount": fallback_discount,
            "errors": errors
        }
