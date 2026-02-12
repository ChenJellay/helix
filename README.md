# Helix - AI-Native Technical Program Management Platform

Helix is an AI-native TPgM platform built on the philosophy of **Living State**: the Code updates the State, and the State constrains the Code.

## Architecture

- **Hybrid RAG Database** - Vector (ChromaDB) + Graph (Neo4j) + Relational (PostgreSQL)
- **Pluggable LLM Layer** - Supports OpenAI, Anthropic, Google, Ollama, and MLX-LM (Apple Silicon)
- **4 AI Agents** - Risk Analyzer, Scope Checker, Launch Prefill, Gap Analyzer
- **Local-First Git Integration** - Scope-check any branch against design docs without GitHub API
- **Streamlit Dashboard** - Full-featured UI for project management, repo linking, analysis, and monitoring — no CLI required

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- An LLM API key (OpenAI, Anthropic, Google) _or_ a local model via Ollama / MLX-LM

### Setup (Cloud LLM)

```bash
# Clone and enter the project
cd Helix

# Edit .env — set your LLM provider + HELIX_WORKSPACE
# HELIX_WORKSPACE should point to the directory containing your git repos
# (e.g. ~/projects)

# Start all services
docker compose up -d

# Run database migrations
docker compose exec helix-api alembic upgrade head

# (Optional) Seed sample data
docker compose exec helix-api python -m helix.seed
```

### Setup (Local LLM with MLX-LM + Qwen on Apple Silicon)

Run Helix entirely on-device using `mlx-lm` and the 4-bit Qwen 2.5 7B model. No API keys required.

#### 1. Install MLX-LM and download the model

```bash
pip install mlx-lm

# The model will be downloaded automatically on first run (~4.5 GB)
```

#### 2. Start the MLX-LM server

```bash
python -m mlx_lm server \
    --model mlx-community/Qwen2.5-7B-Instruct-4bit \
    --port 8080
```

The server exposes an OpenAI-compatible API at `http://localhost:8080/v1`.

#### 3. Configure Helix

Edit the `.env` file:

```bash
HELIX_MODE=local
HELIX_WORKSPACE=~/projects

LLM_PROVIDER=mlx
MLX_BASE_URL=http://localhost:8080
MLX_MODEL=mlx-community/Qwen2.5-7B-Instruct-4bit
```

Helix auto-detects the Qwen-7B model and activates SLM optimizations: token budgeting, simplified prompts, constrained JSON decoding, local embeddings via `sentence-transformers`, and automatic retries on malformed output.

#### 4. Start the infrastructure and API

```bash
# Start databases (Postgres, ChromaDB, Neo4j, Redis)
docker compose up -d

# Run database migrations
docker compose exec helix-api alembic upgrade head

# (Optional) Seed sample data
docker compose exec helix-api python -m helix.seed
```

#### 5. Open the Dashboard

With the MLX-LM server and Helix API both running, open **http://localhost:8501** in your browser.

