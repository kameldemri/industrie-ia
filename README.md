# INDUSTRIE IA — Multi-Agent Manufacturing Pipeline

> 🚧 **Status:** Phase 1 — Infrastructure, Orchestration & LLM Routing
> 🔜 **Next:** Module 1 (PDF Specification Extraction)
> 📄 *This README is a living technical document. It will be updated as each pipeline module is implemented.*

---

## 🎯 Project Mission
**INDUSTRIE IA** automates the transformation of public technical PDFs (e.g., industrial valve blueprints) into complete, audit-ready manufacturing dossiers. Built exclusively with open-source tools and public APIs, the pipeline extracts specifications, generates CAD assets, sources suppliers, calculates Total Cost of Ownership (TCO), produces business plans, and exports multi-format catalogs.

This phase establishes the **production-ready foundation**: Dockerized cross-platform deployment, LangGraph state orchestration, FastAPI gateway, and a provider-agnostic LLM routing layer.

---

## 🏗️ Architecture Overview

### 📦 Container Topology
| Container | Role | Network Exposure | Persistence Model |
|-----------|------|------------------|-------------------|
| `app` | FastAPI backend + LangGraph orchestration + Python logic | `localhost:8000` | Code via host mount, outputs via `./outputs/` |
| `ollama` | Local LLM inference engine (Mistral/Qwen/Llama) | `localhost:11434` | Models via Docker named volume |

**Internal Networking:** Docker Compose provisions an isolated bridge network (`industrie-ia_default`). Containers resolve each other by service hostname (`http://ollama:11434`), eliminating manual IP configuration or `localhost` routing.

### 🔄 State & Workflow Design
```
PDF Upload → FastAPI → LangGraph StateMachine → PipelineState (TypedDict)
   ↓
M1 (Pending) → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9
   ↓
Outputs saved to ./outputs/ → Multi-format catalog export
```
- **LangGraph** enforces deterministic execution order, manages shared state, handles node failures, and supports checkpointing for crash recovery.
- **`PipelineState`** is a strictly typed schema that guarantees data consistency across all modules. Every node reads from and writes to this shared state object.
- **`app/llm.py`** abstracts LLM communication. Switching between local Ollama and external APIs requires zero code changes—only `.env` variables.

---

## 📁 Directory Structure & Component Roles

```
industrie-ia/
├── app/
│   ├── __init__.py               # Marks 'app' as a valid Python import package
│   ├── main.py                   # FastAPI entrypoint: health checks, CORS, pipeline trigger routing
│   ├── graph.py                  # LangGraph compilation, state machine initialization, checkpointer wiring
│   ├── state.py                  # PipelineState TypedDict: strict schema for cross-module data flow
│   ├── llm.py                    # Provider-agnostic LLM router (Ollama ↔ OpenRouter/Groq/Any OpenAI-compatible API)
│   └── nodes/                    # Module implementations (M1 extraction logic pending)
│       └── __init__.py
├── tests/                        # Pytest suite targeting M1, M4, M6, M7 (60% coverage requirement)
├── outputs/                      # Host-mapped directory for generated artifacts (CAD, PDFs, Excel, logs)
├── data/                         # Persistent storage for future SQLite/Postgres checkpoints
├── .env                          # Runtime configuration (API endpoints, model selection, environment flags)
├── .env.example                  # Template for team onboarding and CI/CD
├── .gitignore                    # Excludes secrets, caches, build artifacts, and ephemeral directories
├── Dockerfile                    # App container definition: Python 3.11-slim-bookworm + system dependencies
├── docker-compose.yml            # Multi-service orchestration, volume mapping, resource allocation
└── README.md                     # This document
```

---

## 🌍 Cross-Platform Setup & First-Run Guide

### ✅ Prerequisites
| Component | Linux | Windows | macOS |
|-----------|-------|---------|-------|
| **Container Runtime** | Docker Engine + Compose plugin (`sudo apt install docker.io docker-compose-plugin`) | Docker Desktop + WSL2 backend enabled (Settings → Resources) | Docker Desktop (Apple Silicon or Intel) |
| **Version Control** | Git (`sudo apt install git`) | Git for Windows (use Git Bash or PowerShell) | `brew install git` or Xcode CLI |
| **Disk Space** | ~5 GB (4 GB Ollama models, ~1 GB Python environment) | Same | Same |
| **GPU (Optional)** | NVIDIA driver + [Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) | Docker Desktop + WSL2 + latest NVIDIA drivers | CPU-only (Ollama auto-fallback) |

> 💡 **Note:** No host Python, `pip`, `venv`, or system libraries are required. All dependencies run inside isolated containers.

### 🚀 Step-by-Step First Run

1. **Clone Repository**
   ```bash
   git clone <your-repo-url> && cd industrie-ia
   ```

2. **Initialize Configuration**
   ```bash
   cp .env.example .env
   ```

3. **Pull Base Images**
   Isolates the ~4 GB Ollama image download before building the Python layer.
   ```bash
   docker compose pull
   ```

4. **Build & Launch Services**
   ```bash
   docker compose up -d --build
   ```

5. **Verify Deployment**
   ```bash
   # Linux / macOS / Git Bash:
   curl http://localhost:8000/health

   # Windows PowerShell:
   Invoke-WebRequest -Uri http://localhost:8000/health | Select-Object -ExpandProperty Content
   ```
   ✅ **Expected Response:** `{"status":"ok","service":"industrie-ia","db":"memory"}`

