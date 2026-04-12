"""Module 1: Extract technical specifications from PDF"""
from typing import Dict, Any
from app.llm import get_llm
from app.state import PipelineState

def extract_specs(state: PipelineState) -> Dict[str, Any]:
    """LangGraph node for Module 1."""
    llm = get_llm()
    try:
        return {"status_m1": "pending"}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"M1: {e}"]}
