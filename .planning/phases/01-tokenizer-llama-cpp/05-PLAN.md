---
phase: 01
plan: 05
type: execute
wave: 3
depends_on: [01, 02, 03, 04]
autonomous: true
requirements: [ENV-02, ENV-03, TOK-03]
requirements_addressed: [ENV-02, ENV-03, TOK-03]
files_modified:
  - tsc_cycle/v3_gates/gguf_microconvert_v3.py
  - tsc_cycle/v3_gates/phase1_report.py
  - scripts/run_v3_phase1_gates.sh
  - tests/test_v3_phase1_report.py
---

<objective>
实现 Phase 1 的 llama.cpp micro-convert 硬门禁与总控报告：验证 `/home/samuel/projects/EvoProgTSC/llama.cpp` 的 convert/quantize/llama-cli/llama-tokenize 链路，并将所有 Phase 1 gate artifact 汇总为一个 fatal pass/fail report。
</objective>

<threat_model>
- T-13 HIGH: llama.cpp 路径或二进制错误会让 Phase 5 才发现导出不可用。Mitigation: Phase 1 提前验证 mandated EvoProgTSC llama.cpp 路径。
- T-14 HIGH: 某个 gate 失败但总控脚本继续执行 Phase 2 会浪费教师标注/GPU 成本。Mitigation: `phase1_report.py` 和 shell runner 必须 fail closed。
- T-15 MEDIUM: artifact 路径混入 v1.0 run。Mitigation: 所有 Phase 1 输出限定到 `artifacts/v3/phase1/` 或 `runs/v3.0-gates/`。
</threat_model>

<must_haves>
<truths>
- ENV-02: 本机 `/home/samuel/projects/EvoProgTSC/llama.cpp` micro-convert dry-run 必须完成 dummy LoRA/HF → GGUF → q4_K_M → `llama-cli` 5-token inference。
- ENV-03: micro-convert 中可能加载 9B 的步骤必须通过 `run_safe.sh 100G` 执行。
- TOK-03: Phase 1 总报告必须包含 tokenizer parity artifact 的 100/100 结论。
</truths>
</must_haves>

<tasks>
<task id="05-01" type="execute">
<read_first>
- `tsc_cycle/student/export_gguf.py` — llama.cpp convert/quantize subprocess pattern。
- `tsc_cycle/student/parity_gguf.py` — llama.cpp binary path and process cleanup style。
- `.planning/phases/01-tokenizer-llama-cpp/01-RESEARCH.md` — micro-convert expected outputs。
</read_first>
<action>
Create `tsc_cycle/v3_gates/gguf_microconvert_v3.py` with argparse options:
- `--model`, default `Qwen/Qwen3.5-9B`
- `--llama-cpp`, default `/home/samuel/projects/EvoProgTSC/llama.cpp`
- `--out`, default `runs/v3.0-gates/gguf_microconvert`
- `--n-predict`, default `5`

The CLI must:
1. verify these paths exist under `--llama-cpp`: `convert_hf_to_gguf.py`, `llama-quantize`, `llama-cli`; if `llama-tokenize` exists, record it too;
2. create output dirs only under `runs/v3.0-gates/gguf_microconvert` by default;
3. run a documented micro-convert path that exercises `convert_hf_to_gguf.py` and `llama-quantize Q4_K_M`; if a true dummy LoRA merge is implemented, write adapter/merge dirs under the out path; if the implementation uses a minimal HF tokenizer/model fixture, record `micro_fixture_type` in JSON;
4. run `llama-cli -m <q4_gguf> -n 5 -p "<start_working_out>smoke"`;
5. write `gguf_microconvert.json` with keys exactly: `ok`, `model`, `llama_cpp`, `convert`, `quantize`, `llama_cli`, `llama_tokenize`, `bf16_or_fp16_gguf`, `q4_gguf`, `commands`, `inference_tail`, `error`.
Exit nonzero unless all required commands return 0 and the q4 GGUF exists.
</action>
<verify>
`.venv/bin/python -m py_compile tsc_cycle/v3_gates/gguf_microconvert_v3.py`
</verify>
<acceptance_criteria>
- `tsc_cycle/v3_gates/gguf_microconvert_v3.py` contains `/home/samuel/projects/EvoProgTSC/llama.cpp`.
- `tsc_cycle/v3_gates/gguf_microconvert_v3.py` contains `convert_hf_to_gguf.py`.
- `tsc_cycle/v3_gates/gguf_microconvert_v3.py` contains `llama-quantize` and `Q4_K_M`.
- `tsc_cycle/v3_gates/gguf_microconvert_v3.py` contains `llama-cli` and `-n`.
- `tsc_cycle/v3_gates/gguf_microconvert_v3.py` writes `gguf_microconvert.json`.
</acceptance_criteria>
</task>

<task id="05-02" type="execute">
<read_first>
- `.planning/phases/01-tokenizer-llama-cpp/01-VALIDATION.md` — required artifact list。
- `tsc_cycle/eval/decision.py` — JSON decision/report style.
</read_first>
<action>
Create `tsc_cycle/v3_gates/phase1_report.py` with argparse options:
- `--artifacts`, default `artifacts/v3/phase1`
- `--gguf-report`, default `runs/v3.0-gates/gguf_microconvert/gguf_microconvert.json`
- `--out`, default `artifacts/v3/phase1/phase1_gate_report.json`

The report must read:
- `env_smoke.json`
- `tokenizer_audit.json`
- `tokenizer_parity.json`
- `memory_budget.json`
- `train_100step.json`
- `gguf_microconvert.json`

