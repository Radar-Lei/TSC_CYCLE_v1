---
phase: 01
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true
requirements: [ENV-01, ENV-03, MEM-03]
requirements_addressed: [ENV-01, ENV-03, MEM-03]
files_modified:
  - tsc_cycle/v3_gates/__init__.py
  - tsc_cycle/v3_gates/env_smoke_v3.py
  - scripts/dgx_spark/verify.py
  - tests/test_v3_env_gate.py
---

<objective>
建立 Qwen3.5-9B 环境/模型加载硬门禁：在 DGX Spark `.venv` 中用 `AutoModelForCausalLM` + bnb NF4 + SDPA 完成 1-step forward，并证明没有 vision 参数命名空间；同时让环境验证不再把 vLLM 作为本项目硬依赖。
</objective>

<threat_model>
- T-01 HIGH: 错误加载 vision/conditional-generation 架构会把后续显存预算和训练结论全部污染。Mitigation: `env_smoke_v3.py` 必须断言 `vision_param_count == 0`，并在 JSON 中记录 architecture/class。
- T-02 MEDIUM: vLLM import 失败被误判为 DGX 环境失败。Mitigation: `scripts/dgx_spark/verify.py` 对 vLLM 输出 warning/skip，不返回非零。
- T-03 HIGH: 长 GPU 任务绕过 `run_safe.sh` 导致 unified-memory OOM。Mitigation: 计划验收要求文档化且实际命令使用 `scripts/dgx_spark/run_safe.sh 100G --`。
</threat_model>

<must_haves>
<truths>
- ENV-01: `Qwen/Qwen3.5-9B` 必须以 `AutoModelForCausalLM` / Qwen3.5 causal LM 路径加载，而非 conditional generation/vision 路径。
- MEM-03: 加载后 `model.named_parameters()` 中 `vision_param_count` 必须为 0。
- ENV-03: 任何 9B GPU smoke 命令必须通过 `scripts/dgx_spark/run_safe.sh 100G --` 执行。
</truths>
</must_haves>

<tasks>
<task id="01-01" type="execute">
<read_first>
- `tsc_cycle/student/train.py` — 复用 bnb NF4、SDPA、bf16、`AutoModelForCausalLM` 加载模式。
- `scripts/dgx_spark/verify.py` — 调整本项目环境验证的 hard/warn 边界。
- `scripts/dgx_spark/run_safe.sh` — 确认 GPU gate 的 systemd memory scope 用法。
- `.planning/phases/01-tokenizer-llama-cpp/01-RESEARCH.md` — Phase 1 fatal gate 定义。
</read_first>
<action>
Create package file `tsc_cycle/v3_gates/__init__.py` and CLI module `tsc_cycle/v3_gates/env_smoke_v3.py` with argparse options:
- `--model`, default exactly `Qwen/Qwen3.5-9B`
- `--out`, default exactly `artifacts/v3/phase1/env_smoke.json`
- `--prompt`, default exactly `DGX Spark Qwen3.5 smoke test`

Implement `env_smoke_v3.py` to:
1. import `torch`, `AutoTokenizer`, `AutoModelForCausalLM`, and `BitsAndBytesConfig`;
2. construct `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)`;
3. load tokenizer and model with `AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb_cfg, attn_implementation="sdpa", torch_dtype=torch.bfloat16, device_map={"": 0})`;
4. run one `model(**tokenizer(args.prompt, return_tensors="pt").to("cuda"))` under `torch.inference_mode()`;
5. compute `vision_params = [name for name, _ in model.named_parameters() if name.startswith("vision") or ".vision" in name or "vision_tower" in name]` and fail if non-empty;
6. write JSON containing keys exactly: `ok`, `model`, `model_class`, `architectures`, `torch_version`, `torch_cuda`, `gpu_name`, `logits_shape`, `vision_param_count`, `vision_params_sample`, `attn_implementation`, `quantization`, `error`.
Return exit code 0 only when `ok is true` and `vision_param_count == 0`.
</action>
<verify>
`.venv/bin/python -m py_compile tsc_cycle/v3_gates/env_smoke_v3.py`
</verify>
<acceptance_criteria>
- `tsc_cycle/v3_gates/env_smoke_v3.py` contains `AutoModelForCausalLM.from_pretrained`.
- `tsc_cycle/v3_gates/env_smoke_v3.py` contains `attn_implementation="sdpa"`.
- `tsc_cycle/v3_gates/env_smoke_v3.py` contains `bnb_4bit_quant_type="nf4"`.
- `tsc_cycle/v3_gates/env_smoke_v3.py` contains `vision_param_count`.
- `tsc_cycle/v3_gates/env_smoke_v3.py` writes `artifacts/v3/phase1/env_smoke.json` as the default output.
</acceptance_criteria>
</task>

