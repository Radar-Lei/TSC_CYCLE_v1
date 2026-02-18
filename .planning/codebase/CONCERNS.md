# Codebase Concerns

**Analysis Date:** 2026-02-18

## Tech Debt

### Bare except Clauses (Error Handling Anti-pattern)
- **Issue:** 13 instances of bare `except:` clauses that silently swallow all exceptions without logging or specific handling
- **Files:**
  - `src/grpo/rewards.py`: Lines 156, 179, 309, 335, 345, 361, 430, 483
  - `src/grpo/baseline.py`: Lines 105, 135, 145, 163
  - `src/scripts/analyze_grpo_training.py`: Line 63
- **Impact:** Makes debugging extremely difficult; silently catches system exceptions like KeyboardInterrupt; hides actual error causes
- **Fix approach:** Replace `except:` with `except Exception as e:` and log the exception details. For JSON parsing, catch `json.JSONDecodeError` specifically

### Global State in Reward Functions
- **Issue:** Module-level globals `_config`, `_baseline`, `_sumo_pool`, `_print_counter` in `src/grpo/rewards.py`
- **Files:** `src/grpo/rewards.py`: Lines 29-32, 53, 397
- **Impact:** Not thread-safe; makes testing difficult; implicit dependencies; potential race conditions in parallel SUMO execution
- **Fix approach:** Encapsulate state in a class (e.g., `RewardCalculator`) with explicit initialization; use dependency injection

### Duplicated SUMO_HOME Environment Setup
- **Issue:** Identical 20+ line SUMO_HOME path discovery code duplicated across multiple files
- **Files:**
  - `src/data_generator/day_simulator.py`: Lines 34-53
  - `src/data_generator/predictive_sampler.py`: Lines 22-41
  - `src/grpo/rewards.py`: Different approach (line 277-282)
  - `src/grpo/baseline.py`: Different approach (line 73-78)
- **Impact:** Code duplication; inconsistent handling; maintenance burden
- **Fix approach:** Create `src/utils/sumo_config.py` with centralized `get_sumo_binary()` and `ensure_sumo_env()` functions

### Reference File in Git (`qwen3_(4b)_grpo.py`)
- **Issue:** Root-level `qwen3_(4b)_grpo.py` appears to be a reference implementation from unsloth
- **Files:** `/home/samuel/TSC_CYCLE/qwen3_(4b)_grpo.py` (23KB, 647 lines)
- **Impact:** Listed in `.gitignore` but already committed; confuses codebase structure; may cause merge conflicts
- **Fix approach:** Move to `docs/reference/` or `grpo_reference_only/` (already in gitignore) and remove from git tracking

## Known Bugs

### Zero-std Reward Issue (GRPO Training)
- **Symptoms:** GRPO reward standard deviation can become zero during training, causing learning to stall
- **Files:** `src/scripts/analyze_grpo_training.py` (built to detect this)
- **Trigger:** When all `num_generations` completions receive identical rewards
- **Workaround:** Analysis tool exists to monitor and detect zero-std conditions

### JSON Parsing Fragility in Prompt Extraction
- **Symptoms:** `check_constraints` and `sumo_simulation_reward` fail to extract phase_waits from prompts
- **Files:** `src/grpo/rewards.py`: Lines 170-176, 437-443
- **Trigger:** Regex pattern `r'"phase_waits"\s*:\s*(\[.*?\])'` may fail on nested JSON or edge cases
- **Impact:** Valid completions incorrectly scored as -2.0 or 0.0
- **Fix approach:** Use proper JSON parsing with a known schema; avoid regex for structured data extraction

## Security Considerations

### No Critical Security Issues Found
- **Risk:** Low
- **Files:** N/A
- **Current mitigation:** `.env` is in `.gitignore`; no hardcoded credentials detected in source files
- **Recommendations:**
  - The `benchmark/llm_client.py` uses `api_key="not-needed"` for LM Studio (safe - local inference)
  - Continue to keep secrets in `.env` files excluded from git

## Performance Bottlenecks

### SUMO Simulation Sequential Per Completion
- **Problem:** Each completion triggers a full SUMO simulation; while parallelized via ProcessPoolExecutor, simulation time dominates
- **Files:** `src/grpo/rewards.py`: Lines 257-363, 503-509
- **Cause:** SUMO simulation is inherently slow (requires stepping through time)
- **Improvement path:**
  - Current: Max 4 parallel SUMO instances (line 497)
  - Consider caching baseline results for identical state files
  - Consider reducing timeout (currently 60s) for faster fail-fast

### Process Pool Not Reused Across Steps
- **Problem:** `_sumo_pool` is created once but never shutdown; memory leak potential
- **Files:** `src/grpo/rewards.py`: Lines 31, 495-498
- **Cause:** Pool created on first call, never explicitly closed
- **Improvement path:** Add explicit cleanup function or use context manager pattern