Apply exact pass rules:
1. env passes when `ok == true` and `vision_param_count == 0`;
2. tokenizer audit passes when `ok == true` and every custom tag length is `>=3`;
3. tokenizer parity passes when `ok == true`, `matched == 100`, `mismatched == 0`, `parse_failed == 0`;
4. memory budget passes when `selected_max_seq` is non-null and selected peak is `<85.0`;
5. train 100-step passes when `ok == true` or `status == "ok"` and `steps >= 100`;
6. gguf micro-convert passes when `ok == true` and `q4_gguf` path exists.

Write JSON with keys exactly: `ok`, `fatal_failures`, `warnings`, `gates`, `requirements_covered`, `next_phase_allowed`. `next_phase_allowed` must equal `ok`.
Exit nonzero if `ok` is false.
</action>
<verify>
`.venv/bin/python -m py_compile tsc_cycle/v3_gates/phase1_report.py`
</verify>
<acceptance_criteria>
- `tsc_cycle/v3_gates/phase1_report.py` contains `next_phase_allowed`.
- `tsc_cycle/v3_gates/phase1_report.py` contains `matched == 100` or equivalent exact parity check.
- `tsc_cycle/v3_gates/phase1_report.py` contains `vision_param_count`.
- `tsc_cycle/v3_gates/phase1_report.py` contains `selected_max_seq` and `85.0`.
</acceptance_criteria>
</task>

<task id="05-03" type="execute">
<read_first>
- `scripts/run_pipeline.sh` — local shell orchestration style。
- `scripts/dgx_spark/run_safe.sh` — long gate wrapper。
- `tsc_cycle/v3_gates/phase1_report.py` — final aggregation command。
</read_first>
<action>
Create executable shell script `scripts/run_v3_phase1_gates.sh` with `set -euo pipefail`. The script must run, in this exact order:
1. `source scripts/dgx_spark/env.sh`
2. `python scripts/dgx_spark/verify.py`
3. `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.env_smoke_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/env_smoke.json`
4. `python -m tsc_cycle.v3_gates.tokenizer_audit_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_audit.json`
5. `python -m tsc_cycle.v3_gates.tokenizer_parity_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/tokenizer_parity.json`
6. `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3 --model Qwen/Qwen3.5-9B --seqs 1536 2048 2560 3072 4096 --out artifacts/v3/phase1/memory_budget.json`
7. `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3 --model Qwen/Qwen3.5-9B --seq $(python -c 'import json; print(json.load(open("artifacts/v3/phase1/memory_budget.json"))["selected_max_seq"])') --steps 100 --out artifacts/v3/phase1/train_100step.json`
8. `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.gguf_microconvert_v3 --model Qwen/Qwen3.5-9B --out runs/v3.0-gates/gguf_microconvert`
9. `python -m tsc_cycle.v3_gates.phase1_report --artifacts artifacts/v3/phase1 --out artifacts/v3/phase1/phase1_gate_report.json`
</action>
<verify>
`bash -n scripts/run_v3_phase1_gates.sh`
</verify>
<acceptance_criteria>
- `scripts/run_v3_phase1_gates.sh` contains `set -euo pipefail`.
- `scripts/run_v3_phase1_gates.sh` contains `run_safe.sh 100G -- python -m tsc_cycle.v3_gates.env_smoke_v3`.
- `scripts/run_v3_phase1_gates.sh` contains `run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3`.
- `scripts/run_v3_phase1_gates.sh` contains `python -m tsc_cycle.v3_gates.phase1_report`.
- `bash -n scripts/run_v3_phase1_gates.sh` exits 0.
</acceptance_criteria>
</task>

<task id="05-04" type="execute">
<read_first>
- `tsc_cycle/v3_gates/phase1_report.py` — pass/fail helper functions.
</read_first>
<action>
Create `tests/test_v3_phase1_report.py` with pure JSON fixture tests:
1. all gates passing yields `ok is True` and `next_phase_allowed is True`;
2. tokenizer parity `matched=99` yields `ok is False` and at least one fatal failure mentioning tokenizer parity;
3. env `vision_param_count=1` yields `ok is False`;
4. memory selected peak `85.0` fails because threshold is strictly `<85.0`.
</action>
<verify>
`.venv/bin/python -m pytest tests/test_v3_phase1_report.py`
</verify>
<acceptance_criteria>
- `tests/test_v3_phase1_report.py` contains `matched` and `99`.
- `tests/test_v3_phase1_report.py` contains `vision_param_count`.
- `tests/test_v3_phase1_report.py` contains `85.0`.
- `.venv/bin/python -m pytest tests/test_v3_phase1_report.py` exits 0.
</acceptance_criteria>
</task>
</tasks>

<verification>
- `.venv/bin/python -m pytest tests/test_v3_phase1_report.py`
- `bash -n scripts/run_v3_phase1_gates.sh`
- `.venv/bin/python -m py_compile tsc_cycle/v3_gates/gguf_microconvert_v3.py tsc_cycle/v3_gates/phase1_report.py`
- Full Phase 1 gate command: `scripts/run_v3_phase1_gates.sh`
</verification>

<success_criteria>
- `gguf_microconvert.json` proves EvoProgTSC llama.cpp convert/quantize/llama-cli chain works.
- `phase1_gate_report.json` reports `ok=true` and `next_phase_allowed=true` only when all fatal gates pass.
- The shell runner stops on first failure and never writes outside `artifacts/v3/phase1/` or `runs/v3.0-gates/` by default.
</success_criteria>
