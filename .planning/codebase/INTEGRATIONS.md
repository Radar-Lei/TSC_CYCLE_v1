# External Integrations

**Analysis Date:** 2026-02-09

## APIs & External Services

**Large Language Models (LLM):**
- GLM-4.7 (Zhipu AI) - Used for backfilling "thinking" reasoning content into training data.
  - SDK/Client: `urllib.request` (Standard Library implementation)
  - Auth: `GLM_API_KEY` (env var)
- Qwen3-4B - Primary model target for fine-tuning (GRPO/SFT) to optimize traffic signal control.
  - SDK/Client: `unsloth`, `transformers`

## Data Storage

**Databases:**
- Not detected (Primary data storage is JSON/JSONL files).

**File Storage:**
- Local filesystem - Used for all data storage.
  - Training data: `data/training/`
  - SFT outputs: `outputs/sft/`
  - SUMO configs: `sumo_simulation/`
  - Temporary state files: `.xml` files generated during GRPO counterfactual simulation (e.g., `temp_grpo_state_*.xml`).

**Caching:**
- None (Not detected).

## Authentication & Identity

**Auth Provider:**
- Custom (API Key based) - Used for Zhipu AI (GLM) API access.

## Monitoring & Observability

**Error Tracking:**
- None (Not detected).

**Logs:**
- File-based logging - `phase_processing.log` and custom logging configuration in `src/utils/logging_config.py`.

## CI/CD & Deployment

**Hosting:**
- Not specified (Local/Server execution).

**CI Pipeline:**
- None (Not detected).

## Environment Configuration

**Required env vars:**
- `GLM_API_KEY` - Required for `src/scripts/backfill_thinking.py`.
- `SUMO_HOME` - Path to SUMO installation, required for `traci` and simulation.
- `PYTHONPATH` - Often adjusted in scripts to include project root.

**Secrets location:**
- `.env` file in the project root.

## Webhooks & Callbacks

**Incoming:**
- None (Not detected).

**Outgoing:**
- Zhipu AI API calls - To `https://open.bigmodel.cn/api/paas/v4/chat/completions`.

## Internal Integrations (Simulator)

**SUMO TraCI:**
- Integration between Python and the SUMO traffic simulator.
- Used for:
  - Retrieving traffic metrics (queues, waiting time, speed).
  - Controlling traffic light phases.
  - Saving/Loading simulation state for counterfactual reasoning (GRPO).

---

*Integration audit: 2026-02-09*
