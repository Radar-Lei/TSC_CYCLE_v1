# External Integrations

**Analysis Date:** 2026-02-09

## APIs & External Services

**Machine Learning Models:**
- Hugging Face / ModelScope - Models like `unsloth/Qwen3-4B-Base` are pulled from these hubs as seen in `config/config.json` and `qwen3_(4b)_grpo.py`.
- OpenR1 / Math Datasets - Used for initial pre-fine-tuning of reasoning models.

## Data Storage

**Databases:**
- None detected. The project relies on local filesystem storage.

**File Storage:**
- Local Filesystem: JSON and CSV files are used for traffic history (`traffic_history.json`), training data (`training_data.json`), and metrics (`intersection_metrics.csv`).
- XML: SUMO state files (`.xml`) are used for checkpointing simulations during GRPO evaluation.

**Caching:**
- None detected beyond PyTorch/Transformers model caching.

## Authentication & Identity

**Auth Provider:**
- Custom / None: The system operates locally. Git and Hugging Face tokens may be used during development but are not integrated into the runtime logic beyond potential `push_to_hub` calls (disabled in code).

## Monitoring & Observability

**Error Tracking:**
- None.

**Logs:**
- Local logging: `src/utils/logging_config.py` sets up standard Python logging.
- Console output: Heavily used for tracking simulation progress and training steps.

## CI/CD & Deployment

**Hosting:**
- Local or Private GPU Cloud: Deployed via Docker containers.

**CI Pipeline:**
- None detected.

## Environment Configuration

**Required env vars:**
- `SUMO_HOME`: Path to SUMO installation.
- `PATH`: Must include SUMO tools and CUDA binaries.
- `DEBIAN_FRONTEND`: Set to `noninteractive` in Docker.

**Secrets location:**
- Not applicable (no persistent external service secrets found in logic).

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- None.

---

*Integration audit: 2026-02-09*
