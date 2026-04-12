# INDUSTRIE IA — Multi-Agent Manufacturing Pipeline

> 🚧 **Status:** Phase 1 — Infrastructure, Orchestration & Module Scaffolding
> 📅 **Timeline:** Bootcamp 2026 | Day 13+
> 📄 *Living document. Updated as modules M1→M9 are implemented and integrated.*

---

## 🎯 Mission
**INDUSTRIE IA** automates the transformation of public technical PDFs (e.g., industrial valve blueprints from GrabCAD) into complete, audit-ready manufacturing dossiers. The pipeline extracts specifications, generates CAD assets, sources suppliers, calculates Total Cost of Ownership (TCO), produces business plans, and exports multi-format catalogs—**exclusively using open-source tools and public APIs**.

Built for Algerian SMEs, it eliminates licensing fees, vendor lock-in, and manual engineering bottlenecks.

---

## 🏗️ Architecture Overview

### 📦 Container Topology
| Container | Role | Network Exposure | Persistence |
|-----------|------|------------------|-------------|
| `app` | FastAPI backend + LangGraph state machine + Python logic | `localhost:8000` | Host mount (`.`), outputs via `./outputs/` |
| `ollama` | Local LLM inference (Mistral/Qwen/Llama) | `localhost:11434` | Named Docker volume (`ollama_models`) |

**Internal Routing:** Docker Compose provisions an isolated bridge network. Containers resolve each other by service name (`http://ollama:11434`), eliminating manual IP configuration.

### 🔄 Workflow Design
```
PDF Upload → FastAPI → LangGraph StateMachine → PipelineState (TypedDict)
   ↓
M1 → M4 → M6 → M7 → M9 (Critical Path)
   ↓
Outputs saved to ./outputs/ → Multi-format catalog export
```
- **LangGraph** enforces execution order, manages shared state, handles failures, and supports checkpointing.
- **`PipelineState`** is a strictly typed schema guaranteeing data consistency across all modules.
- **`app/llm.py`** abstracts LLM communication. Switching providers requires only `.env` changes.

---

## 📁 Directory Structure

```
industrie-ia/
├── app/
│   ├── __init__.py               # Python package marker
│   ├── main.py                   # FastAPI entrypoint: /health, /trigger, CORS
│   ├── graph.py                  # LangGraph compilation & state machine wiring
│   ├── state.py                  # PipelineState TypedDict: shared data contract
│   ├── llm.py                    # Provider-agnostic LLM router (Ollama ↔ External APIs)
│   └── nodes/                    # Module implementations (M1–M9)
│       ├── __init__.py
│       ├── m1/node.py            # extract_specs(state) → dict
│       ├── m2/node.py            # generate_cad(state) → dict
│       ├── m3/node.py            # generate_video(state) → dict
│       ├── m4/node.py            # source_suppliers(state) → dict
│       ├── m5/node.py            # simulate_negotiation(state) → dict
│       ├── m6/node.py            # calculate_tco(state) → dict
│       ├── m7/node.py            # generate_business_plan(state) → dict
│       ├── m8/node.py            # simulate_digital_twin(state) → dict
│       └── m9/node.py            # export_catalog(state) → dict
├── tests/                        # Pytest suite (60% coverage target: M1, M4, M6, M7)
│   ├── test_m1.py ... test_m9.py
├── outputs/                      # Generated artifacts (CAD, PDFs, Excel, logs)
├── data/                         # Persistent state (SQLite when enabled)
├── .env                          # Runtime config (NEVER commit)
├── .env.example                  # Template for onboarding (SAFE to commit)
├── .gitignore                    # Excludes secrets, caches, build artifacts
├── Dockerfile                    # App container: Python 3.11 + system deps
├── docker-compose.yml            # Multi-service orchestration
└── README.md                     # This document
```

---

## 🌍 Cross-Platform Setup

### ✅ Prerequisites
| Component | Linux | Windows | macOS |
|-----------|-------|---------|-------|
| **Container Runtime** | Docker Engine + Compose plugin | Docker Desktop + WSL2 | Docker Desktop |
| **Version Control** | Git | Git for Windows (Bash/PowerShell) | `brew install git` |
| **Disk Space** | ~5 GB | ~5 GB | ~5 GB |
| **GPU (Optional)** | NVIDIA + Container Toolkit | Docker Desktop + NVIDIA drivers | CPU-only fallback |

> 💡 No host Python, `pip`, or system libraries required. Everything runs inside containers.

