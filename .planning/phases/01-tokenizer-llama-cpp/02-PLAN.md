---
phase: 01
plan: 02
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [TOK-01, TOK-02, TOK-04]
requirements_addressed: [TOK-01, TOK-02, TOK-04]
files_modified:
  - tsc_cycle/tokenizer_check.py
  - tsc_cycle/v3_gates/tokenizer_audit_v3.py
  - tests/test_tokenizer_check.py
---

<objective>
把 tokenizer 硬门禁从 v1.0 的 4B/硬编码 native think IDs 升级为 Qwen3.5 动态审计：4 个自定义标签均拆成 ≥3 sub-tokens，native `<think>`/`</think>` ID 动态写入 `tokenizer_audit.json`，并为后续数据组装提供禁止 native think 泄漏的动态检查。
</objective>

<threat_model>
- T-04 HIGH: 继续硬编码 v1.0 token IDs 会让 Qwen3.5 训练数据泄漏检测失真。Mitigation: native think IDs 只能来自当前 tokenizer encode 结果和审计 JSON。
- T-05 HIGH: 自定义标签被注册为 special token 或 BPE 合并过短会削弱训练格式学习。Mitigation: `min_custom_subtokens=3` 是硬断言。
- T-06 MEDIUM: chat_template 注入 native `<think>`。Mitigation: tokenizer audit 明确记录 `chat_template_used=false`，数据组装继续使用 raw text tags。
</threat_model>

<must_haves>
<truths>
- TOK-01: `<start_working_out>`, `<end_working_out>`, `<SOLUTION>`, `</SOLUTION>` 在 Qwen3.5 tokenizer 下每个都必须有至少 3 个 sub-token。
- TOK-02: native `<think>` / `</think>` token IDs 必须动态查表并写入 `tokenizer_audit.json`；禁止使用 v1.0 固定值作为真值。
- TOK-04: 训练数据组装必须继续绕开 chat_template，使用 raw text 的自定义 tags。
</truths>
</must_haves>

<tasks>
<task id="02-01" type="execute">
<read_first>
- `tsc_cycle/tokenizer_check.py` — 当前 v1.0 hardcoded implementation。
- `tsc_cycle/prompt_builder.py` — custom tag single source of truth。
- `tsc_cycle/student/dataset.py` — native think ID leakage check caller。
</read_first>
<action>
Refactor `tsc_cycle/tokenizer_check.py` to remove hardcoded Qwen3-4B truth constants as validation requirements:
1. Keep `CUSTOM_TAGS` imported from `prompt_builder.py`.
2. Add `NATIVE_THINK_TAGS = ("<think>", "</think>")`.
3. Add `MIN_CUSTOM_TAG_SUBTOKENS = 3`.
4. Implement `lookup_native_think_ids(tokenizer) -> dict[str, list[int]]` that returns current tokenizer encodings for `<think>` and `</think>` with `add_special_tokens=False`.
5. Implement `native_think_token_ids(tokenizer) -> set[int]` that returns only IDs for native tags whose encoding length is 1.
6. Update `check_tokenizer(tokenizer, min_custom_subtokens=MIN_CUSTOM_TAG_SUBTOKENS)` so each custom tag with fewer than 3 IDs is added to `bad_custom_tags`.
7. Update details to include keys exactly: `custom_tags`, `native_think`, `vocab_size`, `min_custom_subtokens`, `bad_custom_tags`, `bad_native_think`.
8. `bad_native_think` should flag native tags that are not single-token, but must not compare against 151667/151668.
9. Update `assert_no_native_think_in_ids` to accept optional `native_ids` and no longer depend on module-level hardcoded constants.
</action>
<verify>
`.venv/bin/python -m py_compile tsc_cycle/tokenizer_check.py`
</verify>
<acceptance_criteria>
- `tsc_cycle/tokenizer_check.py` contains `MIN_CUSTOM_TAG_SUBTOKENS = 3`.
- `tsc_cycle/tokenizer_check.py` contains `lookup_native_think_ids`.
- `tsc_cycle/tokenizer_check.py` does not contain `NATIVE_THINK_OPEN_ID = 151667`.
- `tsc_cycle/tokenizer_check.py` does not contain `NATIVE_THINK_CLOSE_ID = 151668`.
- `tsc_cycle/tokenizer_check.py` contains `min_custom_subtokens` in details.
</acceptance_criteria>
</task>

