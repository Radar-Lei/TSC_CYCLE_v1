# External Integrations

**Analysis Date:** 2026-02-21

## APIs & External Services

**LLM Inference:**
- OpenAI-compatible API - Used for benchmarking with models served locally (typically via LM Studio).
  - SDK/Client: `openai` Python package.
  - Auth: None (configured as `not-needed` in `benchmark/llm_client.py`).

**Model Hub:**
- Hugging Face - Used via `unsloth` for loading base models (e.g., `Qwen/Qwen3-4B-Base`).
- ModelScope - Secondary model source mentioned in training scripts.

## Data Storage

**Databases:**
- Local Filesystem only - No external database detected.
  - Source Data: JSON/JSONL samples in `outputs/data/` and `outputs/grpo/`.
  - Metrics: CSV and JSON results in `benchmark/results/`.
  - Checkpoints: Pytorch/SafeTensors in `outputs/sft/` and `outputs/grpo/`.

**File Storage:**
- Local filesystem only.

**Caching:**
- Unsloth Compiled Cache - Stores optimized kernels in `unsloth_compiled_cache/`.

## Authentication & Identity

**Auth Provider:**
- Custom - No external auth providers (Auth0/Firebase) used; the system relies on local API connectivity.

## Monitoring & Observability

**Error Tracking:**
- loguru - Local structured logging to `run.log`.

**Logs:**
- File-based logging in `logs/` and `benchmark/results/*/run.log`.

## CI/CD & Deployment

**Hosting:**
- On-premise/Local - Designed for local execution with GPU acceleration.

**CI Pipeline:**
- Docker - `docker/Dockerfile` and associated scripts provide reproducible environments.

## Environment Configuration

**Required env vars:**
- `SUMO_HOME`: Critical for locating SUMO binaries.
- `SUMO_GUI`: Optional, for manual visualization.

**Secrets location:**
- Not applicable - No external secret management detected; `.env` files not found in standard exploration.

## Webhooks & Callbacks

**Incoming:**
- None detected.

**Outgoing:**
- None detected.

---

*Integration audit: 2026-02-21*
