# External Integrations

**Analysis Date:** 2026-02-09

## APIs & External Services

**Model Repositories:**
- Hugging Face - Used for downloading base models (`unsloth/Qwen3-4B-Base`) and datasets (`unsloth/OpenMathReasoning-mini`, `open-r1/DAPO-Math-17k-Processed`).
  - SDK/Client: `transformers`, `datasets`
- ModelScope - Installed in Docker, used for model access in mainland China environments.
  - SDK/Client: `modelscope`

## Data Storage

**Databases:**
- None - Project relies on local filesystem for data storage.

**File Storage:**
- Local Filesystem - Used for training data (`data/training/`), model checkpoints (`outputs/`), and simulation state/routes.
- XML Files - Primary format for SUMO simulation data (`.rou.xml`).

**Caching:**
- Hugging Face Cache - Default location for downloaded models and datasets.

## Authentication & Identity

**Auth Provider:**
- Hugging Face Token - Optional, mentioned for pushing models to the hub (`HF_TOKEN`).

## Monitoring & Observability

**Error Tracking:**
- None - No external service detected.

**Logs:**
- Local logs stored in `logs/` (referenced in `docker/Dockerfile`) and stdout during training.
- WandB/TrackIO - Mentioned in training scripts as optional (`report_to = "none"`).

## CI/CD & Deployment

**Hosting:**
- Local or Private GPU Cloud - Environment is self-contained in Docker.

**CI Pipeline:**
- None - No CI configuration files detected.

## Environment Configuration

**Required env vars:**
- `SUMO_HOME` - Path to the SUMO installation (critical for TraCI).
- `USER_ID`, `GROUP_ID` - Used for Docker permission alignment.

**Secrets location:**
- Not applicable - Project primarily uses public datasets and base models.

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

---

*Integration audit: 2026-02-09*
