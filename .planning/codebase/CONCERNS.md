# Codebase Concerns

**Analysis Date:** 2026-03-25

## Critical

- [ ] **SUMO port collision risk**: `src/grpo/rewards.py:273` and `src/grpo/baseline.py:70` use `random.randint(10000, 60000)` for TraCI ports. With parallel workers this creates a real risk of port collision. The benchmark module (`benchmark/simulation.py:243`) correctly uses `traci.getFreeSocketPort()` instead. Fix: replace `random.randint` with `traci.getFreeSocketPort()` in both `src/grpo/rewards.py` and `src/grpo/baseline.py`.

- [ ] **Token estimation is a rough approximation**: `src/grpo/rewards.py:633` estimates token count as `len(think_content) / 2` (character count divided by 2). This is an unreliable heuristic for Chinese text where tokenization varies significantly. The reward function `think_length_reward` uses this for penalty/bonus scoring, which could misfire. Fix: use actual tokenizer for accurate token counts, or at minimum calibrate the ratio against real tokenizer output.

## Important

- [ ] **SYSTEM_PROMPT duplicated in 6 files**: The same system prompt string is copy-pasted across `src/data_generator/prompt_builder.py:18`, `benchmark/prompt_builder.py:24`, `src/scripts/generate_grpo_data.py:16`, `src/test_gguf.py:16`, `src/test_lmstudio.py:28`, `src/sft/test_inference.py:22`. If the prompt changes, all 6 files must be updated manually. Fix: extract to a shared constants module (e.g., `src/constants.py`) and import everywhere.

- [ ] **TASK_TEMPLATE duplicated in 2 files**: `src/data_generator/prompt_builder.py:27` and `benchmark/prompt_builder.py:33` contain the same task template. The benchmark version intentionally avoids importing from `src/`, but this creates drift risk. Fix: consider a shared data file (e.g., YAML/JSON) that both modules read.

- [ ] **`get_sumocfg_for_state` duplicated**: Identical function logic exists in both `src/grpo/rewards.py:239` and `src/grpo/baseline.py:23`. Both parse state file paths and map to sumocfg paths. Fix: extract to a shared utility in `src/utils/`.

- [ ] **Bare `except:` clauses throughout SUMO integration code**: Found 20+ bare `except:` statements that silently swallow all exceptions including `KeyboardInterrupt` and `SystemExit`. Key locations:
  - `src/grpo/rewards.py:156,179,309,335,345,361,430,483`
  - `src/grpo/baseline.py:105,135,145,163`
  - `sumo_simulation/sumo_simulator.py:292,316,444,1160,1803`
  Fix: replace with `except Exception:` at minimum, and log errors where appropriate.

- [ ] **Dockerfile references old project name**: `docker/Dockerfile:55-67` creates directories under `/home/samuel/SCU_TSC` and sets `WORKDIR /home/samuel/SCU_TSC`, but the project is now `TSC_CYCLE`. This means Docker builds use a stale workspace path. Fix: update Dockerfile paths to match current project name.

- [ ] **`sumo_simulator.py` is 2127 lines**: `sumo_simulation/sumo_simulator.py` is a single monolithic file. The `SUMOSimulator` class handles simulation lifecycle, data collection, signal control, metric computation, and state recording -- all in one class. This makes testing and maintenance difficult. Fix: decompose into separate modules for simulation control, metrics, and signal management.

## Minor

- [ ] **Hardcoded SUMO paths for macOS/custom installs**: `sumo_simulation/sumo_simulator.py:21-29` contains hardcoded paths like `/Users/leida/Cline/sumo/share/sumo` and `/Users/leida/Cline/sumo` which are developer-specific. The benchmark module's `_ensure_sumo_home()` in `benchmark/simulation.py:29-60` handles this more cleanly. Fix: remove developer-specific paths and rely on `SUMO_HOME` env var or standard install locations only.

- [ ] **`build_from_phase_data` returns placeholder string**: `src/data_generator/prompt_builder.py:193-201` has a method `build_from_phase_data` that returns `"Use build_prompt() with Prediction object. Timestamp: {timestamp}"` -- it is unimplemented. Fix: either implement the method or remove it.