<task id="01-02" type="execute">
<read_first>
- `scripts/dgx_spark/verify.py` — current hard checks and imports.
- `CLAUDE.md` — project instruction that vLLM is currently unavailable.
</read_first>
<action>
Modify `scripts/dgx_spark/verify.py` so the import loop treats `vllm` as optional for this project:
- Required imports remain: `transformers`, `accelerate`, `datasets`, `peft`.
- Optional imports are: `deepspeed`, `vllm`.
- If an optional import fails, print `optional {name}: unavailable` and continue.
- If a required import fails, print `ERROR: required package {name} unavailable` and return 1.
Keep the existing upstream `flash_attn` rejection on aarch64 and `TRITON_PTXAS_PATH` hard check unchanged.
</action>
<verify>
`.venv/bin/python -m py_compile scripts/dgx_spark/verify.py`
</verify>
<acceptance_criteria>
- `scripts/dgx_spark/verify.py` contains `required_packages`.
- `scripts/dgx_spark/verify.py` contains `optional_packages`.
- `scripts/dgx_spark/verify.py` contains `optional vllm: unavailable` or equivalent formatted optional output.
- `scripts/dgx_spark/verify.py` still contains `upstream flash-attn should not be installed on DGX Spark`.
- `scripts/dgx_spark/verify.py` still contains `TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas`.
</acceptance_criteria>
</task>

<task id="01-03" type="execute">
<read_first>
- `tests/test_prompt_builder.py` — local pytest style.
- `tsc_cycle/v3_gates/env_smoke_v3.py` — module created by task 01-01.
</read_first>
<action>
Create `tests/test_v3_env_gate.py` with unit tests that do not download a model:
1. import `tsc_cycle.v3_gates.env_smoke_v3`;
2. assert its parser/default config exposes model `Qwen/Qwen3.5-9B` and out `artifacts/v3/phase1/env_smoke.json`;
3. assert the helper that counts vision parameters returns 0 for `[('model.layers.0.weight', object())]` and 2 for `[('vision.foo', object()), ('model.vision_tower.bar', object())]`.
If no helper exists after task 01-01, add `count_vision_params(named_parameters)` returning `(count, sample)`.
</action>
<verify>
`.venv/bin/python -m pytest tests/test_v3_env_gate.py`
</verify>
<acceptance_criteria>
- `tests/test_v3_env_gate.py` contains `Qwen/Qwen3.5-9B`.
- `tests/test_v3_env_gate.py` contains `vision_tower`.
- `.venv/bin/python -m pytest tests/test_v3_env_gate.py` exits 0.
</acceptance_criteria>
</task>
</tasks>

<verification>
- `.venv/bin/python -m pytest tests/test_v3_env_gate.py`
- `.venv/bin/python -m py_compile tsc_cycle/v3_gates/env_smoke_v3.py scripts/dgx_spark/verify.py`
- Long gate command to run before Phase 1 verification: `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.env_smoke_v3 --model Qwen/Qwen3.5-9B --out artifacts/v3/phase1/env_smoke.json`
</verification>

<success_criteria>
- `env_smoke_v3.py` can produce an artifact where `ok=true`, `vision_param_count=0`, and `model` is `Qwen/Qwen3.5-9B`.
- `scripts/dgx_spark/verify.py` no longer hard-fails solely because vLLM is unavailable.
- ENV-01, ENV-03, and MEM-03 are represented in executable checks.
</success_criteria>
