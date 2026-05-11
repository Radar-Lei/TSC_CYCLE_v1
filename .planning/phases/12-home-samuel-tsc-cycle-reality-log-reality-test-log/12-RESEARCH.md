# Phase 12: home-samuel-tsc-cycle-reality-log-reality-test-log - Research

**Researched:** 2026-05-11  
**Domain:** reality.log 输入重放、GGUF q4_K_M 本地推理、协议解析与硬约束验证  
**Confidence:** HIGH

## User Constraints (from CONTEXT.md)

### Locked Decisions

## Phase Boundary

Use the latest trained/deployed v4.0 model artifact as the inference source, read input cases from `/home/samuel/TSC_CYCLE/reality.log`, ignore any existing outputs in that log, and generate a new `reality_test.log` whose outputs are produced by the project model and include the explicit reasoning protocol.

The phase must preserve the established protocol `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` and must not use native `<think>` / `</think>` tags. The preferred deployment artifact from Phase 11 is `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` unless planning finds a stronger current handoff artifact.

### Claude's Discretion

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, Phase 11 GO decision, current codebase conventions, and existing generation/evaluation wrappers to guide decisions.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

## Project Constraints (from CLAUDE.md)

- 用户可见回复与文档必须使用简体中文。[CITED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Git commit message 不得包含 `Co-Authored-By` 行。[CITED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 本机是 DGX Spark，暂时不能使用 vLLM。[CITED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 学生模型目标是 Qwen3-4B-Thinking-2507 蒸馏后的本地 GGUF 推理模型，输出需要显式思考过程。[CITED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 硬约束核心价值是 OOD/真实输入上仍满足 `min_green ≤ final ≤ max_green`、整数秒、相位顺序、覆盖全相位。[CITED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 全链路协议固定为 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`，禁止原生 `<think>`/`</think>`。[CITED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 训练/推理相关工作应遵循 DGX Spark 约束：不用 flash-attn cu12，不用 vLLM，优先复用已知可用环境与安全运行包装。[CITED: /home/samuel/TSC_CYCLE/CLAUDE.md]

## Summary

Phase 12 应实现为一个可重复运行的轻量 CLI/脚本，而不是一次性手工生成文件：从 `/home/samuel/TSC_CYCLE/reality.log` 只提取 `type=prompt` 块中的 `【cycle_predict_input_json】...【/cycle_predict_input_json】` JSON 输入，完全忽略旧 `type=result` 块、旧 `RAW/REASONING/PARSED` 输出，再用 Phase 11 GO 推荐的 v4 q4_K_M GGUF 产物生成新的带推理协议输出。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md:7-12][VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json:49-110]

`reality.log` 当前包含 426 个 `type=prompt` 块、580 个 `type=result` 块、426 个可解析且唯一的 framed input JSON，输入相位数范围为 3 到 5；这说明 Phase 12 的输入基数应以 426 个 prompt/input JSON 为准，而不是 result 块数量。[VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log][VERIFIED: /home/samuel/TSC_CYCLE/reality.log:15-81]

最安全路径是复用现有 `tsc_cycle.prompt_builder`、`tsc_cycle.prompt_builder.parse_assistant_output`、`tsc_cycle.constraint_lint.validate`、`tsc_cycle.student.parity_gguf` 的 llama-server 单次加载模式，并新增一个 Phase 12 专用模块负责 reality.log 解析、逐样本缓存、最终 `reality_test.log` 渲染、报告与 fail-closed 验证。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:72-122][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py:34-89][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:48-143][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:145-173]

**Primary recommendation:** 新增 `tsc_cycle/eval/reality_replay.py` 与 `scripts/run_phase12_reality_test.sh`，用 v4 q4_K_M GGUF + llama-server 生成 `/home/samuel/TSC_CYCLE/reality_test.log`，并用 parser/linter/report 证明 426/426 输出可解析、协议正确、硬约束通过。[VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json:49-110][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:15-24]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| reality.log 输入提取 | 本地 CLI / Backend batch | 文件系统 | 输入来自本地日志文件，解析应在 Python CLI 中完成并输出结构化 records/cache。[VERIFIED: /home/samuel/TSC_CYCLE/reality.log:15-81] |
| Prompt 构建 | 共享应用库 | 本地 CLI | `build_user_prompt()` 已是 teacher/student/eval 单一 prompt source of truth。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:1-14][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:72-82] |
| 模型推理 | 本地 GGUF serving | llama-server 进程 | 现有 GGUF 生成器通过 `llama-server` 单次加载并 POST `/completion`，避免 per-prompt 冷启动。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:15-24][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:117-143] |
| 协议解析 | 共享应用库 | 验证/report | `parse_assistant_output()` 已解析 full/prefill 两种输出并拒绝 malformed close/native think。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:30-39][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:100-122] |
| 硬约束 lint | 共享应用库 | 验证/report | `constraint_lint.validate()` 已校验相位集合、顺序、整数、上下界。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py:34-89] |
| reality_test.log 渲染 | 本地 CLI / 文件系统 | report artifacts | 用户明确要求输出 `/home/samuel/TSC_CYCLE/reality_test.log`，但验证证据应放到 Phase 12 artifacts/report 中。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md:35-37] |

## Standard Stack

### Core

| Library / Tool | Version / Path | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.3 in `/home/samuel/TSC_CYCLE/.venv/bin/python` | Phase 12 CLI、JSONL/cache/report 处理 | 项目要求 Python 3.12，当前 venv 可用。[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml:4][VERIFIED: local importlib audit] |
| `tsc_cycle.prompt_builder` | project module | 构建输入 prompt、assistant prefill、解析模型输出 | 该模块声明是 teacher/student/eval 的单一 prompt source of truth。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:1-14] |
| `tsc_cycle.constraint_lint` | project module | 硬约束验证 | 该模块返回结构化 lint result 并覆盖 phase mismatch/order/integer/min/max。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py:13-22][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py:34-89] |
| llama-server | `/home/samuel/llama.cpp/build/bin/llama-server` | q4_K_M GGUF 本地推理服务 | 现有 eval/parity 代码使用该 CUDA build，且本机路径存在。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:75-80][VERIFIED: local environment audit] |
| v4 q4_K_M GGUF | `/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` | Phase 12 默认推理模型 | Phase 11 gate verdict 为 GO，recommended artifact 指向该文件。[VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json:49-110] |

### Supporting

| Library / Tool | Version / Path | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tsc_cycle.student.parity_gguf` helpers | project module | `_find_free_port`、`_spawn_server`、`_post_completion`、`_kill_server` | 新 CLI 应复用这些 helper，避免复制 server lifecycle 细节。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:48-143] |
| `tsc_cycle.eval.metrics_constraints` | project module | 将 parsed solution 转换成 flat lint metrics | 生成 Phase 12 report/per-sample JSONL 时使用。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/metrics_constraints.py:14-43] |
| `tsc_cycle.eval.metrics_reasoning` | project module | 规则化 reasoning 段质量检查 | 验证 `reality_test.log` 确实包含可解析 reasoning 段时使用。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/metrics_reasoning.py:17-55] |
| GNU `sha256sum` / Python `hashlib` | coreutils 9.4 / stdlib | 输入、模型、输出 artifact hash | Phase 12 report 应记录输入/输出/model hash 以便追溯。[VERIFIED: local environment audit][VERIFIED: /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json:1-15] |
| `pytest` | 9.0.3 in current venv | 单元/契约测试 | 项目已有 pytest 配置与多组 gate tests。[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml:29-31][VERIFIED: local importlib audit] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GGUF q4_K_M via llama-server | HF merged model via `generate_hf.py` | HF 可作为调试 fallback，但 Phase 11 GO 推荐部署产物是 q4_K_M GGUF，且 HF 路径加载 torch/transformers。[VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json:49-110][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_hf.py:24-29] |
| 单次加载 llama-server | 每条输入调用 llama-cli | 现有注释记录 llama-cli per-prompt 冷启动约 5 分钟，426 条会不可接受；server amortizes load。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:1-8] |
| 可重复 CLI + tests | 手工 one-off artifact generation | 解析 426 条输入、忽略旧输出、校验协议与硬约束都需要可审计证据；项目既有 phase gate 模式也是 report/fail-closed。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md:74-77][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase11_eval_report.py:135-219] |