- [ ] **Hardcoded `localhost:1234` for LM Studio**: `benchmark/config.py:38`, `benchmark/batch_config.py:106`, `benchmark/llm_client.py:68`, `src/test_lmstudio.py:41` all default to `http://localhost:1234/v1`. This is fine for local development but should be documented as a requirement. The API key is hardcoded as `"not-needed"` in `benchmark/llm_client.py:92` and `src/test_lmstudio.py:56`.

- [ ] **SFT trainer output path hardcoded**: `src/sft/train.py:224,252` hardcodes `output_dir="outputs/sft/checkpoints"` instead of reading from config. Fix: derive from config paths.

- [ ] **Inconsistent model name references**: `src/sft/train.py:5` docstring says "GLM-4.7-Flash" but `config/config.json:5` specifies `model/Qwen3-4B-Base`. The GLM fallback logic in `src/sft/train.py:64` checks for "GLM" in model name -- dead code path with current config. Fix: update docstrings to reflect actual model usage, or remove GLM-specific logic if no longer needed.

## Security

- [ ] **`.env` files properly gitignored**: `.gitignore:54-55` excludes `.env` and `.env.*`. No `.env` files found in the repository. This is correctly configured.

- [ ] **`trust_remote_code=True` used in model loading**: `src/sft/train.py:77,88,94` and `src/grpo/train.py` use `trust_remote_code=True` when loading models. This is necessary for Qwen3/GLM models but executes arbitrary code from model repositories. Ensure models are only loaded from trusted sources (local or verified HuggingFace repos).

- [ ] **No input validation on config.json**: `config/config.json` is loaded without schema validation in `src/sft/train.py:44-47`, `src/grpo/train.py`, and `src/grpo/baseline.py:198`. Malformed config could cause cryptic errors deep in the training pipeline. Fix: add JSON schema validation at load time.

## Performance

- [ ] **SUMO ProcessPoolExecutor never cleaned up**: `src/grpo/rewards.py:495-498` creates a `ProcessPoolExecutor` stored in module-level `_sumo_pool` global, but it is never shut down. During long GRPO training runs, zombie processes could accumulate if workers crash. Fix: add cleanup via `atexit` handler or explicit shutdown.

- [ ] **Sequential warmup in benchmark simulation**: `benchmark/simulation.py:270-274` runs warmup steps in a pure Python loop calling `simulationStep()` one at a time. For warmup periods of 300+ steps, this adds unnecessary overhead. Note: SUMO's TraCI does not support multi-step advancement, so this is a TraCI limitation rather than a code issue.

- [ ] **SFT data loaded entirely into memory**: `src/sft/train.py:152-157` reads all JSONL lines into a list before converting to HuggingFace Dataset. For very large datasets this could cause OOM. Current dataset sizes are small enough that this is not an immediate problem.

## TODOs Found in Code

- `sumo_simulation/sumo_simulator.py:146`: `# TODO: intersection_state_recorder 模块不存在,暂时注释掉`
- `sumo_simulation/sumo_simulator.py:544`: `# TODO: intersection_state_recorder 模块不存在,暂时注释掉`
- `sumo_simulation/sumo_simulator.py:1215`: `# TODO: intersection_state_recorder 模块不存在,暂时注释掉`

All three TODOs reference a missing `intersection_state_recorder` module that was part of the original `sumo_sim` package. The module appears to have been removed during a refactor but the commented-out references remain.

## Test Coverage Gaps

- [ ] **Only 1 test file in benchmark, 1 in grpo**: `benchmark/tests/test_weighted_stats.py` (423 lines) tests weighted statistics calculation. `src/grpo/test_rewards.py` (393 lines) tests reward functions. No tests exist for:
  - `src/sft/train.py` - SFT training pipeline
  - `src/data_generator/` - data generation modules
  - `src/phase_processor/` - phase processing logic
  - `benchmark/simulation.py` - SUMO simulation control
  - `benchmark/timing_parser.py` - LLM output parsing
  Fix: prioritize tests for `src/phase_processor/` (critical validation logic) and `benchmark/timing_parser.py` (LLM output parsing is failure-prone).

---

*Concerns audit: 2026-03-25*
