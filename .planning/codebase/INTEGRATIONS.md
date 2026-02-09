# External Integrations

**Analysis Date:** 2026-02-09

## APIs & External Services

**Large Language Models:**
- ZhipuAI (GLM-4.7) - Used for backfilling "thinking" process in training data.
  - SDK/Client: `urllib.request` (Custom implementation in `src/scripts/backfill_thinking.py`)
  - Auth: `ZHIPUAI_API_KEY` (env var)

## Data Storage

**Databases:**
- None (Local file-based storage using JSON/JSONL).

**File Storage:**
- Local filesystem only.
  - `data/` - Input traffic data and network files.
  - `outputs/` - Generated training samples and model checkpoints.
  - `sumo_simulation/` - SUMO environment files.

**Caching:**
- `unsloth_compiled_cache/` - Local directory for Unsloth compilation cache.

## Authentication & Identity

**Auth Provider:**
- Custom (API Key based for external LLM services).
  - Implementation: API Key loaded from `.env` and included in HTTP headers in `src/scripts/backfill_thinking.py`.

## Monitoring & Observability

**Error Tracking:**
- None.

**Logs:**
- Local file logging.
  - Implementation: Custom logging setup in `src/utils/logging_config.py` and `src/scripts/train_sft.py`.

## CI/CD & Deployment

**Hosting:**
- Local/Private GPU Server (indicated by local path structures and NVIDIA requirement).

**CI Pipeline:**
- None detected.

## Environment Configuration

**Required env vars:**
- `SUMO_HOME`: Path to the SUMO installation.
- `ZHIPUAI_API_KEY`: API key for ZhipuAI (GLM-4.7).
- `PYTHONPATH`: Should include the project root for module imports.

**Secrets location:**
- `.env` file in the project root.

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- Outgoing API calls to `https://open.bigmodel.cn/api/paas/v4/chat/completions` for GLM-4.7 inference.

---

*Integration audit: 2026-02-09*
