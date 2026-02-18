# Testing Patterns

**Analysis Date:** 2026-02-18

## Test Framework

**Runner:**
- No dedicated test framework (no pytest, unittest, or jest configuration)
- Tests are manual verification scripts: `src/grpo/test_rewards.py`, `src/sft/test_inference.py`
- Tests run via Python module execution

**Assertion Library:**
- Python built-in `assert` statements
- Custom validation functions for distribution quality

**Run Commands:**
```bash
# Test reward functions
python -m src.grpo.test_rewards --config config/config.json

# Test reward distribution with SUMO validation
python -m src.grpo.test_rewards --sumo-validate --sample-size 100

# Test SFT inference
python -m src.sft.test_inference 3  # test 3 samples
```

## Test File Organization

**Location:**
- Tests are co-located with the modules they test
- Pattern: `src/<module>/test_<component>.py`

**Naming:**
- Test files: `test_*.py` prefix
- No test class naming convention (tests are procedural scripts)

**Structure:**
```
src/
├── grpo/
│   ├── rewards.py          # Implementation
│   └── test_rewards.py     # Co-located test
├── sft/
│   ├── train.py            # Implementation
│   └── test_inference.py   # Co-located test
```

## Test Structure

**Suite Organization:**
```python
# src/grpo/test_rewards.py - Procedural test script pattern

# Test fixtures (module-level)
test_completions = [
    [{"content": "...format correct..."}],
    [{"content": "...format error..."}],
]

test_prompts = [
    [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
]

def run_format_tests(config_path, baseline_path):
    """Run all format tests and print results."""
    init_rewards(config_path, baseline_path)

    print("Testing match_format_exactly")
    scores = match_format_exactly(test_completions)
    for i, (completion, score) in enumerate(zip(test_completions, scores)):
        print(f"Test {i+1}: score={score}")
```

**Patterns:**
- Setup: Call `init_rewards()` to initialize module state
- Execution: Call function under test with fixture data
- Verification: Print results for manual inspection
- No teardown (tests are stateless)

## Mocking

**Framework:** None - no mocking library detected

**Patterns:**
- Tests use real function implementations
- External dependencies (SUMO) are optionally invoked:
```python
parser.add_argument("--sumo-validate", action="store_true",
                    help="Run SUMO distribution validation (requires SUMO environment)")
```

**What to Test Without Mocking:**
- Format matching functions: `match_format_exactly()`, `match_format_approximately()`
- Constraint checking: `check_constraints()`
- Think length reward: `think_length_reward()`

**What Requires External Resources:**
- SUMO simulation: Requires SUMO_HOME environment and scenario files
- Model inference: Requires trained model at `outputs/sft/model`

## Fixtures and Factories

**Test Data:**
```python
# Inline fixture definitions
test_completions = [
    # Format correct
    [{"content": "analysis<end_working_out><SOLUTION>[{\"phase_id\": 0, \"final\": 119}]</SOLUTION>"}],
    # Format error: missing <end_working_out>
    [{"content": "analysis<SOLUTION>[{\"phase_id\": 0, \"final\": 119}]</SOLUTION>"}],
]
```

**Location:**
- Fixtures defined inline in test files
- No shared fixture files or factories

**Data Generation for Tests:**
```python
# Generate valid completion for constraint testing
phases = [{"phase_id": p["phase_id"], "final": p["min_green"]} for p in phase_waits]
completion_text = f"<end_working_out><SOLUTION>{json.dumps(phases)}</SOLUTION>"
```

## Coverage

**Requirements:** None enforced

**Coverage Approach:**
- Manual verification of key functions
- Distribution quality checks for SUMO rewards:
```python
def check_distribution_quality(scores):
    """Check if distribution meets requirements."""
    std = statistics.stdev(scores)
    if std < 0.5:
        return False, ["Standard deviation too low"]

    unique_count = len(set(scores))
    if unique_count < len(scores) * 0.3:
        return False, ["Not enough unique values"]

    return True, []
```

## Test Types

**Unit Tests:**
- Format matching functions
- Constraint validation
- Think length calculation
- Pattern: Direct function call with fixture data

**Integration Tests:**
- SUMO reward validation (optional, requires environment)
- SFT inference test (requires trained model)

**E2E Tests:**
- Not present in current test suite
- Pipeline testing done via shell scripts: `docker/grpo_pipeline.sh`

## Common Patterns

**Async Testing:**
- Not applicable (no async code in test suite)

**Error Testing:**
```python
# Test handles missing/invalid data gracefully
def check_constraints(prompts, completions, **kwargs):
    for prompt, completion in zip(prompts, completions):
        match = match_format.search(response)
        if not match:
            scores.append(-2.0)  # Error indicator
            continue

        try:
            plan = json.loads(match.group(1))
        except:
            scores.append(-2.0)  # Parse failure
            continue
```

**Parameterized Testing:**
```python
# Manual parameterization via loop
for i, (prompt, completion, score) in enumerate(zip(test_prompts, test_completions, scores)):
    print(f"Test {i+1}: score={score}")
```

## Test Data Files

**Training Data:**
- `outputs/sft/sft_train.jsonl` - SFT training samples
- `outputs/grpo/grpo_train.jsonl` - GRPO training samples
- `outputs/grpo/baseline.json` - SUMO baseline metrics

**Sample Selection for Testing:**
```python
# Stratified sampling from training data
samples_by_scenario = {}
for sample in all_samples:
    scenario = sample["metadata"]["state_file"].split('/')[2]
    samples_by_scenario[scenario] = samples_by_scenario.get(scenario, [])
    samples_by_scenario[scenario].append(sample)

# Proportional sampling
for scenario, samples in samples_by_scenario.items():
    scenario_sample_size = max(1, int(sample_size * len(samples) / total_samples))
    selected_samples.extend(random.sample(samples, scenario_sample_size))
```

## Validation Scripts

**Reward Distribution Validation:**
```bash
# Run before GRPO training
python -m src.grpo.test_rewards --sumo-validate --sample-size 100

# Checks:
# 1. Standard deviation >= 0.5
# 2. Unique values >= 30% of samples
# 3. Non-zero ratio >= 50%
```

**Inference Test:**
```bash
# Test trained model output format
python -m src.sft.test_inference 5  # test 5 random samples

# Checks:
# 1. <end_working_out> appears exactly 1 time
# 2. <SOLUTION> appears exactly 1 time
# 3. </SOLUTION> appears exactly 1 time
# 4. Regex format matches
```

## Shell Script Testing

**Training Pipeline Tests:**
- `docker/grpo_train.sh` includes reward validation step:
```bash
if [ "$SKIP_VALIDATE" = "false" ]; then
    echo "[验证] Running reward distribution validation..."
    python -m src.grpo.test_rewards --sumo-validate --sample-size 50

    if [ $? -ne 0 ]; then
        echo "[错误] Reward distribution validation failed!"
        exit 1
    fi
fi
```

---

*Testing analysis: 2026-02-18*
