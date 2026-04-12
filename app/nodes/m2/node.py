"""Module 2: Generate 2D/3D CAD plans from specs"""
from typing import Dict, Any
from app.llm import get_llm
from app.state import PipelineState

def generate_cad(state: PipelineState) -> Dict[str, Any]:
    """LangGraph node for Module 2."""
    llm = get_llm()
    try:
        return {"status_m2": "pending"}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"M2: {e}"]}