### 🚀 First Run
```bash
# 1. Clone
git clone https://github.com/kameldemri/industrie-ia && cd industrie-ia

# 2. Configure
cp .env.example .env

# 3. Pull & build
docker compose pull
docker compose up -d --build

# 4. Verify
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"industrie-ia","db":"memory"}
```

---

## 🌐 LLM Configuration (Provider-Agnostic)

Edit `.env` to switch providers. Zero code changes required.

### 🔹 Local Ollama (Default)
```env
LLM_BASE_URL=http://ollama:11434/v1
LLM_API_KEY=unused
LLM_MODEL_NAME=mistral
```

### 🔸 Free External API (Qwen via OpenRouter)
```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-YOUR_KEY_HERE
LLM_MODEL_NAME=qwen/qwen-2.5-7b-instruct:free
```
Apply: `docker compose restart app`

### 🔥 NVIDIA GPU (Linux/Windows)
1. Uncomment `deploy.resources...` block under `ollama` in `docker-compose.yml`
2. Install NVIDIA Container Toolkit (Linux) or enable WSL2 GPU support (Windows)
3. `docker compose up -d`
4. Fallback: If GPU unavailable, Ollama auto-switches to CPU. No crash.

---

## 📝 Development Standards

### 🔹 Commit Convention (Conventional Commits)
```
<type>(<scope>): <description>
```
| Type | Scope | Example |
|------|-------|---------|
| `feat` | `m1`, `llm`, `docker` | `feat(m1): integrate pdfplumber extraction with Pydantic validation` |
| `fix` | `graph`, `api` | `fix(llm): resolve OpenRouter timeout on retry` |
| `docs` | `readme`, `setup` | `docs(readme): add cross-platform troubleshooting matrix` |
| `test` | `m1`, `m6` | `test(m4): add pytest coverage for supplier deduplication` |
| `refactor` | `state`, `nodes` | `refactor(llm): centralize provider config in single router` |
| `chore` | `deps`, `ci` | `chore(deps): pin langgraph==0.2.22 for stability` |

### 🔹 Module Development Contract
```python
# In app/nodes/mX/node.py
from app.llm import get_llm
from app.state import PipelineState

def module_function_name(state: PipelineState) -> dict:
    """LangGraph entry point. Return ONLY state deltas."""
    llm = get_llm()  # Always use this for AI calls
    # ... your logic ...
    return {"output_key": result}  # LangGraph merges automatically
```

**Rules:**
- ✅ Work only in `app/nodes/mX/` + `tests/test_mX.py`
- ✅ Return state deltas only
- ✅ Always use `get_llm()` for AI calls
- ❌ Never modify `state.py`, `graph.py`, `main.py`, or `llm.py` without coordination
- ❌ Never commit `.env`, `outputs/`, `data/`, or `__pycache__/`

---

## 📌 Project Roadmap

| Phase | Target | Status |
|-------|--------|--------|
| ✅ Infrastructure | Docker, LangGraph skeleton, FastAPI, LLM router | Complete |
| ✅ Module Scaffolding | M1–M9 entry points + test stubs | Complete |
| 🚧 Module 1 | PDF extraction with `pdfplumber` + regex fallback | In Progress |
| 🔜 Modules 4,6,7 | Supplier sourcing, TCO, Business Plan | Pending |
| 🔜 Module 9 | Multi-format catalog export | Pending |
| 🔜 Bonus Modules | M2 (CAD), M3 (Video), M5 (Negotiation), M8 (Digital Twin) | If time permits |

---

## 🛠️ Troubleshooting

| Symptom | Quick Fix |
|---------|-----------|
| `curl: (7) Failed to connect` | Wait 5s after `up -d`. Run `docker compose logs app --tail 10` |
| `ImportError` / `ModuleNotFoundError` | Rebuild: `docker compose build app && docker compose up -d` |
| Port `8000` already in use | Change mapping in `docker-compose.yml`: `"8001:8000"` |
| `Permission denied` on Docker socket | `sudo usermod -aG docker $USER && newgrp docker` (Linux) |
| LLM timeout / 401 | Verify `.env` credentials. Test: `docker compose exec app python -c "from app.llm import get_llm; print(get_llm().invoke('ping'))"` |

---

**🔒 License:** Open-source. Built exclusively with public APIs, open models, and zero proprietary dependencies.
**📞 Support:** Report issues via GitHub Issues. Include `docker compose logs app --tail 20` and OS environment details.