<task id="02-02" type="execute">
<read_first>
- `tsc_cycle/tokenizer_check.py` — helper functions from task 02-01.
- `tsc_cycle/prompt_builder.py` — raw custom tags.
</read_first>
<action>
Create `tsc_cycle/v3_gates/tokenizer_audit_v3.py` with argparse options:
- `--model`, default exactly `Qwen/Qwen3.5-9B`
- `--out`, default exactly `artifacts/v3/phase1/tokenizer_audit.json`

The CLI must:
1. load tokenizer via `AutoTokenizer.from_pretrained(args.model)`;
2. call `check_tokenizer(tokenizer, min_custom_subtokens=3)`;
3. write JSON with keys exactly: `ok`, `model`, `vocab_size`, `custom_tags`, `native_think`, `min_custom_subtokens`, `chat_template_used`, `bad_custom_tags`, `bad_native_think`, `error`;
4. set `chat_template_used` to `false` because TSC-CYCLE uses raw `build_user_prompt`/`build_full_assistant` text and not tokenizer chat templates;
5. exit nonzero if `ok` is false.
</action>
<verify>
`.venv/bin/python -m py_compile tsc_cycle/v3_gates/tokenizer_audit_v3.py`
</verify>
<acceptance_criteria>
- `tsc_cycle/v3_gates/tokenizer_audit_v3.py` contains `Qwen/Qwen3.5-9B`.
- `tsc_cycle/v3_gates/tokenizer_audit_v3.py` contains `artifacts/v3/phase1/tokenizer_audit.json`.
- `tsc_cycle/v3_gates/tokenizer_audit_v3.py` contains `chat_template_used`.
- `tsc_cycle/v3_gates/tokenizer_audit_v3.py` exits nonzero when tokenizer check fails.
</acceptance_criteria>
</task>

<task id="02-03" type="execute">
<read_first>
- `tests/test_prompt_builder.py` — pytest style.
- `tsc_cycle/tokenizer_check.py` — refactored helper API.
</read_first>
<action>
Create `tests/test_tokenizer_check.py` using a fake tokenizer class with `encode(text, add_special_tokens=False)` and `__len__` methods. Tests must verify:
1. a custom tag with 2 ids fails when `min_custom_subtokens=3`;
2. native `<think>` and `</think>` single-token dynamic IDs are reported in `details["native_think"]` without comparing to 151667/151668;
3. `assert_no_native_think_in_ids([1, 2, 3], native_ids={99, 100})` passes;
4. `assert_no_native_think_in_ids([1, 99], native_ids={99, 100})` raises `AssertionError`.
</action>
<verify>
`.venv/bin/python -m pytest tests/test_tokenizer_check.py`
</verify>
<acceptance_criteria>
- `tests/test_tokenizer_check.py` contains `min_custom_subtokens=3`.
- `tests/test_tokenizer_check.py` contains `native_ids={99, 100}`.
- `.venv/bin/python -m pytest tests/test_tokenizer_check.py` exits 0.
</acceptance_criteria>
</task>
</tasks>

<verification>
- `.venv/bin/python -m pytest tests/test_tokenizer_check.py`
- `.venv/bin/python -m py_compile tsc_cycle/tokenizer_check.py tsc_cycle/v3_gates/tokenizer_audit_v3.py`
- Phase gate command: `.venv/bin/python -m tsc_cycle.v3_gates.tokenizer_audit_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_audit.json`
</verification>

<success_criteria>
- `tokenizer_audit.json` contains dynamic Qwen3.5 native think IDs and no v1.0 hardcoded expectation.
- All four custom tags have at least 3 sub-token IDs.
- Downstream code has a dynamic API to reject native think IDs without relying on 151667/151668 constants.
</success_criteria>