**Installation:**
```bash
# 不新增 npm 包；优先复用项目 venv 与现有 llama.cpp CUDA build。
/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_prompt_builder.py tests/test_constraint_lint.py -q
```

**Version verification:** Python package/tool versions were verified from the local venv/environment, not npm: Python 3.12.3, torch 2.11.0+cu130, transformers 5.8.0, numpy 2.3.5, pytest 9.0.3, `llama-server` present, `run_safe.sh` present。[VERIFIED: local importlib/environment audit]

**Compatibility note:** `pyproject.toml` declares `transformers>=4.56.2,<5.0`, while the current venv reports `transformers 5.8.0`; Phase 12 should prefer GGUF/llama-server and not depend on HF model loading unless a planner explicitly validates the HF fallback in the current venv。[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml:7-24][VERIFIED: local importlib audit]

## Architecture Patterns

### System Architecture Diagram

```text
/home/samuel/TSC_CYCLE/reality.log
  |
  |-- scan only `type=prompt` blocks
  |-- extract framed JSON between 【cycle_predict_input_json】 and 【/cycle_predict_input_json】
  v
Phase12 input records JSONL/cache
  |
  |-- build_user_prompt(input) + "\n" + build_assistant_prefill()
  v
llama-server (v4 q4_K_M GGUF, loaded once)
  |
  |-- POST /completion, deterministic greedy params
  |-- per-sample cache write for resume
  v
parse_assistant_output(raw_text)
  |              |
  | parse OK     | parse fail / timeout
  v              v
constraint_lint.validate(input, solution)      fail-closed report / partial cache
  |
  | all samples parse + lint OK
  v
/home/samuel/TSC_CYCLE/reality_test.log
  |
  v
artifacts/v4/phase12/{manifest,per_sample,report}.json
```