### 90th Percentile Data Filtering
- **Problem:** All prompts longer than 90th percentile are discarded
- **Files:** `src/grpo/train.py`: Lines 164-169
- **Cause:** Reduces memory but loses potentially valuable training data
- **Improvement path:** Consider dynamic batching or gradient checkpointing instead of hard filtering

## Fragile Areas

### Chat Template Duplication
- **Files:**
  - `src/sft/train.py`: Lines 76-124
  - `src/grpo/train.py`: Lines 79-126
- **Why fragile:** Identical `setup_chat_template()` function in both files; any change must be made twice
- **Safe modification:** Extract to `src/utils/chat_template.py` and import
- **Test coverage:** No unit tests for template correctness

### Regex Pattern for Format Matching
- **Files:** `src/grpo/rewards.py`: Line 38-41
- **Why fragile:** Complex regex `r"<end_working_out>.*?<SOLUTION>(.+?)</SOLUTION>\s*$"` assumes specific tag ordering
- **Safe modification:** Use multi-step parsing; validate each tag independently
- **Test coverage:** Partial - `test_rewards.py` has some test cases but not exhaustive

### Baseline Generation Depends on State File Naming
- **Files:** `src/grpo/baseline.py`: Lines 24-43, `src/grpo/rewards.py`: Lines 239-254
- **Why fragile:** `get_sumocfg_for_state()` uses string parsing on file paths; assumes specific directory structure
- **Safe modification:** Use explicit mapping or configuration for scenario-to-sumocfg mapping
- **Test coverage:** None

## Scaling Limits

### Parallel Workers (16 max)
- **Current capacity:** 16 parallel SUMO workers (config.simulation.parallel_workers)
- **Files:** `config/config.json`: Line 107
- **Limit:** Memory-bound; each SUMO instance consumes significant RAM
- **Scaling path:** Consider distributing across multiple machines for large-scale data generation

### GRPO num_generations (4)
- **Current capacity:** 4 generations per prompt
- **Files:** `config/config.json`: Line 59
- **Limit:** GPU memory constrained; higher values require more VRAM
- **Scaling path:** Use gradient checkpointing or reduce model precision

### Max Sequence Length (2048)
- **Current capacity:** 2048 tokens max
- **Files:** `config/config.json`: Lines 7, 43
- **Limit:** Fixed by model architecture; longer sequences need different model
- **Scaling path:** Use Qwen3-8B or larger model with longer context window

## Dependencies at Risk

### traci (SUMO Traffic Control Interface)
- **Risk:** External dependency on SUMO installation; version-sensitive API
- **Files:** Multiple files import `traci`
- **Impact:** SUMO version mismatch can break simulation
- **Migration plan:** Pin SUMO version in documentation; consider Docker for consistent environment

### unsloth
- **Risk:** Fast-moving library with frequent API changes
- **Files:** `src/sft/train.py`, `src/grpo/train.py`, `src/scripts/merge_checkpoint.py`
- **Impact:** Breaking changes may require code updates
- **Migration plan:** Pin specific version; monitor changelog

### trl (Transformer Reinforcement Learning)
- **Risk:** GRPOTrainer API is relatively new
- **Files:** `src/grpo/train.py`: Line 19
- **Impact:** API changes could break training
- **Migration plan:** Pin version; abstract trainer interface

## Missing Critical Features

### No Automated Test Suite
- **Problem:** Only manual test scripts (`test_rewards.py`, `test_inference.py`); no pytest/unittest framework
- **Files:** `src/grpo/test_rewards.py`, `src/sft/test_inference.py` are standalone scripts, not proper tests
- **Blocks:** CI/CD integration; regression testing

### No Configuration Validation
- **Problem:** Config loaded without schema validation; typos silently ignored
- **Files:** All config loading uses plain `json.load()`
- **Blocks:** Early error detection; configuration debugging

### No Logging Framework
- **Problem:** Uses `print()` statements throughout; no log levels, file output, or structured logging
- **Files:** Nearly all Python files
- **Blocks:** Production debugging; log analysis

## Test Coverage Gaps

### Reward Functions
- **What's not tested:** SUMO simulation reward (requires actual SUMO); parallel execution; timeout handling
- **Files:** `src/grpo/rewards.py`
- **Risk:** Incorrect reward calculation may silently corrupt training
- **Priority:** High

### Data Generation Pipeline
- **What's not tested:** End-to-end data generation; state file creation; noise application
- **Files:** `src/data_generator/` directory
- **Risk:** Invalid training data may be silently generated
- **Priority:** High

### GRPO Training Loop
- **What's not tested:** Full training run; checkpoint saving/loading; model merging
- **Files:** `src/grpo/train.py`
- **Risk:** Training may fail at runtime after hours of computation
- **Priority:** Medium

### SFT Training Loop
- **What's not tested:** Full training run; chat template application
- **Files:** `src/sft/train.py`
- **Risk:** Training may produce invalid model
- **Priority:** Medium

---

*Concerns audit: 2026-02-18*
