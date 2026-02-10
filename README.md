# Helix - AI-Native Technical Program Management Platform

Helix is an AI-native TPgM platform built on the philosophy of **Living State**: the Code updates the State, and the State constrains the Code.

## Architecture

- **Hybrid RAG Database** - Vector (ChromaDB) + Graph (Neo4j) + Relational (PostgreSQL)
- **Pluggable LLM Layer** - Supports OpenAI, Anthropic, Google, Ollama, and MLX-LM (Apple Silicon)
- **4 AI Agents** - Risk Analyzer, Scope Checker, Launch Prefill, Gap Analyzer
- **GitHub Integration** - PR compliance checking via webhook + GitHub Action
- **Streamlit Dashboard** - Project management, risk tracking, launch checklists

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An LLM API key (OpenAI, Anthropic, Google) _or_ a local model via Ollama / MLX-LM

### Setup (Cloud LLM)

```bash
# Clone and enter the project
cd Helix

# Edit .env with your API keys (LLM provider, GitHub token, etc.)
# See the GitHub Integration section below for webhook/action setup

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

Create a `.env` file (or edit the existing one) with:

```bash
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

#### 5. Demo: run a risk analysis

With the MLX-LM server and Helix API both running, try a quick end-to-end flow:

```bash
# Create a project
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Demo Project", "description": "Testing local Qwen inference"}' \
  | python -m json.tool

# Upload a PRD for risk analysis (replace <PROJECT_ID> with the id from above)
curl -s -X POST http://localhost:8000/api/documents \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "1a63e3f9-7e24-4878-9dc8-454de0c0daa7",
    "title": "Sample PRD",
    "doc_type": "prd",
    "content": "We will migrate the payments service from REST to gRPC, adding a new fraud detection ML pipeline that calls an external vendor API with a 99.9% SLA requirement. The rollout targets 50M users over 2 weeks with no feature flags."
  }' \
  | python -m json.tool

# Trigger risk analysis on the document (replace <DOCUMENT_ID>)
curl -s -X POST http://localhost:8000/api/analysis/risk/ded6da7f-cad1-4612-b3a8-c5d3fe14438b \
  | python -m json.tool
```

The risk analyzer will process the PRD through the local Qwen model and return identified risks, dependencies, and mitigations — all running on your Mac.

### Access

| Service        | URL                          |
|----------------|------------------------------|
| API (FastAPI)  | http://localhost:8000        |
| API Docs       | http://localhost:8000/docs   |
| Dashboard (UI) | http://localhost:8501        |
| Neo4j Browser  | http://localhost:7474        |
| MLX-LM Server  | http://localhost:8080/v1     |

## Project Structure

```
src/helix/
├── main.py           # FastAPI entrypoint
├── config.py         # Settings + SLM profiles
├── llm/              # Pluggable LLM abstraction
│   ├── router.py     # litellm-based multi-provider router
│   ├── token_budget.py # Token budget manager for SLMs
│   ├── prompts/      # Jinja2 prompt templates
│   │   └── slm/      # SLM-optimised prompt variants
│   └── providers/    # OpenAI, Anthropic, Google, Ollama, MLX
├── rag/              # Hybrid RAG (vector + graph)
├── agents/           # AI agents (risk, scope, launch, gap)
├── integrations/     # GitHub, metrics clients
├── api/routes/       # API endpoints
├── models/           # DB models + Pydantic schemas
├── tasks/            # Background workers
└── db/               # Database session management
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

## GitHub Integration

Helix plugs into your GitHub workflow to automatically check every PR for scope creep and design-doc alignment. There are two integration paths — use whichever fits your setup.

### How it works

```
PR opened / updated
        │
        ├──▶ Path A: GitHub Webhook ──▶ Helix API (/api/webhooks/github)
        │        (HMAC-SHA256 signature)
        │
        └──▶ Path B: GitHub Action  ──▶ Helix API (/api/webhooks/github)
                 (API key auth)
                                              │
                                              ▼
                                   ScopeCheckerAgent
                                     ├─ fetch PR diff
                                     ├─ retrieve design doc (RAG)
                                     ├─ LLM alignment check
                                     └─ post comment on PR