### Recommended Project Structure

```text
tsc_cycle/
├── eval/
│   └── reality_replay.py        # reality.log parser, GGUF replay runner, output renderer
scripts/
└── run_phase12_reality_test.sh  # project-root wrapper with fixed artifact paths
tests/
└── test_phase12_reality_replay.py  # parser/render/gate contracts without loading GPU stack
artifacts/
└── v4/phase12/                 # generated manifest/report/per-sample evidence
```

### Pattern 1: Extract only framed input JSON from prompt blocks

**What:** 只以 `【cycle_predict_input_json】...【/cycle_predict_input_json】` 作为输入事实来源，并把 `type=result`、`RAW:`、`REASONING:`、`PARSED:` 全部视为旧输出噪声。[VERIFIED: /home/samuel/TSC_CYCLE/reality.log:15-97]

**When to use:** Phase 12 读取 `/home/samuel/TSC_CYCLE/reality.log` 时使用。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md:7-12]

**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/reality.log:15-81 and tsc_cycle.prompt_builder.py:72-82
FRAMED_INPUT_RE = re.compile(
    r"【cycle_predict_input_json】(?P<input>.*?)【/cycle_predict_input_json】",
    re.DOTALL,
)
for match in FRAMED_INPUT_RE.finditer(reality_log_text):
    prediction_input = json.loads(match.group("input"))
