# Testing Patterns

**Analysis Date:** 2026-02-09

## Test Framework

**Runner:**
- Custom `if __name__ == "__main__":` test blocks within modules.
- No dedicated test runner like `pytest` or `unittest` configured at the root level.

**Assertion Library:**
- Python's built-in `assert` statement.

**Run Commands:**
```bash
python src/sft/format_validator.py      # Run self-tests for format validator
python src/sft/trainer.py               # Run self-tests for trainer module
```

## Test File Organization

**Location:**
- Co-located within the source files as `if __name__ == "__main__":` blocks.

**Naming:**
- Tests are contained within the relevant implementation file.

**Structure:**
```
src/
└── [module].py
    └── if __name__ == "__main__":
        # test cases
```

## Test Structure

**Suite Organization:**
```python
if __name__ == "__main__":
    # 自测试
    print("Testing format_validator...")

    # 测试正确格式
    valid_output = '<think>...</think>[{"phase_id": 1, "final": 40}]'
    is_valid, errors = validate_format(valid_output)
    assert is_valid, f"Should be valid: {errors}"

    # ... more cases
```

**Patterns:**
- **Setup pattern:** Manual instantiation of test data (e.g., hardcoded JSON strings).
- **Teardown pattern:** Not explicitly needed for the current functional tests.
- **Assertion pattern:** `assert condition, message_on_failure`.

## Mocking

**Framework:** Not explicitly used in the observed self-tests.

**Patterns:**
- No formal mocking pattern; tests focus on pure functions (validation) or parameter defaults (TrainingArgs).

**What to Mock:**
- Not applicable in current state.

**What NOT to Mock:**
- Not applicable in current state.

## Fixtures and Factories

**Test Data:**
```python
# Hardcoded samples in format_validator.py
valid_output = '<think>观察排队情况,相位 1 饱和度高</think>[{"phase_id": 1, "final": 40}]'
json_str = '[{"phase_id": 1, "final": 40}, {"phase_id": 2, "final": 30}]'
```

**Location:**
- Inline within the test blocks.

## Coverage

**Requirements:** None enforced.

**View Coverage:**
- Not configured.

## Test Types

**Unit Tests:**
- Functional testing of validators in `src/sft/format_validator.py`.
- Parameter validation in `src/sft/trainer.py`.

**Integration Tests:**
- The `validate_model_output` function in `src/sft/trainer.py` acts as an integration test for the model and tokenizer.

**E2E Tests:**
- `src/scripts/train_sft.py` includes a validation step at the end which serves as an E2E smoke test for the trained model.

## Common Patterns

**Async Testing:**
- Not detected.

**Error Testing:**
```python
# Testing expected failures
invalid_output = '[{"phase_id": 1, "final": 40}]'
is_valid, errors = validate_format(invalid_output)
assert not is_valid, "Should fail without think"
```

---

*Testing analysis: 2026-02-09*
