# External Integrations

**Analysis Date:** 2026-02-09

## APIs & External Services

**Model Hosting:**
- ModelScope - Used to fetch models or datasets.
  - SDK/Client: `modelscope`
  - Auth: Not explicitly configured in codebase (uses public access).

**Large Language Models:**
- Unsloth/HuggingFace - Base models (e.g., `unsloth/Qwen3-4B-Base`) are pulled from these repositories.

## Data Storage

**Databases:**
- None detected (File-based storage used).

**File Storage:**
- Local filesystem only.
  - Data output: `outputs/data/` (JSONL format)
  - State snapshots: `outputs/states/`
  - Model checkpoints: `outputs/sft/model`

**Caching:**
- None detected.

## Authentication & Identity

**Auth Provider:**
- Custom / None - The system relies on local/container execution permissions.
  - Implementation: User UID/GID mapping in `docker/data.sh` to ensure file ownership.

## Monitoring & Observability

**Error Tracking:**
- None detected.

**Logs:**
- Standard Python logging: `src/utils/logging_config.py`
- Log file: `phase_processing.log`

## CI/CD & Deployment

**Hosting:**
- On-premise/Cloud GPU Instances (managed via Docker).

**CI Pipeline:**
- None detected in codebase.

## Environment Configuration

**Required env vars:**
- `SUMO_HOME`: Path to SUMO installation.
- `PATH`: Updated to include SUMO and CUDA binaries.

**Secrets location:**
- No sensitive secrets detected. Configuration is stored in `config/config.json`.

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- None.

---

*Integration audit: 2026-02-09*