```

### Pattern 2: Reuse prompt builder and assistant prefill

**What:** 推理输入应为 `build_user_prompt(record["input"]) + "\n" + build_assistant_prefill()`，并由 `_post_completion()` 返回 `build_assistant_prefill() + content` 以便 parser 看到完整协议。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:149-157][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:79-103]

**When to use:** 对每个 extracted reality input 调用 llama-server `/completion` 时使用。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:145-173]

**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:149-157
user_prompt = build_user_prompt(record["input"])
full_prompt = user_prompt + "\n" + build_assistant_prefill()
raw_text, meta = _post_completion(port, full_prompt, n_predict, timeout_sec)
reasoning, solution = parse_assistant_output(raw_text)
```

### Pattern 3: Per-sample cache then final render

**What:** 先为每条输入写 `artifacts/v4/phase12/gen_cache/{sample_id}.json`，再在全部 parse/lint 通过后渲染最终 `reality_test.log`。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:10-13][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:160-173]

**When to use:** 426 条本地推理需要支持中断恢复，并避免失败时留下看似完整的最终日志。[VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log]

**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:160-173
cache_payload = {
    "sample_id": sample_id,
    "input": prediction_input,
    "raw_text": raw_text,
    "solution": solution,
    "parse_error": None if solution is not None else "solution_unparseable",
    "lint_ok": lint.ok if solution is not None else False,
}
cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

### Anti-Patterns to Avoid

- **从旧 `PARSED:` 或旧 `<SOLUTION>` 取答案:** Phase 12 明确要求忽略 `reality.log` 已有输出，只使用模型新输出。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md:7-12]
- **手写新 prompt 文案:** `prompt_builder.py` 已锁定系统提示、framed JSON、硬约束与输出协议，重复实现会引入协议漂移。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:1-14][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:41-69]
- **使用原生 `<think>` 或 malformed `<end_working_out>`:** parser 会拒绝 native think 与 malformed close tag，测试也覆盖该行为。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:100-103][VERIFIED: /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py:98-134]
- **每条 prompt 启动一次 llama-cli:** 现有代码注释记录 per-prompt 冷启动成本过高，应使用 llama-server 单次加载。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:1-8]
- **在 parse/lint 失败时强行 clamp 或修补 JSON:** 输出必须来自模型；验证失败应 fail closed 或重跑推理，而不是把程序生成的修补结果写成模型输出。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md:7-12][ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Prompt 模板 | 新字符串模板 | `build_user_prompt()` | 现有模板已包含系统提示、framed JSON、硬约束、输出协议。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:41-82] |
| Assistant prefill | 手写 `<start_working_out>` 拼接策略 | `build_assistant_prefill()` | 现有生成路径依赖 prefill 让 parser 看到完整协议。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:85-88][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:99-103] |
| 协议 parser | regex/json 自写全套 parser | `parse_assistant_output()` | 已支持 full/prefill 输出并拒绝 native/malformed 标签和非整数值。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:30-39][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:100-122] |
| 硬约束验证 | 新 min/max/order 检查 | `constraint_lint.validate()` / `score_constraint()` | 已覆盖 key set、相位顺序、整数、上下界与 unparseable case。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py:34-89][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/metrics_constraints.py:14-43] |
| GGUF server lifecycle | 手动 `subprocess.Popen`/HTTP/kill 逻辑 | `tsc_cycle.student.parity_gguf` helper | helper 已实现 free port、health wait、POST completion、process-group cleanup。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:48-160] |
| 最新模型选择 | 硬猜 newest run directory | Phase 11 gate `recommended_artifact` | gate report 明确给出 GO 与 recommended artifact。[VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json:49-110] |

**Key insight:** Phase 12 的难点不是算法，而是防止“旧日志输出泄漏到新 reality_test.log”、防止协议漂移、以及让 426 条本地生成具备可恢复和可审计证据。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md:7-12][VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log]

## Common Pitfalls

### Pitfall 1: 把旧 result 当成输入或答案

**What goes wrong:** `reality.log` 中 result 块多于 prompt 块，直接按 separator 或 result 解析会混入旧 LMStudio 输出。[VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log][VERIFIED: /home/samuel/TSC_CYCLE/reality.log:0-14]

