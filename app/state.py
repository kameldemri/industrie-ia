from typing import TypedDict, List, Optional, Dict, Any

class PipelineState(TypedDict):
    raw_pdf_path: Optional[str]
    extracted_specs: Optional[Dict[str, Any]]
    cad_paths: List[str]
    video_path: Optional[str]
    suppliers: List[Dict[str, Any]]
    negotiation_transcript: Optional[str]
    tco_data: Optional[Dict[str, Any]]
    business_plan_paths: List[str]
    twin_alerts: List[Dict[str, Any]]
    catalog_paths: List[str]
    errors: List[str]
