"""Module 4: Source suppliers via open APIs"""
from typing import Dict, Any
from app.llm import get_llm
from app.state import PipelineState

def source_suppliers(state: PipelineState) -> Dict[str, Any]:
    """LangGraph node for Module 4."""
    llm = get_llm()
    try:
        return {"status_m4": "pending"}
    except Exception as e:
        return {"errors": state.get("errors", []) + [f"M4: {e}"]}
