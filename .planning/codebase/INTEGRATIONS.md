# External Integrations

**Analysis Date:** 2026-02-09

## APIs & External Services

**Model Repositories:**
- Hugging Face / ModelScope - Source for base models (e.g., `unsloth/Qwen3-4B-Base`).
  - SDK/Client: `transformers`, `unsloth`
  - Auth: Handled via environment variables or CLI login (if needed).

## Data Storage

**Databases:**
- None (Filesystem-based storage).

**File Storage:**
- Local filesystem for JSONL datasets and model checkpoints.
- Location: `outputs/sft/`, `outputs/data/`, `outputs/states/`.

**Caching:**
- Model caching via `HF_HOME` and `MODELSCOPE_CACHE`.
- Unsloth specific cache: `unsloth_compiled_cache/`.

## Authentication & Identity

**Auth Provider:**
- Custom / None (The project is a training pipeline; no user-facing authentication detected).

## Monitoring & Observability

**Error Tracking:**
- None.

**Logs:**
- File-based logging: `training.log` in output directories.
- Console output via Python `logging` module.

## CI/CD & Deployment

**Hosting:**
- Local or Cloud GPU instances (via Docker).

**CI Pipeline:**
- None (Manual script execution via `docker/*.sh`).

## Environment Configuration

**Required env vars:**
- `SUMO_HOME`: Path to SUMO installation.
- `HF_HOME`: Hugging Face cache directory.
- `MODELSCOPE_CACHE`: ModelScope cache directory.
- `UNSLOTH_USE_MODELSCOPE`: Toggle for using ModelScope instead of Hugging Face.

**Secrets location:**
- Not detected (likely passed as environment variables if needed for private repositories).

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- None.

---

*Integration audit: 2026-02-09*