---

## 🔄 Runtime Management & Daily Workflow

| Operation | Command | Behavior |
|-----------|---------|----------|
| **Start services** | `docker compose up -d` | Reuses cached images & volumes. ~5s startup. |
| **Safe shutdown** | `docker compose down` | Stops & removes containers. Preserves models, code, outputs. |
| **Pause/Resume** | `docker compose stop` / `start` | Keeps RAM state. Ideal for short breaks. |
| **Apply `.env` changes** | `docker compose restart app` | No rebuild required. Variables load at runtime. |
| **View live logs** | `docker compose logs -f app` | Real-time FastAPI, LangGraph, and LLM routing output. |
| **Rebuild after dependency changes** | `docker compose build app && docker compose up -d` | Detects `requirements.txt` or `Dockerfile` modifications. ~15–30s. |

⚠️ **Never Execute:**
- `docker compose down -v` → Deletes named volumes (erases Ollama models & persistent state)
- `docker system prune -f` → Forces full redownload of base images and build layers

🔁 **After System Reboot / PC Shutdown:**
Navigate to project directory → `docker compose up -d` → Wait 5 seconds → Verify with `curl`. Zero redownloads. All models and code persist automatically.

---

## 🌐 LLM Configuration (Provider-Agnostic)

The pipeline routes all AI requests through `app/llm.py`. Switching providers requires only updating `.env`. No code modifications are needed.

### 🔹 Default: Local Ollama (CPU)
```env
LLM_BASE_URL=http://ollama:11434/v1
LLM_API_KEY=unused
LLM_MODEL_NAME=mistral
```

### 🔸 Recommended: Free External API (Qwen via OpenRouter)
```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-YOUR_KEY_HERE
LLM_MODEL_NAME=qwen/qwen-2.5-7b-instruct:free
```
Apply: `docker compose restart app`

### 🔥 NVIDIA GPU Acceleration (Linux / Windows)
1. Uncomment the `deploy.resources...` block under the `ollama` service in `docker-compose.yml`
2. Ensure NVIDIA drivers and Container Toolkit are installed on the host
3. `docker compose up -d`
4. If GPU is unavailable or misconfigured, Ollama gracefully falls back to CPU inference. No container crashes.

---

## 🛠️ Troubleshooting & Diagnostics

| Symptom | Root Cause | Resolution |
|---------|------------|------------|
| `curl: (7) Failed to connect` | Container still initializing or crashed | Wait 5s. Run `docker compose logs app --tail 15` to inspect stack trace. |
| `ImportError` / `ModuleNotFoundError` | Missing `__init__.py` or stale cache | Rebuild: `docker compose build app && docker compose up -d` |
| Port `8000` or `11434` already in use | Host service conflict | Change mapping in `docker-compose.yml`: `"8001:8000"` / `"11435:11434"` |
| `Permission denied` on Docker socket | User lacks `docker` group access | `sudo usermod -aG docker $USER && newgrp docker` |
| LLM timeout / `401 Unauthorized` | Invalid API key or rate limit | Verify `.env` credentials. Test: `docker compose exec app python -c "from app.llm import get_llm; print(get_llm().invoke('ping'))"` |

---

## 📝 Development & Contribution Standards

### 🔹 Commit Convention
We follow [Conventional Commits](https://www.conventionalcommits.org/) for automated changelogs, semantic versioning, and audit-ready history.

```
<type>(<scope>): <description>

[optional body]
```

| Type | Scope Examples | Usage |
|------|----------------|-------|
| `feat` | `m1`, `llm`, `state`, `docker` | New functionality or module implementation |
| `fix` | `graph`, `api`, `config` | Bug resolution or error handling |
| `docs` | `readme`, `api`, `setup` | Documentation updates only |
| `test` | `m1`, `m6`, `utils` | Test additions or coverage improvements |
| `refactor` | `state`, `routing`, `nodes` | Code restructuring without behavior change |
| `chore` | `deps`, `ci`, `docker` | Maintenance, dependency updates, tooling |

### 🔹 Branch & Merge Workflow
```bash
git checkout -b feat/m1-extraction
# Implement, test, and commit atomically
git add .
git commit -m "feat(m1): integrate pdfplumber extraction with Pydantic validation"
git push -u origin feat/m1-extraction
# Open Pull Request → Peer Review → Merge to main
```

---

## 📌 Project Roadmap & Next Steps

| Phase | Target | Status |
|-------|--------|--------|
| ✅ Infrastructure | Docker Compose, LangGraph skeleton, FastAPI gateway, LLM router | Complete |
| 🚧 Module 1 | PDF specification extraction with structured JSON output | Pending |
| 🔜 Module 2–3 | DXF generation, HD presentation video | Planned |
| 🔜 Module 4–5 | Supplier sourcing (Wikidata/Comtrade), AI negotiation simulation | Planned |
| 🔜 Module 6–7 | TCO calculation (World Bank), Business Plan generation | Planned |
| 🔜 Module 8–9 | Digital twin simulation, Multi-format catalog export | Planned |

This documentation will be updated iteratively as each module is implemented, tested, and integrated into the LangGraph state machine. All changes will maintain backward compatibility and adhere to open-source compliance standards.

---

**🔒 License:** Open-source. Built exclusively with public APIs, open models, and zero proprietary dependencies.
**📞 Support:** Report issues via GitHub Issues. Include `docker compose logs app --tail 20` and OS environment details.
