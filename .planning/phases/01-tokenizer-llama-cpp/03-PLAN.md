---
phase: 01
plan: 03
type: execute
wave: 2
depends_on: [02]
autonomous: true
requirements: [TOK-03]
requirements_addressed: [TOK-03]
files_modified:
  - tsc_cycle/v3_gates/tokenizer_parity_v3.py
  - tests/test_v3_tokenizer_parity.py
---

<objective>
实现 HF `AutoTokenizer.encode` 与本机 `/home/samuel/projects/EvoProgTSC/llama.cpp/llama-tokenize` 的 100 prompt parity 硬门禁，产出可复现 prompt fixture 和 mismatch 诊断。
</objective>

<threat_model>
- T-07 HIGH: GGUF tokenizer 与 HF tokenizer 不一致会导致部署端 prompt/tag 解码错位。Mitigation: 100/100 exact ID parity 是硬门禁。
- T-08 MEDIUM: llama-tokenize CLI 输出格式随版本变化导致误解析。Mitigation: parser 必须在无法提取 ID 时 fail closed，并把 stderr/stdout tail 写入诊断。
- T-09 MEDIUM: parity prompt 覆盖不足。Mitigation: 固定 100 prompt，混合 v1 数据、OOD 数据和 synthetic boundary prompt。
</threat_model>

<must_haves>
<truths>
- TOK-03: HF `AutoTokenizer.encode(..., add_special_tokens=False)` 与 `llama-tokenize` 在 100 个测试 prompt 上必须 100% parity。
- Tokenizer parity fixture 必须确定性落盘，后续 Phase 5 可复用同一批 prompt。
</truths>
</must_haves>

<tasks>
<task id="03-01" type="execute">
<read_first>
- `tsc_cycle/student/parity_prompts.py` — deterministic sample selection pattern。
- `tsc_cycle/student/tokenize_sanity.py` — GGUF tokenizer diagnostic style。
- `tsc_cycle/prompt_builder.py` — prompt construction source of truth。
- `.planning/phases/01-tokenizer-llama-cpp/01-RESEARCH.md` — llama-tokenize caveat。
</read_first>
<action>
Create `tsc_cycle/v3_gates/tokenizer_parity_v3.py` with argparse options:
- `--model`, default `Qwen/Qwen3.5-9B`
- `--labeled`, default `data/labeled.jsonl`
- `--ood-inputs`, default `data/ood_inputs.jsonl`
- `--prompt-fixture`, default `artifacts/v3/phase1/tokenizer_parity_prompts.jsonl`
- `--llama-tokenize`, default `/home/samuel/projects/EvoProgTSC/llama.cpp/llama-tokenize`
- `--gguf`, default empty string; when llama-tokenize requires `-m`, caller supplies Phase 1 micro-converted GGUF
- `--out`, default `artifacts/v3/phase1/tokenizer_parity.json`
- `--n`, default `100`
- `--seed`, default `42`

Implement deterministic fixture generation:
1. read valid records from `data/labeled.jsonl` and build prompt text via `build_user_prompt(record["input"])`;
2. include OOD inputs from `data/ood_inputs.jsonl` if available by wrapping each line as prompt input;
3. add synthetic boundary prompts with min_green<15, max_green>120, and 1/2/4/8 phase counts until at least 100 candidates exist;
4. sort candidates by stable id and sample exactly 100 with `random.Random(42)`;
5. write JSONL rows with keys `prompt_id`, `source`, `text`.

Implement parity check:
1. HF IDs = `tokenizer.encode(text, add_special_tokens=False)`;
2. llama IDs = parsed output from invoking llama-tokenize for the same text;
3. support command shapes with and without `-m args.gguf`: if `--gguf` is non-empty, call `[llama-tokenize, "-m", gguf, text]`; otherwise call `[llama-tokenize, text]`;
4. parse integer token IDs robustly from stdout lines; if no IDs are found, mark parse failure;
5. write JSON with `ok`, `n`, `matched`, `mismatched`, `parse_failed`, `fixture`, `llama_tokenize`, `gguf`, and `results`.
Exit nonzero unless `matched == n` and `parse_failed == 0`.
</action>
<verify>
`.venv/bin/python -m py_compile tsc_cycle/v3_gates/tokenizer_parity_v3.py`
</verify>
<acceptance_criteria>
- `tsc_cycle/v3_gates/tokenizer_parity_v3.py` contains `tokenizer_parity_prompts.jsonl`.
- `tsc_cycle/v3_gates/tokenizer_parity_v3.py` contains `/home/samuel/projects/EvoProgTSC/llama.cpp/llama-tokenize`.
- `tsc_cycle/v3_gates/tokenizer_parity_v3.py` contains `matched == args.n` or equivalent exact 100% pass condition.
- `tsc_cycle/v3_gates/tokenizer_parity_v3.py` writes mismatch diagnostics including first differing index or parse failure details.
</acceptance_criteria>
</task>

<task id="03-02" type="execute">
<read_first>
- `tsc_cycle/v3_gates/tokenizer_parity_v3.py` — fixture and parser functions.
- `tests/test_hashing.py` — deterministic testing style.
</read_first>
<action>
Create `tests/test_v3_tokenizer_parity.py` with no external model/binary dependency. Tests must cover:
1. deterministic prompt selection returns the same ordered `prompt_id` list for seed 42 twice;
2. synthetic boundary prompt generation includes text containing `min_green` and `max_green`;
3. llama-tokenize parser extracts IDs from a representative stdout string like `0 -> 123` and `token 1: 456`;
4. parser returns empty list or raises a controlled parse error on stdout with no integers.
</action>
<verify>
`.venv/bin/python -m pytest tests/test_v3_tokenizer_parity.py`
</verify>
<acceptance_criteria>
- `tests/test_v3_tokenizer_parity.py` contains `seed=42`.
- `tests/test_v3_tokenizer_parity.py` contains `min_green` and `max_green`.
- `.venv/bin/python -m pytest tests/test_v3_tokenizer_parity.py` exits 0.
</acceptance_criteria>
</task>
</tasks>

<verification>
- `.venv/bin/python -m pytest tests/test_v3_tokenizer_parity.py`
- `.venv/bin/python -m py_compile tsc_cycle/v3_gates/tokenizer_parity_v3.py`
- Phase gate command after llama-tokenize syntax is verified: `.venv/bin/python -m tsc_cycle.v3_gates.tokenizer_parity_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_parity.json`
</verification>

<success_criteria>
- `artifacts/v3/phase1/tokenizer_parity_prompts.jsonl` contains exactly 100 deterministic prompts.
- `artifacts/v3/phase1/tokenizer_parity.json` reports `ok=true`, `matched=100`, `mismatched=0`, `parse_failed=0`.
</success_criteria>
