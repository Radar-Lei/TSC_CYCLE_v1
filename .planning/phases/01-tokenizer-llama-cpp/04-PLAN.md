---
phase: 01
plan: 04
type: execute
wave: 2
depends_on: [01]
autonomous: true
requirements: [MEM-01, MEM-02, ENV-03]
requirements_addressed: [MEM-01, MEM-02, ENV-03]
files_modified:
  - tsc_cycle/v3_gates/memory_budget_v3.py
  - tests/test_v3_memory_budget.py
---

<objective>
实现 Qwen3.5-9B 显存预算实测门禁：对 max_seq_length ∈ {1536, 2048, 2560, 3072, 4096} 全量实测 peak memory，选择 peak<85GB 的最大值，并用该值完成 100-step dry-run under 100GB cap。
</objective>

<threat_model>
- T-10 HIGH: 用估算代替实测会让 Phase 4 全量训练 OOM。Mitigation: 五个指定 seq 候选必须逐一实际运行并记录 CUDA peak。
- T-11 HIGH: GPU dry-run 不在 MemoryMax=100G scope 中运行会导致整机卡死风险。Mitigation: 计划验收要求 run command 只通过 `scripts/dgx_spark/run_safe.sh 100G --`。
- T-12 MEDIUM: OOM 后 CUDA 状态污染后续候选。Mitigation: 每个 candidate 支持独立 subprocess 模式或显式释放模型、empty_cache、记录失败并继续下一个候选。
</threat_model>

<must_haves>
<truths>
- MEM-01: 必须实测 1536、2048、2560、3072、4096 五个候选，不允许外推。
- MEM-02: 9B + r=64 LoRA + bs=1 + grad_ckpt(use_reentrant=False) 必须能在 100GB cap 内训练 100 steps。
- ENV-03: 所有长 GPU 训练/显存 gate 必须在 `MemoryMax=100G MemorySwapMax=0` 下执行。
</truths>
</must_haves>

<tasks>
<task id="04-01" type="execute">
<read_first>
- `tsc_cycle/student/train.py` — model, LoRA, gradient checkpointing, Trainer setup patterns。
- `scripts/dgx_spark/run_safe.sh` — memory scope wrapper。
- `.planning/phases/01-tokenizer-llama-cpp/01-VALIDATION.md` — validation commands and artifacts。
</read_first>
<action>
Create `tsc_cycle/v3_gates/memory_budget_v3.py` with argparse options:
- `--model`, default `Qwen/Qwen3.5-9B`
- `--seqs`, nargs `+`, type int, default exactly `1536 2048 2560 3072 4096`
- `--seq`, optional single int for dry-run mode
- `--steps`, type int, default `1`
- `--out`, default `artifacts/v3/phase1/memory_budget.json`
- `--batch-size`, default `1`
- `--grad-accum`, default `16`
- `--lora-r`, default `64`
- `--lora-alpha`, default `64`

Implement the module so each candidate run:
1. loads tokenizer/model with Qwen3.5-9B, bnb NF4, bf16, SDPA, device_map `{"": 0}`;
2. calls `prepare_model_for_kbit_training(... gradient_checkpointing_kwargs={"use_reentrant": False})`;
3. creates `LoraConfig(r=64, lora_alpha=64, lora_dropout=0.0, bias="none", target_modules="all-linear", task_type="CAUSAL_LM")`;
4. constructs a synthetic batch of length exactly `seq` with labels equal to input ids except prompt-masked positions may be omitted for the memory gate;
5. runs forward/backward/optimizer for `steps`, using bs=1 and gradient accumulation 16 when `steps >= 16`;
6. records `peak_allocated_gb`, `peak_reserved_gb`, `elapsed_sec`, `status`, and `error`;
7. selects `selected_max_seq` as largest candidate with `status == "ok"` and `peak_reserved_gb < 85.0`.

If `--seq` is provided, run only that sequence and write a dry-run style artifact with `selected_max_seq` equal to that seq when successful.
</action>
<verify>
`.venv/bin/python -m py_compile tsc_cycle/v3_gates/memory_budget_v3.py`
</verify>
<acceptance_criteria>
- `tsc_cycle/v3_gates/memory_budget_v3.py` contains `1536` and `4096`.
- `tsc_cycle/v3_gates/memory_budget_v3.py` contains `target_modules="all-linear"`.
- `tsc_cycle/v3_gates/memory_budget_v3.py` contains `use_reentrant` and `False`.
- `tsc_cycle/v3_gates/memory_budget_v3.py` contains `peak_reserved_gb < 85.0` or equivalent threshold.
- `tsc_cycle/v3_gates/memory_budget_v3.py` contains `Qwen/Qwen3.5-9B`.
</acceptance_criteria>
</task>

<task id="04-02" type="execute">
<read_first>
- `tsc_cycle/v3_gates/memory_budget_v3.py` — selection helpers.
</read_first>
<action>
Create `tests/test_v3_memory_budget.py` for pure helper logic:
1. test selected_max_seq chooses 3072 from candidates where 4096 has peak 90.0GB and 3072 has peak 84.9GB;
2. test selected_max_seq returns `None` when all candidates fail or exceed 85GB;
3. test default seq list is exactly `[1536, 2048, 2560, 3072, 4096]`.
If helper functions do not exist after task 04-01, add `select_max_seq(results, threshold_gb=85.0)` and `default_seqs()`.
</action>
<verify>
`.venv/bin/python -m pytest tests/test_v3_memory_budget.py`
</verify>
<acceptance_criteria>
- `tests/test_v3_memory_budget.py` contains `[1536, 2048, 2560, 3072, 4096]`.
- `tests/test_v3_memory_budget.py` contains `84.9` and `90.0`.
- `.venv/bin/python -m pytest tests/test_v3_memory_budget.py` exits 0.
</acceptance_criteria>
</task>
</tasks>

<verification>
- `.venv/bin/python -m pytest tests/test_v3_memory_budget.py`
- `.venv/bin/python -m py_compile tsc_cycle/v3_gates/memory_budget_v3.py`
- Long gate sweep: `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3 --model Qwen/Qwen3.5-9B --seqs 1536 2048 2560 3072 4096 --out artifacts/v3/phase1/memory_budget.json`
- Long 100-step gate: `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3 --model Qwen/Qwen3.5-9B --seq $(jq -r .selected_max_seq artifacts/v3/phase1/memory_budget.json) --steps 100 --out artifacts/v3/phase1/train_100step.json`
</verification>

<success_criteria>
- `memory_budget.json` records all five required seq candidates.
- `memory_budget.json` contains a non-null `selected_max_seq` whose peak reserved memory is `<85GB`.
- `train_100step.json` reports successful 100-step execution under the 100GB wrapper.
</success_criteria>