**Why it happens:** 文件开头就是一个 result 块，而第一个完整 prompt 块从第 15 行才开始。[VERIFIED: /home/samuel/TSC_CYCLE/reality.log:0-17]

**How to avoid:** 只提取 framed input JSON；记录 `prompt_count=426`、`input_json_count=426`、`unique_input_hashes=426` 作为 manifest gate。[VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log]

**Warning signs:** 输出条数接近 580 或 1006 separator，而不是 426。[VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log]

### Pitfall 2: 生成内容缺少 opening think tag

**What goes wrong:** llama-server completion 只返回 prefill 后的新 token，如果不把 `build_assistant_prefill()` 加回 raw_text，`parse_assistant_output()` 可能只能按 prefill form 解析或导致 report 不一致。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:69-103]

**Why it happens:** 现有 `_post_completion()` 明确返回 `build_assistant_prefill() + content`。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:99-103]

**How to avoid:** 复用 `_post_completion()` 或保持同等返回语义。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:69-103]

**Warning signs:** `raw_text` 以 `</end_working_out>` 前内容开头但缺少 `<start_working_out>`，或 report 中 reasoning tier 大量 miss。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/metrics_reasoning.py:22-55]

### Pitfall 3: n_predict 截断导致缺少 `</SOLUTION>`

**What goes wrong:** 输出未闭合时 parser 返回 `solution=None`，最终 hard-constraint lint 也只能标记 unparseable。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:100-122][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/metrics_constraints.py:30-33]

**Why it happens:** 现有 GGUF eval 默认 `n_predict=384`；reality.log 需要显式 reasoning，长 reasoning 可能接近上限。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:19-24][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:81]

**How to avoid:** 先沿用 deterministic greedy 参数；若出现 parse_error，只对失败样本用更高 `n_predict` 重跑并记录 retry，不要修补输出。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:79-87][ASSUMED]

**Warning signs:** `parse_error=solution_unparseable` 且 `raw_text` 尾部没有 `</SOLUTION>`。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:153-168]

### Pitfall 4: 直接覆盖最终文件导致半成品被误用

**What goes wrong:** 中途失败时 `/home/samuel/TSC_CYCLE/reality_test.log` 可能存在但不完整。[ASSUMED]

**Why it happens:** 426 条推理耗时较长，进程可能被中断。[VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log]

**How to avoid:** 先写 `reality_test.log.tmp` 与 per-sample cache，全部 gate 通过后 atomic rename 到 `reality_test.log`。[ASSUMED]

**Warning signs:** final log 行数/record 数低于 manifest 的 426。[VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log]

## Code Examples

Verified patterns from existing sources:

### GGUF completion and parse

```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:149-168
user_prompt = build_user_prompt(rec["input"])
full = user_prompt + "\n" + build_assistant_prefill()
text, meta = _post_completion(port, full, args.n_predict, args.timeout_sec)
_, sol = parse_assistant_output(text)
err = None if sol is not None else "solution_unparseable"
```

### Hard-constraint lint

```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py:34-89
res = validate(prediction_input, solution)
if not res.ok:
    violations = res.violations
```

### Final log record shape recommendation

