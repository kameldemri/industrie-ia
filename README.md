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
  - [Module 2: CAD Generation](#module-2-cad-generation)
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

| Component | Technology | Responsibility |
|-----------|-----------|---------------|
| `app` container | Python 3.11, FastAPI, LangGraph | Pipeline orchestration, module execution, API endpoints |
| `ollama` container | Ollama runtime | Local LLM inference (Mistral, Qwen, Llama) |
| Host volume | Docker bind mount | Persistent output storage (`./outputs/` ↔ `/app/outputs/`) |

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

### Module 2: CAD Generation

**File:** `app/nodes/m2/node.py`
**Function:** `generate_cad(state: PipelineState) -> dict`

#### Purpose
Generate 2D DXF and 3D IFC engineering drawings from extracted technical specifications.

#### Inputs (Read from PipelineState)
| Key | Type | Description | Fallback |
|-----|------|-------------|----------|
| `extracted_specs` | `dict` | Technical specifications from Module 1 | `{}` (use defaults) |
| `errors` | `list[str]` | Accumulated error messages from upstream | `[]` |

#### Outputs (Returned to LangGraph)
| Key | Type | Description |
|-----|------|-------------|
| `cad_paths` | `list[str]` | Absolute paths to generated `.dxf` and `.ifc` files |
| `errors` | `list[str]` | Updated error list with module-specific messages |

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

### Module 8: Digital Twin & Predictive Maintenance

**File:** `app/nodes/m8/node.py`
**Function:** `build_catalog(state: PipelineState) -> dict`

#### Purpose
Simulate a digital twin for industrial components and generate predictive maintenance alerts based on operational sensor data. Uses the AI4I 2020 Predictive Maintenance dataset to model degradation curves, detect anomalies, and estimate remaining useful life (RUL).

#### Inputs (Read from PipelineState)
| Key | Type | Description | Fallback |
|-----|------|-------------|----------|
| `extracted_specs` | `dict` | Product specifications (name, material, pressure rating, quantity) | `{}` |
| `tco_data` | `dict` | Cost analysis from Module 6 | `{}` |
| `suppliers` | `list[dict]` | Supplier list from Module 4 | `[]` |
| `plan` / `business_plan` | `dict` | Financial projections from Module 7 | `{}` |
| `errors` | `list[str]` | Accumulated warnings from upstream | `[]` |

#### Outputs (Returned to LangGraph)
| Key | Type | Description |
|-----|------|-------------|
| `catalog_data` | `dict` | Comprehensive digital twin state (sensor dataset, alerts, health status, maintenance recommendations) |
| `cad_paths` | `list[str]` | Paths to generated CAD placeholder files (STEP, STL, DXF) |
| `errors` | `list[str]` | Updated error list with module-specific messages |

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
| Key | Type | Description | Fallback |
|-----|------|-------------|----------|
| `extracted_specs` | `dict` | Technical specifications from Module 1 | `{}` |
| `cad_paths` | `list[str]` | Paths to generated CAD files from Module 2 | `[]` |
| `suppliers` | `list[dict]` | Supplier data from Module 4 | `[]` |
| `tco_data` | `dict` | Cost analysis from Module 6 | `{}` |
| `errors` | `list[str]` | Accumulated warnings from upstream | `[]` |

#### Outputs (Returned to LangGraph)
| Key | Type | Description |
|-----|------|-------------|
| `catalog_paths` | `list[str]` | Absolute paths to generated catalog files |
| `errors` | `list[str]` | Updated error list with export-specific messages |

#### Implementation Details

**Data Aggregation**
All relevant state keys are collected into a single `catalog_data` dictionary, with timestamps and metadata appended for auditability.

**Format Generation**

*JSON Export*
- Serializes `catalog_data` with UTF-8 encoding and pretty-printing
- Uses `default=str` to handle non-serializable types (e.g., datetime)
- Saved to `/app/outputs/catalog.json`

*Excel Export (openpyxl)*
- Creates a workbook with three worksheets:
  - `Technical Specs`: key-value pairs from `extracted_specs`
  - `Suppliers`: tabular view of supplier entries (name, country, contact)
  - `TCO Summary`: aggregated financial metrics from `tco_data`
- Saved to `/app/outputs/catalog.xlsx`

*HTML Export (Jinja2)*
- Renders a styled HTML document using an embedded template
- Includes technical specifications, TCO summary, and supplier list
- Saved to `/app/outputs/catalog.html`

*PDF Export (optional, weasyprint)*
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
| Key | Type | Description | Fallback |
|-----|------|-------------|----------|
| `key_name` | `type` | [What this key contains and where it originates] | [Default value if missing] |

#### Outputs (Returned to LangGraph)
| Key | Type | Description |
|-----|------|-------------|
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

| Issue | Resolution |
|-------|-----------|
| Connection refused on port 8000 | Wait 10 seconds after `up -d`; check `docker compose logs app` |
| Module import errors | Rebuild container: `docker compose build app && docker compose up -d` |
| Output files not visible on host | Verify `./outputs/` directory exists and has write permissions |
| LLM timeout or authentication failure | Validate `.env` credentials; test with `docker compose exec app python -c "from app.llm import get_llm; print(get_llm().invoke('test'))"` |
| Tests fail after code changes | Clear pytest cache: `docker compose exec app pytest --cache-clear tests/` |

---

## Roadmap

| Phase | Objective | Status |
|-------|-----------|--------|
| Infrastructure | Docker orchestration, LangGraph skeleton, FastAPI setup | Complete |
| Core Modules | M2 (CAD), M6 (TCO), M9 (Catalog) implementation and testing | Complete |
| Extraction Module | M1: PDF parsing with pdfplumber and regex fallback | In progress |
| Data Integration | M4: Supplier sourcing via Wikidata/UN Comtrade APIs | Pending |
| Business Logic | M7: Business plan generation with financial projections | Pending |
| Polish and Validation | End-to-end testing, documentation finalization | Pending |

---

## References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- ezdxf Documentation: https://ezdxf.readthedocs.io/
- ifcopenshell Documentation: https://ifcopenshell.org/
- World Bank API: https://data.worldbank.org/api
- Wikidata Query Service: https://query.wikidata.org/

---

*This document is maintained as part of the INDUSTRIE IA project. For issues or contributions, please refer to the project repository.*