```

Both paths end at the same webhook endpoint. The endpoint accepts **either** a GitHub HMAC signature (`X-Hub-Signature-256`) **or** a Helix API key (`X-API-Key`).

### Prerequisites

1. A Helix project with a linked GitHub repo (`github_repo` field).
2. A GitHub personal access token (classic) with the **`repo`** scope, or a GitHub App installation token.
3. The Helix API must be reachable from GitHub (public URL or tunnel).

### Environment variables

Add these to your `.env`:

```bash
# GitHub personal access token — used by the Scope Checker to read PRs and post comments
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Webhook secret — must match the secret configured in your GitHub repo's webhook settings
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# Helix API key — used by the GitHub Action to authenticate with Helix
HELIX_API_KEY=your-api-key
```

### Link a project to a repo

When you create a project (or update an existing one), include the full `owner/repo` name:

```bash
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Payments Migration",
    "description": "REST-to-gRPC migration",
    "github_repo": "acme-corp/payments-service"
  }' | python -m json.tool
```

The `github_repo` field is what Helix uses to match incoming webhook events to the correct project and its design docs.

### Path A: Direct GitHub Webhook

Best when your Helix API has a stable public URL.

#### 1. Configure the webhook in GitHub

Go to your repo **Settings > Webhooks > Add webhook** and fill in:

| Field           | Value                                                   |
|-----------------|---------------------------------------------------------|
| Payload URL     | `https://<your-helix-host>/api/webhooks/github`         |
| Content type    | `application/json`                                      |
| Secret          | The same value as `GITHUB_WEBHOOK_SECRET` in your `.env`|
| Events          | Select **Pull requests**                                |

#### 2. Verify

Open or update a PR in the linked repo. Helix will:
1. Verify the HMAC-SHA256 signature.
2. Look up the project by `github_repo`.
3. Retrieve the approved design doc from RAG.
4. Send the PR diff + design doc to the LLM for alignment analysis.
5. Post a **Helix Scope Check Report** comment on the PR with an alignment score, any violations, and recommendations.

### Path B: GitHub Action

Best when the Helix API is behind a firewall or you prefer a CI-based trigger.

#### 1. Add repository secrets

In your repo, go to **Settings > Secrets and variables > Actions** and add:

| Secret              | Value                                                         |
|---------------------|---------------------------------------------------------------|
| `HELIX_API_URL`     | Full URL of the Helix API (e.g. `https://helix.internal:8000`)|
| `HELIX_API_KEY`     | The same value as `HELIX_API_KEY` in your Helix `.env`        |
| `HELIX_PROJECT_ID`  | UUID of the Helix project linked to this repo                 |

#### 2. Add the workflow

Copy `.github/workflows/helix-tpm.yml` into the target repository (or reference it from a central repo):

```yaml
name: Helix TPM Guardrails
on: [pull_request]

jobs:
  alignment-check:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Helix Scope Check
        uses: ./github-action
        with:
          helix_api_url: ${{ secrets.HELIX_API_URL }}
          helix_api_key: ${{ secrets.HELIX_API_KEY }}
          project_id: ${{ secrets.HELIX_PROJECT_ID }}
```

The action builds a lightweight Docker image, constructs a synthetic `pull_request` webhook payload, and sends it to Helix authenticated with `X-API-Key`.

#### 3. Verify

Open a PR. The **Helix TPM Guardrails** check will appear in the PR's "Checks" tab, and the scope-check comment will be posted just like the webhook path.

### Scope Check output

When violations are detected, Helix posts a comment like:

```
## Helix Scope Check Report

**Alignment Score:** 0.45

### Violations Found

- 🔴 **scope_creep** in `src/payments/fraud.py`: New fraud ML pipeline not in approved design
  - **Recommendation:** Submit a design amendment before proceeding
- 🟡 **missing_feature_flag** in `src/payments/grpc.py`: Rollout has no feature flag
  - **Recommendation:** Add a feature flag for staged rollout

⚠️ **TPM approval is required before merging this PR.**

**Summary:** PR introduces fraud detection pipeline that is not part of the approved design ...

---
*Generated by Helix TPM Guardrails*
```

### Background repo indexing

Helix periodically re-indexes the file tree of linked repos (every 4 hours) to keep the RAG repo-map context current. This runs automatically via the background scheduler — no extra setup needed.

## Lifecycle Stages

1. **Discovery** - Upload PRD, get AI risk analysis and dependency graph
2. **Execution** - PR scope-creep detection against approved design docs
3. **Launch** - Auto-prefilled launch checklists from project artifacts
4. **Stewardship** - Post-launch metric monitoring and gap analysis

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