```text
# Source: /home/samuel/TSC_CYCLE/reality.log:15-97 + Phase 12 context
{as_of}|INFO|type=prompt|crossing_id={crossing_id}

{build_user_prompt(input)}
--------------------------------------------------------------------------------
{as_of}|INFO|type=result|engine=tsc-cycle-v4-q4_K_M|crossing_id={crossing_id}|sample_id={sample_id}
RAW:
<start_working_out>...</end_working_out><SOLUTION>{"1":50,...}</SOLUTION>
PARSED:
{
  "1": 50
}
LINT:
{"ok": true, "violations": []}
--------------------------------------------------------------------------------
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 原始 `reality.log` 使用 LMStudio result 格式，`RAW` 中可只有 `<SOLUTION>`，reasoning 单独在 `REASONING:` 块。[VERIFIED: /home/samuel/TSC_CYCLE/reality.log:0-14] | Phase 12 应输出完整 raw protocol `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md:7-12] | v4.0 标签协议修复后。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md:16-22] | reality_test.log 不能照搬旧 result layout 的协议缺口。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:63-69] |
| 每 prompt CLI 推理。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:1-8] | llama-server 单次加载，多次 POST `/completion`。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:15-24] | Phase 10/11 GGUF parity/eval 路径已采用。[VERIFIED: /home/samuel/TSC_CYCLE/scripts/run_v4_phase11_eval_matrix.sh:52-57] | 426 条 reality inputs 可在一个 server lifecycle 内完成并支持 cache resume。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:10-13] |
| 手工选择模型产物。[ASSUMED] | Phase 11 gate report 的 `recommended_artifact` 作为部署 handoff。[VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json:49-110] | Phase 11 decision GO 后。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md:19-27] | Phase 12 默认模型路径明确，避免误用 v1 baseline 或中间 fp16 artifact。[VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json:49-110] |

**Deprecated/outdated:**
- `vLLM`：项目指令明确本机暂时不能使用 vLLM，Phase 12 不应规划 vLLM 推理。[CITED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 原生 `<think>`/`</think>`：v4.0 requirements 明确 out of scope，parser 也拒绝 native tags。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md:60-65][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:100-103]
- malformed `<end_working_out>` close：v4.0 requirements 要求改为 `</end_working_out>`，parser/tests 也拒绝 malformed close。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md:18-20][VERIFIED: /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py:98-134]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | parse/lint 失败时可以只重跑推理而不修补输出。 | Common Pitfalls / Anti-Patterns | 如果用户希望 best-effort 写入失败样本，planner 需要改为 partial log + report，而不是 fail-closed。 |
| A2 | `reality_test.log.tmp` atomic rename 是期望的最终文件写入策略。 | Common Pitfalls | 如果用户需要边生成边查看最终文件，planner 需要改为 `.partial` 明确命名。 |
| A3 | `n_predict=384` 不足时可对失败样本提高 token budget 重跑。 | Common Pitfalls | 如果必须全程同一 decode 配置，planner 应禁止 retry 或把 retry 结果标记为不同 pass。 |

## Open Questions (RESOLVED)

