# INDUSTRIE IA — Multi-Agent Manufacturing Pipeline

> **Status:** Phase 2 — Core Modules Implemented (M2, M6, M9)
> **Timeline:** Bootcamp 2026 | Day 13+
> **License:** Open-source. Built exclusively with public APIs, open models, and zero proprietary dependencies.

---

## 📑 Table of Contents

- [Executive Summary](#-executive-summary)
- [System Architecture](#-system-architecture)
  - [Component Overview](#component-overview)
  - [Data Flow: PipelineState Contract](#data-flow-pipelinestate-contract)
  - [Fault Tolerance Design](#fault-tolerance-design)
- [Module Documentation](#-module-documentation)
  - [Module 1: PDF Specification Extraction](#module-1-pdf-specification-extraction) — Multi-stage PDF→OCR→LLM→regex pipeline with JSON normalization
  - [Module 2: CAD Generation](#module-2-cad-generation)
  - [Module 3: HD Presentation Video Generation](#module-3-hd-presentation-video-generation)
    - [Module 4: Supplier Sourcing via Public APIs](#module-4-supplier-sourcing-via-public-apis) — UN Comtrade + Wikidata integration with mock fallback
  - [Module 5: AI Supplier Negotiation Simulation](#module-5-ai-supplier-negotiation-simulation)
  - [Module 6: Total Cost of Ownership (TCO) Calculator](#module-6-total-cost-of-ownership-tco-calculator)
  - [Module 7: Business Plan Generator](#module-7-business-plan-generator)
  - [Module 8: Digital Twin & Predictive Maintenance](#module-8-digital-twin--predictive-maintenance)
  - [Module 9: Catalog Export](#module-9-catalog-export)
  - [Adding Module Documentation](#adding-module-documentation)
- [Development Standards](#-development-standards)
  - [Module Interface Contract](#module-interface-contract)
  - [Testing Approach](#testing-approach)
- [Project Structure](#-project-structure)
- [Setup and Execution](#-setup-and-execution)
- [Configuration](#-configuration)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#-roadmap)
- [References](#-references)

---

## Executive Summary

INDUSTRIE IA is an automated pipeline for transforming public technical documentation into complete manufacturing dossiers. The system ingests PDF engineering drawings, extracts structured specifications, generates CAD assets, sources suppliers via public APIs, calculates Total Cost of Ownership (TCO), and exports multi-format client deliverables.

The architecture is built on LangGraph for orchestration, FastAPI for service exposure, and Docker for deployment consistency. All components use open-source libraries and public data sources, ensuring zero licensing costs and full auditability.

---

## System Architecture

### Component Overview

| Component          | Technology                      | Responsibility                                             |
| ------------------ | ------------------------------- | ---------------------------------------------------------- |
| `app` container    | Python 3.11, FastAPI, LangGraph | Pipeline orchestration, module execution, API endpoints    |
| `ollama` container | Ollama runtime                  | Local LLM inference (Mistral, Qwen, Llama)                 |
| Host volume        | Docker bind mount               | Persistent output storage (`./outputs/` ↔ `/app/outputs/`) |

### Data Flow: PipelineState Contract

All modules communicate through a single typed dictionary, `PipelineState`, defined in `app/state.py`. This contract ensures type safety and decouples module implementations.

```python
# Simplified PipelineState definition
PipelineState = TypedDict(
    "PipelineState",
    {
        "raw_pdf_path": str,
        "extracted_specs": dict,
        "cad_paths": list[str],
        "suppliers": list[dict],
        "tco_data": dict,
        "catalog_paths": list[str],
        "errors": list[str],
        # ... additional keys as modules are added
    },
    total=False,  # Keys are optional to support partial execution
)
```

**Execution model:**

1. LangGraph initializes an empty `PipelineState`
2. Each module reads required keys, performs computation, returns a delta dict
3. LangGraph merges deltas into the shared state
4. Final state is returned to the API layer

### Fault Tolerance Design

The pipeline is designed for graceful degradation. If a module fails or receives incomplete input:

- Missing keys default to empty collections (`{}`, `[]`) or predefined fallback values
- Exceptions are caught at the node level; errors are appended to `state["errors"]`
- Execution continues to downstream modules where possible
- Final outputs include an audit trail of all warnings and fallbacks

This ensures the system produces usable partial results even when upstream modules are incomplete or external APIs are unavailable.

---

## Module Documentation

### Module 1: PDF Specification Extraction

**File:** `app/nodes/m1/node.py`  
**Function:** `extract_specs(state: PipelineState) -> dict`

#### Purpose

Extract structured industrial specifications from technical PDFs or scanned drawings using a multi-stage pipeline: native text extraction, OCR fallback, LLM parsing, and regex normalization. Outputs a validated JSON schema of diameters, pressures, materials, temperatures, fluids, certifications, and valve types.

#### Inputs (Read from PipelineState)

| Key            | Type        | Description                          | Fallback                  |
| -------------- | ----------- | ------------------------------------ | ------------------------- |
| `raw_pdf_path` | `str`       | Path to uploaded technical PDF       | `None` → prompt-only mode |
| `input_prompt` | `str`       | Manual specification hints from user | `""`                      |
| `errors`       | `list[str]` | Accumulated warnings from upstream   | `[]`                      |

#### Outputs (Returned to LangGraph)

| Key               | Type        | Description                                                         |
| ----------------- | ----------- | ------------------------------------------------------------------- |
| `extracted_specs` | `dict`      | Normalized specification dictionary with sorted, deduplicated lists |
| `m1_output_path`  | `str`       | Absolute path to raw extraction cache (`/app/outputs/M1_*.json`)    |
| `errors`          | `list[str]` | Updated error list with module-specific messages                    |

#### Implementation Details

**Multi-Stage Extraction Pipeline**

- **Native Text**: `pdfplumber` extracts selectable text with layout preservation
- **OCR Fallback**: `pytesseract` + `fitz` (PyMuPDF) renders pages to images when text extraction yields <50 characters
- **LLM Parsing**: `get_llm()` prompts structured JSON output matching bootcamp schema; strips markdown blocks for robust `json.loads()`
- **Regex Fallback**: Pattern-matches `DN\d+`, `PN\d+`, temperature ranges, material names, certifications, and valve types if LLM returns empty or malformed JSON

**Normalization & Validation**

- Standardizes formats: `DN 100` → `dn100`, `PN 16` → `pn16`, `-120 °C` → `-120°C`
- Deduplicates, lowercases, and sorts all lists for deterministic downstream consumption
- Caches raw output to `/app/outputs/` for auditability and demo inspection

**Graceful Degradation**

- Missing PDF → processes `input_prompt` only, logs warning
- LLM timeout/invalid JSON → triggers regex fallback pipeline
- Empty extraction → returns `{}` with preserved `errors` list; downstream modules activate mock defaults

#### Usage Example

```python
state = {
    "raw_pdf_path": "/app/data/sample_valve.pdf",
    "input_prompt": "",
    "errors": []
}
result = extract_specs(state)
# result["extracted_specs"]["diameters"] → ["dn100", "dn150"]
# result["extracted_specs"]["materials"] → ["stainless steel", "wcb"]
# result["extracted_specs"]["pressures"] → ["pn16", "pn40"]
```

---

### Module 2: CAD Generation

**File:** `app/nodes/m2/node.py`
**Function:** `generate_cad(state: PipelineState) -> dict`

#### Purpose

Generate 2D DXF and 3D IFC engineering drawings from extracted technical specifications.

#### Inputs (Read from PipelineState)

| Key               | Type        | Description                              | Fallback            |
| ----------------- | ----------- | ---------------------------------------- | ------------------- |
| `extracted_specs` | `dict`      | Technical specifications from Module 1   | `{}` (use defaults) |
| `errors`          | `list[str]` | Accumulated error messages from upstream | `[]`                |

#### Outputs (Returned to LangGraph)

| Key         | Type        | Description                                         |
| ----------- | ----------- | --------------------------------------------------- |
| `cad_paths` | `list[str]` | Absolute paths to generated `.dxf` and `.ifc` files |
| `errors`    | `list[str]` | Updated error list with module-specific messages    |

#### Implementation Details

**Specification Normalization**
Input specifications are validated against a Pydantic model to ensure geometric consistency:

```python
class CADSpecs(BaseModel):
    part_name: str = "INDUSTRIE_IA_Part"
    length_mm: float = Field(100.0, ge=0.01)
    width_mm: float = Field(100.0, ge=0.01)
    height_mm: float = Field(50.0, ge=0.01)
    material: str = "Steel"
```

Missing or invalid fields are filled with sensible defaults; validation failures trigger fallback construction using available fields.

**DXF Generation (ezdxf)**

- Creates a new DXF document in R2018 format with millimeter units (`$INSUNITS = 4`)
- Draws a closed polyline representing the part outline (`length_mm × width_mm`)
- Adds a center circle (radius = 15% of minimum dimension) as a placeholder for bores or mounting features
- Annotates with part name and material using model-space text entities
- Saves to `/app/outputs/{part_name}_2D.dxf`

**IFC Generation (ifcopenshell)**

- Initializes a minimal IFC4 file with project metadata
- Creates an `IfcBuildingElementProxy` entity populated with part name and material description
- Establishes basic spatial structure via `IfcRelAggregates`
- Saves to `/app/outputs/{part_name}_3D.ifc`

**Error Handling**
Each generation step is wrapped in a try-except block. Failures are logged to `state["errors"]` but do not halt execution, allowing partial output generation.

#### Usage Example

```python
state = {
    "extracted_specs": {
        "part_name": "Valve_DN100",
        "length_mm": 350,
        "width_mm": 210,
        "height_mm": 280,
        "material": "SS316L"
    },
    "errors": []
}
result = generate_cad(state)
# result["cad_paths"] → ["/app/outputs/Valve_DN100_2D.dxf", "/app/outputs/Valve_DN100_3D.ifc"]
```

---

### Module 3: HD Presentation Video Generation

**File:** `app/nodes/m3/node.py`
**Function:** `generate_video(state: PipelineState) -> dict`

#### Purpose

Convert 2D DXF engineering drawings into a dynamic 3D presentation video using Manim. Parses geometric entities, normalizes dimensions, generates a scene script, and renders an MP4/AVI file with camera rotation, layer-based coloring, and technical annotations.

#### Inputs (Read from PipelineState)

| Key               | Type        | Description                                                 | Fallback |
| ----------------- | ----------- | ----------------------------------------------------------- | -------- |
| `cad_paths`       | `list[str]` | File paths from Module 2 (expects `.dxf`)                   | `[]`     |
| `extracted_specs` | `dict`      | Part metadata (name, material, pressure) for on-screen text | `{}`     |
| `errors`          | `list[str]` | Accumulated warnings from upstream                          | `[]`     |

#### Outputs (Returned to LangGraph)

| Key              | Type           | Description                                           |
| ---------------- | -------------- | ----------------------------------------------------- |
| `video_path`     | `str`          | Absolute path to rendered `.mp4` file                 |
| `video_path_avi` | `str` / `None` | Path to `.avi` conversion (if `ffmpeg` available)     |
| `m3_script`      | `str`          | Path to the dynamically generated Manim Python script |
| `status_m3`      | `str`          | Execution state (`"done"` or `"failed"`)              |
| `errors`         | `list[str]`    | Updated error list with module-specific messages      |

#### Implementation Details

**DXF Parsing & Dimension Normalization**

- Reads `.dxf` via `ezdxf` and extracts `CIRCLE` and `LWPOLYLINE` entities
- Scales raw millimeter coordinates to Manim's normalized unit space (0.3–3.0 range) to prevent rendering overflow or microscopic geometry
- Maps DXF layer names to semantic roles (`BODY`, `BORE`, `INLET`, `OUTLET`, `FLANGE`)

**Dynamic Script Generation**

- Builds a complete `manim.ThreeDScene` class as a string template
- Embeds parsed objects, layer colors, and M1-extracted specs directly into the script
- Uses conditional positioning logic (e.g., flanges top/bottom, bore at origin, inlet/outlet on axes) to assemble a coherent 3D representation

**Rendering Pipeline**

- Executes Manim via `subprocess.run` with low-quality (`-ql`) settings for fast demo turnaround (~10–20s render)
- Enables ambient camera rotation (`begin_ambient_camera_rotation`) for 3D showcase
- Optionally converts MP4 to AVI using `ffmpeg` for broader compatibility
- All errors are caught and appended to `state["errors"]`; the node never raises unhandled exceptions

**Graceful Degradation**

- Missing `cad_paths` or `.dxf` file → logs warning, returns `"failed"` status
- Empty DXF parsing → falls back to a default placeholder box
- `ffmpeg` missing → AVI output skipped, MP4 retained

#### Usage Example

```python
state = {
    "cad_paths": ["/app/outputs/Valve_DN100_2D.dxf", "/app/outputs/Valve_DN100_3D.ifc"],
    "extracted_specs": {"part_name": "Valve DN100", "pressure": "PN40", "material": "SS316L"},
    "errors": []
}
result = generate_video(state)
# result["status_m3"] → "done"
# result["video_path"] → "outputs/videos/m3_<uuid>/480p15/GeneratedScene.mp4"
```

---

### Module 4: Supplier Sourcing via Public APIs

**File:** `app/nodes/m4/node.py`  
**Function:** `source_suppliers(state: PipelineState) -> dict`

#### Purpose

Identify and rank industrial material suppliers using two free, keyless public APIs: UN Comtrade (export volume statistics by HS code) and Wikidata SPARQL (global company registry). Returns a structured supplier list with economic scoring, employee count, and unit cost estimates for downstream negotiation and TCO calculation.

#### Inputs (Read from PipelineState)

| Key               | Type        | Description                                             | Fallback              |
| ----------------- | ----------- | ------------------------------------------------------- | --------------------- |
| `extracted_specs` | `dict`      | Product specifications from Module 1 (`materials` list) | `{}` → mock suppliers |
| `errors`          | `list[str]` | Accumulated warnings from upstream                      | `[]`                  |

#### Outputs (Returned to LangGraph)

| Key              | Type         | Description                                                                  |
| ---------------- | ------------ | ---------------------------------------------------------------------------- |
| `suppliers`      | `list[dict]` | Ranked company list with name, country, employee count, and unit cost fields |
| `m4_output_path` | `str`        | Path to raw API response cache (for audit)                                   |
| `errors`         | `list[str]`  | Updated error list with module-specific messages                             |

#### Implementation Details

**Public API Integration**

- **UN Comtrade**: Queries `public/v1/preview/C/A/HS` endpoint with HS codes mapped from material names (e.g., `stainless steel` → `7219`). Returns export values by reporter country across 15 major manufacturing economies.
- **Wikidata SPARQL**: Searches for industrial companies (`wdt:P31 wd:Q4830453`) with labels matching material keywords. Returns company name, country, and employee count.
- Both APIs require zero authentication; rate limiting handled via `time.sleep()` and robust exception handling.

**Supplier Scoring & Ranking**

- Export volume → economic influence score (0.5–10) via linear scaling
- Employee count → company reliability score (3.0–4.5)
- Final list sorted by combined score; top 8 retained for downstream modules

**Cost Field Injection**

- Public APIs do not return unit pricing. Mock cost fields are injected for M5/M6 compatibility:
  ```python
  {"unit_material_cost": 400.0, "unit_manufacturing_cost": 170.0, "unit_maintenance_cost": 42.0}
  ```
- M5 AI negotiation can adjust these values; M6 TCO engine consumes them directly.

**Graceful Degradation**

- Missing materials → returns `MOCK_SUPPLIERS` with logged warning
- API timeout/HTTP error → catches exception, falls back to mocks
- All errors appended to `state["errors"]`; pipeline continues without interruption

#### Usage Example

```python
state = {
    "extracted_specs": {"materials": ["stainless steel", "carbon steel"]},
    "errors": []
}
result = source_suppliers(state)
# result["suppliers"][0] → {"name": "TestCorp", "country": "Algeria",
#                           "unit_material_cost": 400.0, "score": 4.5, ...}
# result["errors"] → [] or warning list
```

---

### Module 5: AI Supplier Negotiation Simulation

**File:** `app/nodes/m5/node.py`
**Function:** `simulate_negotiation(state: PipelineState) -> dict`

#### Purpose

Simulate an AI-driven procurement negotiation with multiple suppliers to secure optimal pricing and terms. Uses a structured LLM prompt to generate a realistic negotiation transcript, final agreed prices, and a negotiated discount percentage for downstream cost calculations.

#### Inputs (Read from PipelineState)

| Key               | Type         | Description                                                             | Fallback                                |
| ----------------- | ------------ | ----------------------------------------------------------------------- | --------------------------------------- |
| `extracted_specs` | `dict`       | Product specifications (part name, material, quantity, pressure rating) | `{}`                                    |
| `suppliers`       | `list[dict]` | Supplier list from Module 4 (name, country, base price)                 | `MOCK_SUPPLIERS` (3 predefined entries) |
| `errors`          | `list[str]`  | Accumulated warnings from upstream                                      | `[]`                                    |

#### Outputs (Returned to LangGraph)

| Key                      | Type               | Description                                       |
| ------------------------ | ------------------ | ------------------------------------------------- |
| `negotiation_transcript` | `list[dict]`       | Structured dialogue log: role, message, timestamp |
| `negotiated_prices`      | `dict[str, float]` | Final agreed price per unit per supplier          |
| `selected_supplier`      | `str`              | Name of the chosen supplier after negotiation     |
| `negotiated_discount`    | `float`            | Discount factor (0.0–1.0) applied to base pricing |
| `errors`                 | `list[str]`        | Updated error list with module-specific messages  |

#### Implementation Details

**Structured Prompt Engineering**

- Builds a context-rich prompt embedding product specs, quantity, and supplier list
- Enforces strict JSON output schema via explicit instructions to prevent hallucination
- Strips markdown code blocks (` ```json `) if added by the LLM for robust parsing

**Graceful Fallback Strategy**

- If `suppliers` is missing or empty, uses a predefined mock list (`MOCK_SUPPLIERS`) and logs a warning
- If LLM invocation fails or returns invalid JSON, applies a conservative 10% fallback discount and generates a system message transcript
- All errors are appended to `state["errors"]`; the node never raises unhandled exceptions

**LLM Convention Compliance**

- Imports and initializes `get_llm()` per project standard, though the negotiation logic is prompt-based and does not require iterative agent calls
- Provider-agnostic: works with local Ollama (Mistral) or external APIs via `.env` configuration

**Output Validation**

- Parses LLM response with `json.loads()` and validates required keys (`transcript`, `final_prices`, `selected_supplier`, `discount_pct`)
- Converts `discount_pct` to a decimal factor (`0.10` for 10%) for direct use in Module 6 TCO calculations

#### Usage Example

```python
state = {
    "extracted_specs": {
        "part_name": "Valve_DN100",
        "material": "SS316L",
        "quantity": 200
    },
    "suppliers": [
        {"name": "SupplierAlpha_DZ", "country": "Algeria", "base_price": 450.0},
        {"name": "SupplierBeta_FR", "country": "France", "base_price": 520.0}
    ],
    "errors": []
}
result = simulate_negotiation(state)
# result["negotiated_discount"] → 0.10 (10% discount applied)
# result["selected_supplier"] → "SupplierAlpha_DZ"
# result["negotiation_transcript"] → [{"role": "buyer", "message": "..."}, ...]
```

---

### Module 6: Total Cost of Ownership (TCO) Calculator

**File:** `app/nodes/m6/node.py`
**Function:** `calculate_tco(state: PipelineState) -> dict`

#### Purpose

Calculate a 10-year Total Cost of Ownership projection for manufactured components, integrating material/manufacturing costs, negotiated supplier discounts, and inflation-adjusted maintenance expenses. Outputs structured JSON and Excel files for downstream business planning and client reporting.

#### Inputs (Read from PipelineState)

| Key                  | Type         | Description                                                                                           | Fallback                 |
| -------------------- | ------------ | ----------------------------------------------------------------------------------------------------- | ------------------------ |
| `extracted_specs`    | `dict`       | Product specifications from Module 1 (quantity, material)                                             | `{}`                     |
| `suppliers`          | `list[dict]` | Supplier cost data from Module 4 (unit_material_cost, unit_manufacturing_cost, unit_maintenance_cost) | `[]` → mock costs        |
| `negotiation_result` | `dict`       | Negotiation outcome from Module 5 (discount factor)                                                   | `{}` → 10% mock discount |
| `errors`             | `list[str]`  | Accumulated warnings from upstream                                                                    | `[]`                     |

#### Outputs (Returned to LangGraph)

| Key              | Type        | Description                                                                       |
| ---------------- | ----------- | --------------------------------------------------------------------------------- |
| `tco_data`       | `dict`      | Full TCO calculation: production cost, total TCO, per-unit cost, yearly breakdown |
| `tco_excel_path` | `str`       | Absolute path to generated Excel file (`outputs/tco_result.xlsx`)                 |
| `tco_json_path`  | `str`       | Absolute path to generated JSON file (`outputs/tco_result.json`)                  |
| `errors`         | `list[str]` | Updated error list with module-specific messages                                  |

#### Implementation Details

**Input Resolution with Fallbacks**

- Reads quantity from `extracted_specs["quantity"]`; defaults to 200 units if missing
- Reads unit costs from first supplier entry; falls back to predefined mock values if supplier data absent or malformed
- Reads discount from `negotiation_result["discount"]`; defaults to 0.10 (10%) if negotiation output unavailable

**World Bank API Integration**

- Fetches Algeria inflation rates via public endpoint: `https://api.worldbank.org/v2/country/DZ/indicator/FP.CPI.TOTL.ZG?format=json`
- Implements 10-second timeout and exception handling; falls back to predefined mock inflation curve on failure
- Pads or truncates response to exactly 10 years for consistent projection horizon

**TCO Calculation Engine**

- Production cost = `(unit_material + unit_manufacturing) × quantity × (1 - discount)`
- Maintenance costs compound annually using cumulative inflation factor: `maintenance_year_n = base_maintenance × ∏(1 + inflation_i/100)`
- Returns granular yearly breakdown with inflation rate, cumulative factor, and inflated maintenance cost per year

**Multi-Format Export**

- **Excel**: Two worksheets — "TCO Summary" (key metrics) and "Yearly Breakdown" (10-year projection). Includes unit cost rows for Module 7 compatibility.
- **JSON**: Pretty-printed, UTF-8 encoded dump of full `tco_data` dictionary for machine consumption.
- Both files saved to `outputs/` directory (Docker-mounted to host).

**Graceful Degradation**

- Missing upstream data triggers mock values with logged warnings
- API failures activate fallback inflation curve without pipeline interruption
- All exceptions caught at node level; errors appended to `state["errors"]`, never raised

#### Usage Example

```python
state = {
    "extracted_specs": {"quantity": 200, "material": "SS316L"},
    "suppliers": [{
        "unit_material_cost": 420.0,
        "unit_manufacturing_cost": 180.0,
        "unit_maintenance_cost": 45.0
    }],
    "negotiation_result": {"discount": 0.12},  # 12% negotiated discount
    "errors": []
}
result = calculate_tco(state)
# result["tco_data"]["total_tco_usd"] → 138420.50 (example)
# result["tco_excel_path"] → "outputs/tco_result.xlsx"
```

---

### Module 7: Business Plan Generator

**File:** `app/nodes/m7/node.py`
**Function:** `generate_business_plan(state: Dict[str, Any]) -> dict`

#### Purpose

Generate a comprehensive business plan for manufactured components, including SWOT analysis, 3-year financial projections, Return on Investment (ROI), and Net Present Value (NPV). Outputs structured JSON, Excel, and PDF files for stakeholder review and client delivery.

#### Inputs (Read from PipelineState)

| Key               | Type         | Description                                                   | Fallback        |
| ----------------- | ------------ | ------------------------------------------------------------- | --------------- |
| `tco_data`        | `dict`       | Cost analysis from Module 6 (quantity, unit costs, total TCO) | Mock TCO values |
| `extracted_specs` | `dict`       | Product specifications from Module 1 (name, material)         | `{}`            |
| `suppliers`       | `list[dict]` | Supplier list from Module 4                                   | `[]`            |
| `errors`          | `list[str]`  | Accumulated warnings from upstream                            | `[]`            |

#### Outputs (Returned to LangGraph)

| Key                     | Type             | Description                                                                  |
| ----------------------- | ---------------- | ---------------------------------------------------------------------------- |
| `business_plan_paths`   | `dict[str, str]` | Paths to generated files: `json`, `excel`, `pdf`                             |
| `business_plan_summary` | `dict`           | Key financial metrics: NPV, 3-year ROI, Year 3 revenue                       |
| `plan`                  | `dict`           | Full business plan structure: projections, SWOT, financials                  |
| `errors`                | `list[str]`      | Updated error list (add `state.get("errors", [])` for convention compliance) |

#### Implementation Details

**TCO Data Integration**

- Reads `tco_data` from Module 6; falls back to mock values if missing
- Extracts quantity, unit material/manufacturing costs, and total TCO for financial modeling
- Gracefully handles missing keys via `.get()` with sensible defaults

**Financial Projection Engine**

- Calculates unit cost with 5% efficiency gain: `base_cost × 0.95`
- Sets unit price at 2.5× cost (standard industrial markup)
- Projects 3-year revenue/cost growth: revenue +20% YoY, costs +15% YoY
- Applies 81% net margin factor to simulate operational efficiency

**Investment Metrics**

- **NPV (Net Present Value)**: Discounts 3-year net income at 10% rate, subtracts initial production investment
- **ROI (Return on Investment)**: `(total_net_income - investment) / investment × 100`
- Both metrics rounded to 2 decimals for client-ready reporting

**SWOT Analysis**

- Predefined, context-aware strengths/weaknesses/opportunities/threats based on industrial manufacturing domain
- Structured for easy Excel/PDF rendering and stakeholder comprehension

**Multi-Format Export**

- **JSON**: Pretty-printed, UTF-8 encoded full plan for machine consumption
- **Excel**: Three worksheets — "Business Plan" (key metrics), "Projections" (3-year table), "SWOT" (categorized lists)
- **PDF**: Styled ReportLab document with title, metrics, SWOT summary, and projection highlights
- All files saved to `outputs/` directory (Docker-mounted to host)

**Graceful Degradation**

- Missing `tco_data` triggers mock financial baseline; plan still generates with logged assumptions
- All file operations wrapped in try-except; errors would append to state (add `"errors"` key to return for full compliance)

#### Usage Example

```python
state = {
    "tco_data": {
        "quantity": 200,
        "unit_material_usd": 420.0,
        "unit_manufacturing_usd": 180.0,
        "production_cost_usd": 117000.0,
        "total_tco_usd": 255000.0
    },
    "extracted_specs": {"product_name": "Valve_DN100"},
    "suppliers": [{"name": "SupplierA"}],
    "errors": []
}
result = generate_business_plan(state)
# result["business_plan_summary"]["npv"] → 45230.50 (example)
# result["business_plan_summary"]["roi_3yr"] → 38.65 (%)
# result["business_plan_paths"]["pdf"] → "outputs/business_plan.pdf"
```

---

### Module 8: Digital Twin & Predictive Maintenance

**File:** `app/nodes/m8/node.py`
**Function:** `build_catalog(state: PipelineState) -> dict`

#### Purpose

Simulate a digital twin for industrial components and generate predictive maintenance alerts based on operational sensor data. Uses the AI4I 2020 Predictive Maintenance dataset to model degradation curves, detect anomalies, and estimate remaining useful life (RUL).

#### Inputs (Read from PipelineState)

| Key                      | Type         | Description                                                        | Fallback |
| ------------------------ | ------------ | ------------------------------------------------------------------ | -------- |
| `extracted_specs`        | `dict`       | Product specifications (name, material, pressure rating, quantity) | `{}`     |
| `tco_data`               | `dict`       | Cost analysis from Module 6                                        | `{}`     |
| `suppliers`              | `list[dict]` | Supplier list from Module 4                                        | `[]`     |
| `plan` / `business_plan` | `dict`       | Financial projections from Module 7                                | `{}`     |
| `errors`                 | `list[str]`  | Accumulated warnings from upstream                                 | `[]`     |

#### Outputs (Returned to LangGraph)

| Key            | Type        | Description                                                                                           |
| -------------- | ----------- | ----------------------------------------------------------------------------------------------------- |
| `catalog_data` | `dict`      | Comprehensive digital twin state (sensor dataset, alerts, health status, maintenance recommendations) |
| `cad_paths`    | `list[str]` | Paths to generated CAD placeholder files (STEP, STL, DXF)                                             |
| `errors`       | `list[str]` | Updated error list with module-specific messages                                                      |

#### Implementation Details

**Dataset Integration & Simulation**

- Attempts to load the real AI4I 2020 Kaggle dataset from `data/sensors/ai4i2020.csv` using `pandas`
- If unavailable, falls back to a physics-based simulation that replicates the dataset's degradation curves (tool wear, temperature drift, torque/RPM correlation)
- Samples evenly across the dataset to capture full lifecycle progression

**Dynamic Threshold Adjustment**

- Alarm thresholds are adjusted based on M1-extracted specifications
- Product-type detection (valve vs. pump) modifies temperature tolerance limits
- Pressure rating (e.g., PN16, PN40) scales pressure alarm thresholds proportionally

**Anomaly Detection & Health Assessment**

- Evaluates sensor readings against ground-truth failure flags (TWF, HDF, PWF, OSF, RNF) and dynamic thresholds
- Classifies alerts by severity (HIGH/MEDIUM) based on tool wear, temperature deviation, and torque anomalies
- Computes system health status: `STABLE`, `UNSTABLE`, or `CRITICAL`
- Calculates risk score and estimates Remaining Useful Life (RUL) based on alert density and degradation rate

**Graceful Degradation**

- Missing upstream data triggers generic thresholds and standard product naming
- Dataset absence activates the simulation fallback without pipeline interruption
- All errors are appended to `state["errors"]`; core execution never raises unhandled exceptions

#### Usage Example

```python
state = {
    "extracted_specs": {"product_name": "Valve_DN100", "pressure": "PN40", "quantity": 200},
    "tco_data": {"total_tco_usd": 142350.0},
    "suppliers": [{"name": "SupplierA", "country": "DZ"}],
    "errors": []
}
result = build_catalog(state)
# result["catalog_data"]["digital_twin"]["health_status"] → "STABLE" or "CRITICAL"
# result["catalog_data"]["maintenance"]["action"] → "Next scheduled inspection in 30 days"
```

---

### Module 9: Catalog Export

**File:** `app/nodes/m9/node.py`
**Function:** `export_catalog(state: PipelineState) -> dict`

#### Purpose

Aggregate outputs from all upstream modules and compile them into client-ready deliverables in multiple formats.

#### Inputs (Read from PipelineState)

| Key               | Type         | Description                                | Fallback |
| ----------------- | ------------ | ------------------------------------------ | -------- |
| `extracted_specs` | `dict`       | Technical specifications from Module 1     | `{}`     |
| `cad_paths`       | `list[str]`  | Paths to generated CAD files from Module 2 | `[]`     |
| `suppliers`       | `list[dict]` | Supplier data from Module 4                | `[]`     |
| `tco_data`        | `dict`       | Cost analysis from Module 6                | `{}`     |
| `errors`          | `list[str]`  | Accumulated warnings from upstream         | `[]`     |

#### Outputs (Returned to LangGraph)

| Key             | Type        | Description                                      |
| --------------- | ----------- | ------------------------------------------------ |
| `catalog_paths` | `list[str]` | Absolute paths to generated catalog files        |
| `errors`        | `list[str]` | Updated error list with export-specific messages |

#### Implementation Details

**Data Aggregation**
All relevant state keys are collected into a single `catalog_data` dictionary, with timestamps and metadata appended for auditability.

**Format Generation**

_JSON Export_

- Serializes `catalog_data` with UTF-8 encoding and pretty-printing
- Uses `default=str` to handle non-serializable types (e.g., datetime)
- Saved to `/app/outputs/catalog.json`

_Excel Export (openpyxl)_

- Creates a workbook with three worksheets:
  - `Technical Specs`: key-value pairs from `extracted_specs`
  - `Suppliers`: tabular view of supplier entries (name, country, contact)
  - `TCO Summary`: aggregated financial metrics from `tco_data`
- Saved to `/app/outputs/catalog.xlsx`

_HTML Export (Jinja2)_

- Renders a styled HTML document using an embedded template
- Includes technical specifications, TCO summary, and supplier list
- Saved to `/app/outputs/catalog.html`

_PDF Export (optional, weasyprint)_

- Converts the generated HTML to PDF if the `weasyprint` library is available
- Failure to import or render is logged but does not prevent other formats from generating
- Saved to `/app/outputs/catalog.pdf`

**Graceful Degradation**

- Missing upstream data results in placeholder content (e.g., "No specifications available")
- Optional dependencies (e.g., `weasyprint`) are imported inside try blocks; absence is logged but non-fatal
- All file operations use absolute paths under `/app/outputs/` for Docker consistency

#### Usage Example

```python
state = {
    "extracted_specs": {"part_name": "Valve_DN100", "material": "SS316L"},
    "cad_paths": ["/app/outputs/Valve_DN100_2D.dxf"],
    "tco_data": {"total_tco_usd": 142350.00, "quantity": 200},
    "errors": []
}
result = export_catalog(state)
# result["catalog_paths"] → [
#   "/app/outputs/catalog.json",
#   "/app/outputs/catalog.xlsx",
#   "/app/outputs/catalog.html",
#   "/app/outputs/catalog.pdf"  # if weasyprint available
# ]
```

---

## Adding Module Documentation

To document additional modules, follow this structure:

### Module X: [Module Name]

**File:** `app/nodes/mX/node.py`
**Function:** `[function_name](state: PipelineState) -> dict`

#### Purpose

[Concise description of the module's responsibility within the pipeline.]

#### Inputs (Read from PipelineState)

| Key        | Type   | Description                                      | Fallback                   |
| ---------- | ------ | ------------------------------------------------ | -------------------------- |
| `key_name` | `type` | [What this key contains and where it originates] | [Default value if missing] |

#### Outputs (Returned to LangGraph)

| Key          | Type   | Description                                                      |
| ------------ | ------ | ---------------------------------------------------------------- |
| `output_key` | `type` | [What this key contains and which downstream modules consume it] |

#### Implementation Details

[Technical notes on algorithms, libraries, validation logic, error handling, or design decisions.]

#### Usage Example

```python
# Minimal working example showing input state and expected output
state = {...}
result = module_function(state)
# result["key"] → expected value
```

---

## Development Standards

### Module Interface Contract

All modules must adhere to the following signature and behavior:

```python
from app.state import PipelineState

def module_function(state: PipelineState) -> dict:
    """
    LangGraph node entry point.

    Args:
        state: Shared PipelineState dictionary containing upstream outputs.

    Returns:
        dict: State delta containing new keys/values to be merged by LangGraph.
              Must include "errors" key if appending to error list.
    """
    # Read inputs with fallbacks
    data = state.get("upstream_key", fallback_value)

    # Perform computation

    # Return minimal delta
    return {"new_key": result, "errors": state.get("errors", [])}
```

**Requirements:**

- Import `get_llm` from `app.llm` if AI functionality is required (initialize but do not call unless needed)
- Use absolute paths under `/app/outputs/` for all file writes
- Append errors to `state["errors"]` rather than raising exceptions
- Return only new or modified keys; do not return the full state

### Testing Approach

- Unit tests verify module logic in isolation using mocked dependencies
- Integration tests validate state flow between modules via LangGraph
- Fallback tests confirm graceful handling of missing or malformed input
- Target coverage: 60%+ on critical modules (M1, M4, M6, M7)

Run tests with:

```bash
docker compose exec app pytest tests/test_m2.py tests/test_m9.py -v
```

---

## Project Structure

```
industrie-ia/
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI application: routes, middleware
│   ├── graph.py                  # LangGraph compilation and node wiring
│   ├── state.py                  # PipelineState TypedDict definition
│   ├── llm.py                    # Provider-agnostic LLM router
│   ├── static/                   # Static assets for web interface
│   │   └── index.html            # Minimal demo interface
│   └── nodes/                    # Module implementations
│       ├── __init__.py
│       ├── m2/node.py            # CAD generation [implemented]
│       ├── m6/node.py            # TCO calculation [implemented]
│       ├── m9/node.py            # Catalog export [implemented]
│       └── ...                   # Additional modules as implemented
├── tests/
│   ├── test_m2.py                # Module 2 unit tests
│   ├── test_m6.py                # Module 6 unit tests
│   ├── test_m9.py                # Module 9 unit tests
│   └── ...                       # Additional tests as modules are added
├── outputs/                      # Generated artifacts (gitignored)
├── .env.example                  # Configuration template
├── Dockerfile                    # Application container definition
├── docker-compose.yml            # Multi-service orchestration
└── README.md                     # This document
```

---

## Setup and Execution

### Prerequisites

- Docker Engine with Compose plugin
- Git
- ~5 GB available disk space

### Initial Configuration

```bash
git clone https://github.com/kameldemri/industrie-ia
cd industrie-ia
cp .env.example .env
```

### Start Services

```bash
docker compose up -d --build
```

### Verify Deployment

```bash
curl http://localhost:8000/health
# Expected response: {"status":"ok","service":"industrie-ia"}
```

### Access Demo Interface

```
http://localhost:8000
```

---

## Configuration

LLM provider selection is managed via environment variables in `.env`. No code changes are required to switch providers.

**Local Ollama (default):**

```env
LLM_BASE_URL=http://ollama:11434/v1
LLM_API_KEY=unused
LLM_MODEL_NAME=mistral
```

**External API (OpenRouter example):**

```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-YOUR_KEY
LLM_MODEL_NAME=qwen/qwen-2.5-7b-instruct:free
```

Apply changes with:

```bash
docker compose restart app
```

---

## Troubleshooting

| Issue                                 | Resolution                                                                                                                                |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Connection refused on port 8000       | Wait 10 seconds after `up -d`; check `docker compose logs app`                                                                            |
| Module import errors                  | Rebuild container: `docker compose build app && docker compose up -d`                                                                     |
| Output files not visible on host      | Verify `./outputs/` directory exists and has write permissions                                                                            |
| LLM timeout or authentication failure | Validate `.env` credentials; test with `docker compose exec app python -c "from app.llm import get_llm; print(get_llm().invoke('test'))"` |
| Tests fail after code changes         | Clear pytest cache: `docker compose exec app pytest --cache-clear tests/`                                                                 |

---

## Roadmap

| Phase                 | Objective                                                   | Status      |
| --------------------- | ----------------------------------------------------------- | ----------- |
| Infrastructure        | Docker orchestration, LangGraph skeleton, FastAPI setup     | Complete    |
| Core Modules          | M2 (CAD), M6 (TCO), M9 (Catalog) implementation and testing | Complete    |
| Extraction Module     | M1: PDF parsing with pdfplumber and regex fallback          | In progress |
| Data Integration      | M4: Supplier sourcing via Wikidata/UN Comtrade APIs         | Pending     |
| Business Logic        | M7: Business plan generation with financial projections     | Pending     |
| Polish and Validation | End-to-end testing, documentation finalization              | Pending     |

---

## References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- ezdxf Documentation: https://ezdxf.readthedocs.io/
- ifcopenshell Documentation: https://ifcopenshell.org/
- World Bank API: https://data.worldbank.org/api
- Wikidata Query Service: https://query.wikidata.org/

---

_This document is maintained as part of the INDUSTRIE IA project. For issues or contributions, please refer to the project repository._