Everything below can be done directly from the Streamlit dashboard — see the [Dashboard Workflow](#dashboard-workflow) section for the full walkthrough.

### Access

| Service        | URL                          |
|----------------|------------------------------|
| API (FastAPI)  | http://localhost:8000        |
| API Docs       | http://localhost:8000/docs   |
| Dashboard (UI) | http://localhost:8501        |
| Neo4j Browser  | http://localhost:7474        |
| MLX-LM Server  | http://localhost:8080/v1     |

## Dashboard Workflow

The Streamlit dashboard at **http://localhost:8501** is the primary interface for non-technical users. Every operation — project setup, repo linking, document upload, and all four AI analyses — can be performed entirely from the browser.

### Overview

The sidebar contains two persistent controls:

- **Navigation** — switch between pages (Projects, Documents, Risk Dashboard, Scope Checks, Launch Checklist, Gap Analysis)
- **Active Project selector** — choose the project context once; it persists across all pages

A green health-check indicator confirms the API is reachable.

### Step 1: Create a Project and Link a Repository

Open the **Projects** page.

1. Expand **Create New Project** and fill in a name and description.
2. Under **Link a Repository**, select a git repo from the dropdown (auto-discovered from `HELIX_WORKSPACE`) or type a path manually.
3. Click **Create Project**.

Already have a project without a linked repo? Click the **Link Repository** expander on the project card and pick one.

### Step 2: Upload Design Documents

Switch to the **Documents** page. The active project is pre-selected in the sidebar.

1. Expand **Upload Document**.
2. Paste your PRD, technical design, or meeting notes as Markdown.
3. Choose the document type and click **Upload & Analyze**.

Helix indexes the document into the RAG system and, for PRDs and technical designs, automatically kicks off a risk analysis in the background.

### Step 3: Run Risk Analysis

Open the **Risk Dashboard** page.

- The top section lists every document for the active project with a **Run Risk Analysis** button. Click it to (re-)analyze any document on demand.
- Results appear below: overall risk score, individual risks with probability and impact, mitigations, and dependency graphs.

### Step 4: Run Scope Checks

Open the **Scope Checks** page.

1. If the project has a linked repo, Helix fetches its branches automatically.
2. Select a **base branch** (e.g. `main`) and a **head branch** (your feature branch).
3. Click **Run Scope Check**.

Helix diffs the branches, retrieves relevant design docs via RAG, parses CI/CD workflows, and runs the LLM alignment check. Results — alignment score, violations, and TPM-approval status — appear in the history list.

### Step 5: Generate a Launch Checklist

Open the **Launch Checklist** page and click **Generate Checklist**. The AI reads all project documents and risk assessments to produce a pre-filled checklist with confidence scores, warnings, and gaps.

### Step 6: Define Metric Targets and Run Gap Analysis

Open the **Gap Analysis** page.

1. Add **Metric Targets** (e.g. "P95 Latency < 200ms") using the form at the top.
2. Click **Run Gap Analysis Now**. Helix compares actual metric values against your targets and produces an executive summary, root-cause analysis, and recommendations.

---

## Local Git Integration

Helix runs locally and watches over your project repositories. It compares feature branches against approved design documents to detect scope creep — no GitHub API, webhooks, or public URLs required.

### How it works

```
Local git repo on disk
        |
        +---> Dashboard: Scope Checks page (branch dropdowns)
        |         or
        +---> CLI: helix check --repo . --base main
        |         or
        +---> API: POST /api/check-local
                        |
                        v
              ScopeCheckerAgent.check_branch()
                  |-- git diff base..head  (local)
                  |-- parse .github/workflows/*.yml (local)
                  |-- retrieve design doc (RAG)
                  |-- LLM alignment check
                  +-- display report / store in DB
```

### Configuration

Two environment variables control the local integration:

```bash
# Mode: "local" (default) or "cloud"
HELIX_MODE=local

# Root directory containing your git repos.
# All repo paths stored in the DB are relative to this directory.
HELIX_WORKSPACE=~/projects
```

With `HELIX_WORKSPACE=~/projects`, a repo at `~/projects/payments-service` is stored as `payments-service` in the database. The dashboard auto-discovers every git repo in this directory.

### Option A: Dashboard (recommended for most users)

All repo-linking and scope checks are available through the Streamlit dashboard with no terminal required. See the [Dashboard Workflow](#dashboard-workflow) section above.

### Option B: CLI

```bash
# Link a repo to a project
python -m helix.cli link --repo ~/projects/payments-service --project-id <UUID>

# Check current branch against main (auto-detects both)
python -m helix.cli check --repo ~/projects/payments-service

# Specify branches explicitly
python -m helix.cli check --repo . --base main --head feature/fraud-detection

# Run synchronously and print the full report (no API server needed)
python -m helix.cli check --repo . --sync
```

### Option C: API

```bash
curl -s -X POST http://localhost:8000/api/check-local \
  -H "Content-Type: application/json" \
  -H "X-API-Key: changeme-generate-a-real-key" \
  -d '{
    "repo_path": "payments-service",
    "base_branch": "main",
    "head_branch": "feature/fraud-detection"
  }' | python -m json.tool
```

### (Optional) Automate with a git hook

Install a pre-push hook so scope checks run automatically:

```bash
python -m helix.cli install-hook --repo ~/projects/payments-service --hook pre-push
```

This writes a small shell script to `.git/hooks/pre-push` that calls `helix check` in the background whenever you push.

### CI/CD awareness

Helix automatically parses `.github/workflows/*.yml` files from linked repos and feeds the CI/CD configuration to agents as additional context. This means the Scope Checker can flag changes to files that lack test coverage or CI integration — all without actually connecting to GitHub.

### Scope check output

When violations are detected, Helix reports:

```
## Helix Scope Check Report

**Alignment Score:** 0.45

### Violations Found

- [CRITICAL] **scope_creep** in `src/payments/fraud.py`: New fraud ML pipeline not in approved design
  - **Recommendation:** Submit a design amendment before proceeding
- [WARNING] **missing_feature_flag** in `src/payments/grpc.py`: Rollout has no feature flag
  - **Recommendation:** Add a feature flag for staged rollout

**TPM approval is recommended before merging.**

**Summary:** PR introduces fraud detection pipeline that is not part of the approved design ...

---
*Generated by Helix*
```

### Background repo indexing

Helix periodically re-indexes the file tree of linked repos (every 4 hours) to keep the RAG repo-map context current. In local mode this traverses the filesystem directly — no GitHub API calls.

## Project Structure

```
src/helix/
├── main.py              # FastAPI entrypoint
├── cli.py               # CLI entrypoint (check, link, install-hook)
├── config.py            # Settings + SLM profiles
├── llm/                 # Pluggable LLM abstraction
│   ├── router.py        # litellm-based multi-provider router
│   ├── token_budget.py  # Token budget manager for SLMs
│   ├── prompts/         # Jinja2 prompt templates
│   │   └── slm/         # SLM-optimised prompt variants
│   └── providers/       # OpenAI, Anthropic, Google, Ollama, MLX
├── rag/                 # Hybrid RAG (vector + graph)
├── agents/              # AI agents (risk, scope, launch, gap)
├── integrations/
│   ├── local_git.py     # Async local git client
│   ├── path_resolver.py # Workspace-relative path management
│   ├── workflow_parser.py # GitHub Actions YAML parser (local)
│   └── github.py        # GitHub REST API client (cloud mode)
├── api/routes/
│   ├── workspace.py     # Repo discovery + branch listing
│   ├── local_check.py   # POST /api/check-local
│   ├── analysis.py      # Risk, gap analysis, metric targets
│   ├── projects.py      # Project CRUD
│   ├── documents.py     # Document upload + listing
│   ├── launch.py        # Launch checklist generation
│   ├── webhooks.py      # GitHub webhooks (cloud mode only)
│   └── ...
├── models/              # DB models + Pydantic schemas
├── tasks/               # Background workers
└── db/                  # Database session management

ui/
└── app.py               # Streamlit dashboard (single-page app)
```

## LLM Provider Configuration

| Provider   | `LLM_PROVIDER` | Required env vars                          |
|------------|-----------------|---------------------------------------------|
| OpenAI     | `openai`        | `OPENAI_API_KEY`                            |
| Anthropic  | `anthropic`     | `ANTHROPIC_API_KEY`                         |
| Google     | `google`        | `GOOGLE_API_KEY`                            |
| Ollama     | `ollama`        | `OLLAMA_BASE_URL` (default: `localhost:11434`) |
| MLX-LM     | `mlx`           | `MLX_BASE_URL` (default: `localhost:8080`), `MLX_MODEL` |

When using a local 7B-class model (Qwen, Llama 3 8B, etc.), Helix automatically applies SLM optimizations. You can also force a profile via `SLM_PROFILE=qwen-7b` in your `.env`.

## Lifecycle Stages

Each stage maps to a page on the Streamlit dashboard:

1. **Discovery** — Upload PRD, get AI risk analysis and dependency graph (**Documents** + **Risk Dashboard**)
2. **Execution** — Branch scope-creep detection against approved design docs (**Scope Checks**)
3. **Launch** — Auto-prefilled launch checklists from project artifacts (**Launch Checklist**)
4. **Stewardship** — Post-launch metric monitoring and gap analysis (**Gap Analysis**)

## Cloud / GitHub Integration (Future)

Direct GitHub webhook and GitHub Action integration (PR comments, CI checks) is planned for a future milestone. The existing cloud integration code is gated behind `HELIX_MODE=cloud` and disabled by default. See [docs/CLOUD_DEPLOYMENT.md](docs/CLOUD_DEPLOYMENT.md) for details.

## Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/
```

## License

MIT