1. **RESOLVED — `reality_test.log` 不完全复刻旧 log 的 `RAW/REASONING/PARSED` 三段。**
   - Final decision: 输出保持 prompt/result 人类可读结构，但 `RAW:` 内写完整 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` 协议，并额外写 `PARSED:`/`LINT:` 方便审计。
   - Rationale: 用户要求模型输出包含思考过程；v4.0 协议要求完整 raw protocol，旧 `REASONING:` 分离格式会掩盖协议完整性。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md:41-45][VERIFIED: /home/samuel/TSC_CYCLE/reality.log:0-14]

2. **RESOLVED — 允许对生成失败样本重试，但禁止程序修补模型输出。**
   - Final decision: Phase 12 gate 要求 426/426 parse+lint OK；若样本 timeout/truncated/unparseable，只允许以更高 token budget 或相同 CLI resume/retry 重新推理该样本，并记录 retry 元数据；不得 clamp、补 phase、改 JSON 或把修补结果写成模型输出。
   - Rationale: 用户目标是完整 `reality_test.log`，且输出必须来自最新模型；现有 eval 代码记录 parse_error 而不自动修补，Phase 12 延续该 fail-closed 语义。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py:151-168]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `/home/samuel/TSC_CYCLE/reality.log` | 输入源 | ✓ | 1.7 MiB, 426 framed inputs | 无；缺失则阻塞。[VERIFIED: local file audit] |
| `/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` | 默认模型 | ✓ | 2.4 GiB, sha256 in Phase 10 report | v1 q4_K_M 是 fallback/comparison artifact，但 Phase 12 默认不应使用。[VERIFIED: local file audit][VERIFIED: /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json:1-15][VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json:64-110] |
| `/home/samuel/llama.cpp/build/bin/llama-server` | GGUF 推理 | ✓ | executable present | HF merged model fallback 需要 torch/transformers 验证。[VERIFIED: local environment audit][VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_hf.py:24-29] |
| `/home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh` | HF fallback / safe wrapper | ✓ | script present | GGUF path通常不需要 torch 进程；仍可由 wrapper 管理外层命令。[VERIFIED: local environment audit] |
| Python venv | CLI/tests | ✓ | Python 3.12.3 | 无；项目 requires Python 3.12。[VERIFIED: local importlib audit][VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml:4] |
| pytest | contract tests | ✓ | 9.0.3 | 可用 `python -m pytest`。[VERIFIED: local importlib audit][VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml:29-31] |

**Missing dependencies with no fallback:** None found for the recommended GGUF path。[VERIFIED: local environment audit]

**Missing dependencies with fallback:** Current venv `transformers 5.8.0` differs from `pyproject.toml` `<5.0`; this affects only HF fallback risk, not recommended GGUF replay path。[VERIFIED: local importlib audit][VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml:7-24]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 in `/home/samuel/TSC_CYCLE/.venv`。[VERIFIED: local importlib audit] |
| Config file | `/home/samuel/TSC_CYCLE/pyproject.toml` `[tool.pytest.ini_options]` uses `testpaths = ["tests"]` and `addopts = "-q"`。[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml:29-31] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_phase12_reality_replay.py -q`。[VERIFIED: project pytest config] |
| Full suite command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q`。[VERIFIED: project pytest config] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P12-IMPLICIT-01 | 从 `reality.log` 提取 426 个 framed input JSON，且不读取旧 result 输出 | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_phase12_reality_replay.py::test_extracts_only_prompt_inputs -q` | ❌ Wave 0 |
| P12-IMPLICIT-02 | 使用 Phase 11 GO recommended q4_K_M artifact，不误用 v1 baseline | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_phase12_reality_replay.py::test_uses_phase11_recommended_artifact -q` | ❌ Wave 0 |
| P12-IMPLICIT-03 | 输出 raw_text 可由 `parse_assistant_output()` 解析且禁止 native/malformed tags | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_phase12_reality_replay.py::test_rendered_outputs_follow_v4_protocol -q` | ❌ Wave 0 |
| P12-IMPLICIT-04 | 每条 parsed solution 通过 `constraint_lint.validate()` | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_phase12_reality_replay.py::test_report_fails_closed_on_parse_or_lint_errors -q` | ❌ Wave 0 |
| P12-IMPLICIT-05 | 最终 `/home/samuel/TSC_CYCLE/reality_test.log` 只有全部样本通过后才写入/rename | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_phase12_reality_replay.py::test_final_log_not_written_when_gate_fails -q` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_phase12_reality_replay.py tests/test_prompt_builder.py tests/test_constraint_lint.py -q`。[VERIFIED: existing test files]
- **Per wave merge:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_phase12_reality_replay.py tests/test_v4_phase11_eval_matrix.py -q`。[VERIFIED: existing test files]
- **Phase gate:** Full suite green before `/gsd-verify-work` plus Phase 12 generation report showing 426/426 parse+lint OK。[VERIFIED: python audit of /home/samuel/TSC_CYCLE/reality.log]

### Wave 0 Gaps

- [ ] `tests/test_phase12_reality_replay.py` — covers parser, artifact selection, protocol render, fail-closed gate。[VERIFIED: tests directory currently lacks Phase 12 test]
- [ ] `tsc_cycle/eval/reality_replay.py` — module under test; should be lightweight and avoid importing torch/transformers at collection time。[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v4_phase11_eval_matrix.py:19-34]
- [ ] `scripts/run_phase12_reality_test.sh` — end-to-end wrapper using absolute paths and existing llama-server。[VERIFIED: /home/samuel/TSC_CYCLE/scripts/run_v4_phase11_eval_matrix.sh:3-10]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No network auth boundary is introduced; llama-server binds localhost in existing helpers.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:126-135] |
| V3 Session Management | no | No user sessions are introduced.[VERIFIED: Phase 12 context] |
| V4 Access Control | yes | Refuse writes outside `/home/samuel/TSC_CYCLE/reality_test.log` and `artifacts/v4/phase12/`; copy Phase 11 reject-output-path style.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase11_eval_report.py:50-56][ASSUMED] |
| V5 Input Validation | yes | Parse framed JSON with `json.loads`, validate expected `prediction.phase_waits`, then lint outputs with `constraint_lint.validate()`.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py:34-89] |
| V6 Cryptography | yes | Use SHA-256 hashing via existing artifact/report pattern or stdlib/coreutils; do not implement custom hashing.[VERIFIED: /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json:8-14] |

### Known Threat Patterns for Phase 12

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Old output contamination from `reality.log` | Tampering | Extract only framed input JSON and record input hashes; never parse old `RAW/REASONING/PARSED` as source data.[VERIFIED: /home/samuel/TSC_CYCLE/reality.log:0-14][VERIFIED: /home/samuel/TSC_CYCLE/reality.log:15-81] |
| Partial final artifact mistaken for complete output | Integrity | Write per-sample cache and tmp file first; atomic rename final log only after gate passes.[ASSUMED] |
| Path traversal / accidental overwrite | Tampering | Hard-code or validate output targets under project root and Phase 12 artifact root.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase11_eval_report.py:50-56][ASSUMED] |
| Local server exposed beyond localhost | Information Disclosure | Reuse `_spawn_server()` defaults `--host 127.0.0.1` and `--no-webui`.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py:126-135] |
| Native think/protocol leakage | Tampering | Use `parse_assistant_output()` and fail if native `<think>` or malformed close appears.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py:100-103] |

## Sources

### Primary (HIGH confidence)

- `/home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-CONTEXT.md` — Phase 12 boundary, input/output/model constraints checked.[VERIFIED]
- `/home/samuel/TSC_CYCLE/reality.log` — log structure, prompt/result examples, framed JSON format checked.[VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py` — prompt construction, prefill, protocol parser checked.[VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py` — hard-constraint validator checked.[VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/eval/generate_gguf.py` — GGUF generation/cache schema checked.[VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/student/parity_gguf.py` — llama-server helper and deterministic completion params checked.[VERIFIED]
- `/home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json` — Phase 11 GO and recommended artifact checked.[VERIFIED]
- `/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json` — q4_K_M artifact paths and hashes checked.[VERIFIED]
- `/home/samuel/TSC_CYCLE/CLAUDE.md` — project constraints checked.[CITED]

### Secondary (MEDIUM confidence)

- Local environment audit via `/home/samuel/TSC_CYCLE/.venv/bin/python` and shell probes — package versions/tool availability checked.[VERIFIED]
- Python audit of `/home/samuel/TSC_CYCLE/reality.log` — counts/hash uniqueness/protocol marker statistics checked.[VERIFIED]

### Tertiary (LOW confidence)

- Assumptions A1-A3 about retry policy, atomic rename, and n_predict fallback require planner/user confirmation if they become locked behavior.[ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — current code paths, artifact paths, and environment availability were verified locally.[VERIFIED]
- Architecture: HIGH — recommended architecture directly reuses existing Phase 10/11 GGUF generation and parser/linter modules.[VERIFIED]
- Pitfalls: HIGH for old-output contamination and protocol parser behavior; MEDIUM for retry/atomic-write policy because those are recommendations rather than existing implementation.[VERIFIED][ASSUMED]

**Research date:** 2026-05-11  
**Valid until:** 2026-06-10 for codebase/artifact paths; re-verify sooner if Phase 11 recommended artifact changes or `reality.log` is replaced.[ASSUMED]
