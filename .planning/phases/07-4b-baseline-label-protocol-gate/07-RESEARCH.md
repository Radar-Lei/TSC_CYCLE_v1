# Phase 7: 4B baseline/label protocol gate - Research

**Researched:** 2026-05-10  
**Domain:** 本地 preflight gate、Qwen3-4B tokenizer 协议审计、v1 baseline 只读引用  
**Confidence:** HIGH（代码库与规划文件为主；外部事实用 HF/Transformers 文档交叉验证）

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Baseline and Environment Gate
- The student model is locked to `Qwen/Qwen3-4B-Thinking-2507`; Qwen3.5-9B must not be selected by any Phase 7 gate.
- Training environment checks must reference `/dgx-spark-training` expectations and `/home/samuel/dgx-spark-setup/.venv`; do not upgrade PyTorch, Transformers, CUDA, or the training framework.
- v1.0 baseline paths under `runs/20260507T032419Z/` are read-only references; Phase 7 must detect and report whether the gate writes there.

### Label Protocol Gate
- The only accepted thought/output protocol is `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`.
- The incorrect closing marker `<end_working_out>` must be rejected as a malformed ending tag.
- Native Qwen `<think>` and `</think>` must be rejected anywhere in fixture inputs or outputs.
- Tokenizer audit must dynamically record the native `<think>`/`</think>` token IDs and prove the four custom tags split into multiple sub-tokens.

### Claude's Discretion
- Implementation details are at Claude's discretion as long as the gate is scriptable, testable, and produces auditable artifacts for downstream Phase 8-11 execution.

### Claude's Discretion
- Implementation details are at Claude's discretion as long as the gate is scriptable, testable, and produces auditable artifacts for downstream Phase 8-11 execution.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- Dataset cleaning and `<end_working_out>` normalization counts belong to Phase 8.
- Full training smoke and adapter generation belong to Phase 9.
- GGUF conversion and q4_K_M smoke belong to Phase 10.
- Final eval matrix and GO/NO-GO decision belong to Phase 11.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BASE-01 | 学生模型固定为 `Qwen/Qwen3-4B-Thinking-2507`，不再使用 Qwen3.5-9B 作为本里程碑训练基座 | Gate 必须 fail-closed 校验模型 ID 等于 `Qwen/Qwen3-4B-Thinking-2507`，并拒绝 `Qwen/Qwen3.5-9B`；现有 v3 gate 默认仍是 Qwen3.5，不能直接复用默认值。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/env_smoke_v3.py; grep codebase] |
| BASE-02 | 训练栈沿用 `/dgx-spark-training` 与 `/home/samuel/dgx-spark-setup/.venv` 的已验证 4B 路径，不升级 PyTorch/Transformers/训练框架 | Phase 7 应只读取并报告环境，不安装或升级依赖；本机 `/home/samuel/dgx-spark-setup/.venv/bin/python` 存在，但该 venv 当前未安装 `bitsandbytes` 与 `trl`，因此 gate 应把它作为环境证据/告警而不是静默修复。[VERIFIED: command probes 2026-05-10] |
| BASE-03 | v1.0 baseline artifact 与 gen_cache 以只读方式引用，v4.0 流程不得写入 `runs/20260507T032419Z/` | v1 baseline root 与 q4_K_M artifact 当前为只读权限；实际 gen_cache 目录名是 `gguf_q4_k_m`，而 CONTEXT 写作 `gguf_q4km`，planner 必须处理这个路径差异。[VERIFIED: stat/find /home/samuel/TSC_CYCLE/runs/20260507T032419Z] |
| TAG-01 | 全链路思考协议固定为 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` | 以 REQUIREMENTS/ROADMAP/CONTEXT 的 slash closing form 为准；当前 `prompt_builder.py` 与既有测试把 `<end_working_out>` 当作正例、把 `</end_working_out>` 当作 legacy 反例，Phase 7 必须先修正这一反向实现。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py; /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py] |
| TAG-02 | 数据清洗/重建必须把错误的 `<end_working_out>` 结束标签规范化为 `</end_working_out>`，并报告替换数量 | Phase 7 不做数据清洗，但必须用 fixture/gate 明确接受 slash close、拒绝 bare close，并把规范化计数留给 Phase 8。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; /home/samuel/TSC_CYCLE/.planning/phases/07-4b-baseline-label-protocol-gate/07-CONTEXT.md] |
| TAG-03 | 训练与评测 prompt builder 禁止注入原生 `<think>`/`</think>` 或 chat_template thinking token | Qwen model card 说明默认 chat template 会自动包含 `<think>`，因此 Phase 7 必须继续使用 raw-text prompt path 并拒绝 `apply_chat_template` 路径。[CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507; VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py] |
| TAG-04 | Qwen3-4B tokenizer audit 证明 4 个自定义标签均为多 sub-token，且 native `<think>`/`</think>` token id 被动态记录用于泄漏检查 | 现有 `tokenizer_check.py` 已有动态 native ID 查询与 custom tag 多 token 检查，但注释仍提到 Qwen3.5，Phase 7 应复用函数并把 model 改为 Qwen3-4B。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py; CITED: https://huggingface.co/docs/transformers/main_classes/tokenizer] |
</phase_requirements>

## Summary

Phase 7 是一个本地、可脚本化、可测试的硬门禁阶段：它不应启动训练、不应重建数据、不应写入 v1 baseline；它只应产出审计 JSON/Markdown artifact，证明 v4.0 已回到 `Qwen/Qwen3-4B-Thinking-2507`，训练环境未被升级，v1.0 baseline 是只读引用，并且标签协议只接受 slash closing form `</end_working_out>`。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]

最关键的代码库发现是：当前 `tsc_cycle/prompt_builder.py`、`tests/test_prompt_builder.py` 与部分 Phase 7 前置测试片段仍把 `<end_working_out>` 当作正确 closing tag，并把 `</end_working_out>` 当作 legacy 反例；这与 v4.0 REQUIREMENTS、ROADMAP、CONTEXT 和用户补充上下文冲突，Phase 7 计划必须把“修正协议方向”作为第一组 RED/GREEN 工作。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py; /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py; /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]

v3 gate 模式可以复用，但不能照搬默认值：`env_smoke_v3.py`、`tokenizer_audit_v3.py`、`phase1_report.py`、`run_safe_scope_check_v3.py` 提供了 parser、JSON artifact、fail-closed 聚合报告、动态 tokenizer audit、只读/frozen evidence 的实现模式；它们当前默认 Qwen3.5-9B 或 v3 artifact 路径，Phase 7 应建立新的 `phase7` gate 模块/脚本，避免继续选择 Qwen3.5。[VERIFIED: grep codebase; /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/*.py]

**Primary recommendation:** 新增一个轻量 Phase 7 gate（建议 `tsc_cycle/v4_gates/baseline_protocol_gate.py` 或 `tsc_cycle/v3_gates/phase7_baseline_protocol_gate.py`）加对应 pytest，聚合 model/env/baseline/tokenizer/protocol fixture 结果到 `artifacts/v4/phase7/phase7_gate_report.json`，并 fail-closed 阻止 Phase 8。[ASSUMED]

## Project Constraints (from CLAUDE.md)

- 本项目目标是将 GPT-5.5 high 教师能力蒸馏到 `Qwen3-4B-Thinking-2507`，最终产出本地 GGUF fp16 + q4_K_M 的 4B 推理模型。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 硬约束价值目标是 OOD 上满足 min/max、整数秒、相位顺序与覆盖全相位，且数值决策接近教师。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 学生模型锁定为 Qwen3-4B-Thinking-2507；训练栈为 QLoRA r=64，HF Transformers + PEFT 或已验证方案；导出目标为 llama.cpp GGUF。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- DGX Spark GB10 aarch64 CUDA 13 环境下禁止引入 flash-attn cu12 路径，优先 SDPA、swap/OOM 防护与已知良好 venv。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 暂时不能使用 vLLM；Phase 7 不能规划 vLLM 检查或依赖。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 教师 API worker 上限为 10；Phase 7 不调用教师 API，但后续 artifact 中不能建议超过该上限。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 训练任何思考标签前必须验证自定义标签拆成多个 sub-token，且不能与原生 `<think>` 冲突。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 数据进入训练集前必须通过硬约束 lint；Phase 7 的 protocol fixture 不代替 Phase 8/9 的数据 lint。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- 回复与报告沟通使用简体中文；git commit message 不得包含 `Co-Authored-By`。[VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 模型 ID 锁定 | Local CLI gate | Training config | Phase 7 只需读取常量/参数并 fail-closed，不加载全训练流程；后续训练配置再消费锁定值。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| DGX Spark 环境引用 | Local CLI gate | OS/runtime | Gate 应读取 interpreter/package/scope 证据，不应安装或升级依赖。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/07-4b-baseline-label-protocol-gate/07-CONTEXT.md] |
| v1 baseline 只读引用 | Filesystem/artifact layer | Eval layer | Phase 7 的职责是证明 `runs/20260507T032419Z/` 前后未写入；Phase 11 才使用 baseline 做评测比较。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| 标签协议 fixture | Shared prompt/protocol layer | Teacher/student/eval modules | `prompt_builder.py` 是教师、学生、评测共享单一来源；协议修正必须优先在该层锁定。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py] |
| tokenizer custom/native audit | Tokenizer layer | Dataset/training/eval | 动态记录 native token IDs 后，Phase 8/9/10/11 可复用作泄漏检查。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py] |
| gate report artifact | Artifact/reporting layer | Planner/phase handoff | 既有 v3 gate 使用 JSON artifact 聚合结果，Phase 7 应沿用可审计产物模式。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py] |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.3 in project/dgx venv; host `python3` is 3.14.4 | 运行 gate 脚本与 pytest | 项目 `pyproject.toml` 要求 `>=3.12,<3.13`，所以 gate 命令必须显式使用 venv Python，不要使用 host `python3`。[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; command probes] |
| Transformers | project venv 5.8.0 installed; PyPI current 5.8.0; pyproject pins `>=4.56.2,<5.0` | `AutoTokenizer.from_pretrained` 与 tokenizer `encode(..., add_special_tokens=False)` audit | 官方 tokenizer API 支持从预训练模型加载 tokenizer，并用 `encode` 将字符串转 token IDs；Qwen3 model card 要求 transformers 不低于 4.51.0。[VERIFIED: command probes; CITED: https://huggingface.co/docs/transformers/main_classes/tokenizer; CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507] |
| pytest | installed 9.0.3; PyPI current 9.0.3 | Phase 7 fixture acceptance/rejection 与 gate helper 单测 | 项目已有 pytest 配置 `testpaths = ["tests"]` 且现有轻量 gate 测试用 pytest。[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; command probes] |
| pathlib/json/hashlib/stat/os | Python stdlib | baseline path metadata、hash、permission/write-bit 检查与 JSON report | 既有 v3 report/frozen 代码使用这些 stdlib 模式，无需新增依赖。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/sft_v3.py; /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| torch | project/dgx venv 2.11.0+cu130 installed; PyPI current 2.11.0 | 可选环境证据，不建议 Phase 7 加载 4B 权重 | Phase 7 可报告 torch/CUDA 版本，但不应做全模型加载训练 smoke；BASE-02 是环境引用门，不是训练门。[VERIFIED: command probes; /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| bitsandbytes | project venv 0.48.0 installed; dgx-spark-setup venv missing | 环境报告项 | Phase 7 应记录缺失/存在状态，不应安装；缺失在 dgx setup venv 中是告警而非 Phase 7 自动修复。[VERIFIED: command probes] |
| TRL | project venv 1.3.0 installed; dgx-spark-setup venv missing | 环境报告项 | Phase 7 只报告训练栈状态；Phase 9 才真正依赖训练库。[VERIFIED: command probes] |
| scripts/dgx_spark/run_safe.sh | present/executable | 后续训练安全 wrapper 证据 | Phase 7 可检查路径存在；run_safe 内存 scope 的深度训练检查留给训练 smoke 阶段。[VERIFIED: command probes; /home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 新建 Phase 7 gate 模块 | 直接改 v3 gate 默认值 | 直接改 v3 默认值容易污染已完成 v3 证据；Phase 7 需要 v4 artifact 边界和 Qwen3-4B 专属 report。[VERIFIED: grep codebase; ASSUMED] |
| 动态 tokenizer audit | 硬编码 `<think>`/`</think>` IDs 151667/151668 | model card 示例出现 `151668`，但 requirement 要“动态记录”；硬编码会让换 tokenizer 时检查失真。[CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507; VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |
| raw-text fixture parser | `apply_chat_template` | Qwen3 model card 说明默认 chat template 会自动包含 `<think>`；本项目 TAG-03 禁止 native thinking token 注入。[CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507; VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |

**Installation:**
```bash
# 不安装新包；使用现有 venv 运行 Phase 7 gate。
/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest ...
```
[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; command probes]

**Version verification:** `python3 -m pip index versions transformers pytest torch` 在 2026-05-10 返回 transformers 5.8.0、pytest 9.0.3、torch 2.11.0 为当前 PyPI 版本；项目 venv 当前安装 transformers 5.8.0、pytest 9.0.3、torch 2.11.0+cu130。[VERIFIED: command probes]

## Architecture Patterns

### System Architecture Diagram

```text
Operator / CI
  |
  v
Phase 7 gate command
  |
  +--> Model lock check
  |       |-- accept exactly Qwen/Qwen3-4B-Thinking-2507
  |       `-- reject any Qwen3.5-9B selection
  |
  +--> Environment evidence check
  |       |-- read venv paths/package versions/run_safe path
  |       `-- report warnings; do not install/upgrade
  |
  +--> v1 baseline read-only check
  |       |-- snapshot paths, modes, mtimes, hashes/counts before
  |       |-- perform read-only stat/open checks only
  |       `-- snapshot after and fail if changed/writable/output path targets v1
  |
  +--> Tokenizer audit
  |       |-- AutoTokenizer.from_pretrained(Qwen/Qwen3-4B-Thinking-2507)
  |       |-- encode four custom tags with add_special_tokens=False
  |       `-- dynamically record native <think>/</think> IDs
  |
  +--> Protocol fixture gate
  |       |-- accept <start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>
  |       |-- reject <end_working_out>
  |       `-- reject native <think>/</think> in inputs/outputs
  |
  v
artifacts/v4/phase7/phase7_gate_report.json
  |
  +--> Phase 8 consumes protocol literals + tokenizer audit
  `--> Phase 11 consumes read-only baseline references
```
[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py]

### Recommended Project Structure
```text
tsc_cycle/
├── prompt_builder.py              # shared protocol literals and parser; must be corrected first
├── tokenizer_check.py             # reusable dynamic tokenizer audit helpers
└── v4_gates/                      # recommended new namespace for v4-specific gates
    ├── __init__.py
    └── phase7_baseline_protocol.py
scripts/
└── run_v4_phase7_gate.sh          # fixed argv wrapper, no shell snippets
artifacts/
└── v4/phase7/
    ├── tokenizer_audit.json
    ├── baseline_readonly.json
    ├── protocol_fixture.json
    ├── environment.json
    └── phase7_gate_report.json
tests/
├── test_v4_phase7_baseline_gate.py
├── test_v4_phase7_protocol.py
└── test_v4_phase7_tokenizer_audit.py
```
[ASSUMED]

### Pattern 1: Fail-closed aggregate report
**What:** 每个子检查写结构化 payload，最终 `phase7_gate_report.json` 包含 `ok`、`fatal_failures`、`warnings`、`gates`、`requirements_covered`、`next_phase_allowed`。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py]

**When to use:** 所有 Phase 7 子门禁都应纳入同一 report，planner 后续用 report 的 `ok=true` 作为 Phase 8 前置条件。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py
report = {
    "ok": not failures,
    "fatal_failures": failures,
    "warnings": warnings,
    "gates": gates,
    "requirements_covered": ["BASE-01", "BASE-02", "BASE-03", "TAG-01", "TAG-02", "TAG-03", "TAG-04"],
    "next_phase_allowed": not failures,
}
```
[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py]

### Pattern 2: Dynamic tokenizer ID audit, no constants
**What:** 用 `tokenizer.encode(tag, add_special_tokens=False)` 记录 custom/native tag IDs，custom tag 必须多 token，native tag IDs 动态记录给后续泄漏检查。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py; CITED: https://huggingface.co/docs/transformers/main_classes/tokenizer]

**When to use:** Phase 7 tokenizer audit、Phase 8 tokenized data leakage check、Phase 9 smoke generation check都应使用同一个 dynamic native ID set。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]

**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py
native = {tag: tokenizer.encode(tag, add_special_tokens=False) for tag in ("<think>", "</think>")}
custom = {tag: tokenizer.encode(tag, add_special_tokens=False) for tag in CUSTOM_TAGS}
```
[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py]

### Pattern 3: Read-only baseline snapshot before/after
**What:** 对 `runs/20260507T032419Z/` 做前后 snapshot，记录权限位、mtime、文件计数、关键文件 hash；gate 期间不得以任何 output path 写入该 root。[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py; /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/sft_report_v3.py]

**When to use:** BASE-03 和后续 Phase 11 baseline 评测引用都需要该证据。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]

**Example:**
```python
# Source pattern: /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py
write_bits = path.stat().st_mode & 0o222
assert write_bits == 0
```
[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py]

### Anti-Patterns to Avoid
- **复用 v3 默认模型 ID:** v3 gate 默认 `Qwen/Qwen3.5-9B`，Phase 7 若复用默认值会直接违反 BASE-01。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/env_smoke_v3.py]
- **使用 `apply_chat_template` 做协议 fixture:** Qwen3 model card 指出默认 chat template 会自动包含 `<think>`，违反 TAG-03。[CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507]
- **把 protocol 修正延后到 Phase 8:** 当前代码正负例方向已反，Phase 7 如果不先锁 fixture，Phase 8 会在错误 parser 上做数据清洗。[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py; /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]
- **写入 v1 baseline 目录生成 gate artifact:** v1 root 当前只读，且 requirement 要零写入；所有 Phase 7 artifacts 应在 `artifacts/v4/phase7/`。[VERIFIED: stat /home/samuel/TSC_CYCLE/runs/20260507T032419Z; /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| tokenizer token ID 映射 | 自写 BPE/字符串切分 | `AutoTokenizer.from_pretrained(...).encode(..., add_special_tokens=False)` | 官方 tokenizer API 才能反映模型实际 vocab/special token 行为。[CITED: https://huggingface.co/docs/transformers/main_classes/tokenizer] |
| native think 泄漏检测 | 硬编码 v1 常量 | `native_think_token_ids(tokenizer)` 动态集合 | Requirement 明确要求动态记录；现有 helper 已实现。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py] |
| gate report 聚合 | console-only 输出 | JSON artifact + pytest 断言 | v3 gate 已建立 JSON report 模式，planner/后续 phase 可消费。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py] |
| baseline “只读”证明 | 只检查 `Path.exists()` | 权限位 + 前后 hash/count/mtime snapshot + output path guard | 只存在不等于只读；BASE-03 要证明未写入。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py] |
| 协议解析 | 宽松 regex 接受多个 close tag | 单一 parser，遇 native tags 或 wrong close fail-closed | TAG-01/TAG-02/TAG-03 要 fixture 明确接受/拒绝，不能兼容旧错格式。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |

**Key insight:** Phase 7 的价值不是“跑更多 smoke”，而是用最小可审计证据提前阻断三类昂贵错误：选错 9B 基座、污染 v1 baseline、沿用错误 `<end_working_out>` 协议。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; /home/samuel/TSC_CYCLE/.planning/STATE.md]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | 数据清洗/重建中 `<end_working_out>` → `</end_working_out>` 的替换属于 Phase 8；Phase 7 只做 fixture gate，不扫描/改写数据集。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/07-4b-baseline-label-protocol-gate/07-CONTEXT.md] | Phase 7 输出协议字面值与 accept/reject fixture；Phase 8 做数据迁移计数。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |
| Live service config | 未发现 Phase 7 依赖外部 live service config；本阶段不调用 OpenAI API、不改 wandb、不改部署端点。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] | None — code/config gate only。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| OS-registered state | DGX safe wrapper `scripts/dgx_spark/run_safe.sh` 存在；Phase 7 不注册 systemd service，只可检测 wrapper path。[VERIFIED: command probes] | 记录存在性；不要调用 `sudo swapoff` 或修改 OS state。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/run_safe_scope_check_v3.py] |
| Secrets/env vars | Phase 7 不需要 `OPENAI_API_KEY`；teacher labeling 在其他阶段才需要。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/teacher/labeler.py; /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] | 不读取/要求 secrets；若环境报告包含 env，只报告非敏感路径/版本。[ASSUMED] |
| Build artifacts | v1 baseline root `runs/20260507T032419Z/` 已存在且只读； q4 artifact 存在；实际 q4 gen_cache 目录名为 `gguf_q4_k_m`。[VERIFIED: stat/find /home/samuel/TSC_CYCLE/runs/20260507T032419Z] | Gate 应接受实际路径或 fail with actionable path mismatch；不得写入 v1 root。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |

## Common Pitfalls

### Pitfall 1: 协议正负例方向反了
**What goes wrong:** 代码接受 `<end_working_out>` 并拒绝 `</end_working_out>`，与 TAG-01/TAG-02 相反。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py; /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py]  
**Why it happens:** v3/v2 历史实现把 bare close tag 写入 `TAG_THINK_CLOSE`，并把 slash close 标成 legacy。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py]  
**How to avoid:** Phase 7 第一批测试必须把 slash close 设为唯一正例，bare close/native think 设为反例。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]  
**Warning signs:** 测试里出现 `assert TAG_THINK_CLOSE == "<end_working_out>"` 或 parser 对 `</end_working_out>` 返回 `None`。[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py]

### Pitfall 2: v3 gate 默认 Qwen3.5 泄漏到 v4 Phase 7
**What goes wrong:** Phase 7 报告显示 Qwen3.5-9B smoke 通过，但这正是 BASE-01 禁止路径。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/env_smoke_v3.py; /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]  
**Why it happens:** v3 gate module、scripts、tests 大量默认 `Qwen/Qwen3.5-9B`。[VERIFIED: grep codebase]  
**How to avoid:** 新建 v4/phase7 namespace 或显式传 `--model Qwen/Qwen3-4B-Thinking-2507` 并在 aggregate report 中拒绝任何 Qwen3.5 string。[ASSUMED]  
**Warning signs:** Artifact path 包含 `v3/phase1`、run root 包含 `v3.0-9B`、report 中 `model` 包含 `Qwen3.5`。[VERIFIED: grep codebase]

### Pitfall 3: chat_template 自动注入 native thinking token
**What goes wrong:** 即使 fixture 文本不含 `<think>`，`apply_chat_template` 也可能自动包含 `<think>`，破坏 TAG-03。[CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507]  
**Why it happens:** Qwen3-4B-Thinking model card 说明 default chat template automatically includes `<think>`。[CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507]  
**How to avoid:** Phase 7 protocol fixture 与后续 dataset/training 使用 raw text path，并在 report 中记录 `chat_template_used=false`。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py]  
**Warning signs:** 代码调用 `tokenizer.apply_chat_template` 或 report 中 `chat_template_used=true`。[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v3_dataset_raw_text.py]

### Pitfall 4: baseline gen_cache 路径命名不一致
**What goes wrong:** Gate 按 CONTEXT 的 `gguf_q4km` 查找会报告缺失，但实际文件系统使用 `gguf_q4_k_m`。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/07-4b-baseline-label-protocol-gate/07-CONTEXT.md; find /home/samuel/TSC_CYCLE/runs/20260507T032419Z/eval/gen_cache]  
**Why it happens:** 文档缩写与实际 eval cache 目录命名不同。[VERIFIED: find /home/samuel/TSC_CYCLE/runs/20260507T032419Z/eval/gen_cache]  
**How to avoid:** Gate 应报告两者：文档期望值与实际发现路径；若需要固定，建议以后续实际路径 `gguf_q4_k_m` 为 baseline cache reference。[ASSUMED]  
**Warning signs:** BASE-03 因 cache 目录缺失失败，但 `find eval/gen_cache -name '*q4*'` 有结果。[VERIFIED: command probes]

### Pitfall 5: Host Python 版本误用
**What goes wrong:** Host `python3` 是 3.14.4，不满足项目 `>=3.12,<3.13`；使用 host Python 可能导致依赖/API 行为与 venv 不一致。[VERIFIED: command probes; /home/samuel/TSC_CYCLE/pyproject.toml]  
**Why it happens:** Shell 默认 `python3` 不等于项目 venv Python。[VERIFIED: command probes]  
**How to avoid:** Scripts 使用固定 venv Python 路径，并在 report 中记录 `sys.executable`。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/env_smoke_v3.py]  
**Warning signs:** report 里 `sys_executable` 不是 `/home/samuel/TSC_CYCLE/.venv/bin/python` 或 `/home/samuel/dgx-spark-setup/.venv/bin/python`。[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/env_smoke_v3.py]

## Code Examples

### Protocol fixture acceptance/rejection contract
```python
# Source: Phase 7 requirement contract derived from /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md
VALID = '<start_working_out>reasoning</end_working_out><SOLUTION>{"1":60}</SOLUTION>'
REJECT_BARE_CLOSE = '<start_working_out>reasoning<end_working_out><SOLUTION>{"1":60}</SOLUTION>'
REJECT_NATIVE = '<start_working_out>bad <think></think></end_working_out><SOLUTION>{"1":60}</SOLUTION>'
```
[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]

### Tokenizer audit with official tokenizer API
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py + HF tokenizer docs
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-4B-Thinking-2507")
ids = tokenizer.encode("</end_working_out>", add_special_tokens=False)
```
[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py; CITED: https://huggingface.co/docs/transformers/main_classes/tokenizer]

### Fail-closed native think leakage check
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py
native_ids = native_think_token_ids(tokenizer)
assert_no_native_think_in_ids(input_ids, native_ids=native_ids)
```
[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py]

### Baseline write-bit evidence
```python
# Source pattern: /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py
write_bits = baseline_path.stat().st_mode & 0o222
if write_bits != 0:
    raise AssertionError("v1 baseline path is writable")
```
[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Qwen3.5-9B local training route | Qwen3-4B-Thinking-2507 v1-validated route | v4.0 roadmap on 2026-05-10 | Phase 7 must reject Qwen3.5 selection and prevent wasting local DGX Spark time.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] |
| Native Qwen `<think>`/`</think>` or chat_template thinking | Custom raw-text tags with native think rejection | Locked by v4.0 TAG requirements | Phase 7 must use raw-text fixture and dynamic native ID audit.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507] |
| Bare close `<end_working_out>` as accepted protocol | Slash close `</end_working_out>` as accepted protocol | v4.0 label protocol repair | Existing code/tests must be inverted before Phase 8 rebuild.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py] |
| v1 baseline as active output target | v1 baseline as frozen read-only reference | v4.0 roadmap | Phase 7 artifacts must live outside `runs/20260507T032419Z/`.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] |

**Deprecated/outdated:**
- `Qwen/Qwen3.5-9B` in v3 gates/scripts is outdated for Phase 7 and must not be selected by Phase 7 gate.[VERIFIED: grep codebase; /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]
- `LEGACY_THINK_CLOSE = "</end_working_out>"` in current code is backwards relative to v4.0 requirements; `</end_working_out>` is the required close marker.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py; /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]
- `apply_chat_template` is inappropriate for Phase 7 protocol fixture because Qwen3-4B-Thinking model card says default chat template automatically includes `<think>`.[CITED: https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 新建 `tsc_cycle/v4_gates/` namespace 比修改 v3 gate 默认值更安全。 | Summary / Architecture Patterns | 若项目偏好复用 v3 namespace，planner 可改路径，但仍必须隔离 artifact 与模型默认值。 |
| A2 | Phase 7 gate artifact 推荐写到 `artifacts/v4/phase7/`。 | Architecture Patterns | 若项目已有隐藏 v4 artifact 标准，路径需调整；不影响 gate 结构。 |
| A3 | baseline cache 最终应采用实际路径 `gguf_q4_k_m`。 | Common Pitfalls | 若用户坚持 CONTEXT 的 `gguf_q4km`，需要创建映射或更新文档，否则 gate 会误报。 |
| A4 | Phase 7 不应要求 secrets，也不应读取 sensitive env values。 | Runtime State Inventory | 若后续把 API smoke 纳入 Phase 7，需新增 secret handling，但这会超出当前 ROADMAP。 |

## Open Questions (RESOLVED)

1. **RESOLVED: 协议关闭标签以 slash close `</end_working_out>` 为唯一正确值。**
   - What we know: v4.0 REQUIREMENTS 明确 TAG-02 要把错误 `<end_working_out>` 规范化为 `</end_working_out>`，用户 additional_context 也写“corrected `</end_working_out>` protocol”。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; user prompt]
   - Decision: Planner and executor must treat `</end_working_out>` as the only valid thought closing marker, and must treat bare close `<end_working_out>` as a malformed negative fixture.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]

2. **RESOLVED: v1 gen_cache 以实际发现路径为准，同时在报告中记录文档路径不匹配。**
   - What we know: CONTEXT/STATE 提到 `gguf_q4km`，实际存在目录是 `gguf_q4_k_m`，`gguf_q4km` 不存在。[VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md; find/stat command]
   - Decision: Phase 7 report must record `documented_path_exists=false` for `runs/20260507T032419Z/eval/gen_cache/gguf_q4km`, record `discovered_q4_cache=runs/20260507T032419Z/eval/gen_cache/gguf_q4_k_m`, and downstream Phase 11 should consume the discovered path unless later artifacts supersede it.[ASSUMED]

3. **RESOLVED: `/home/samuel/dgx-spark-setup/.venv` 缺少 bnb/trl 是 Phase 7 warning，不触发安装或升级。**
   - What we know: 该 venv Python 存在并为 3.12.3，但 `bitsandbytes` 与 `trl` package metadata 缺失；项目 venv 中二者存在。[VERIFIED: command probes]
   - Decision: Phase 7 must only report both venv package matrices and warnings; it must not install or upgrade packages. Phase 9 owns any training-runtime dependency closure before full QLoRA training.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `/home/samuel/TSC_CYCLE/.venv/bin/python` | pytest/gate execution | ✓ | Python 3.12.3 | Use this for Phase 7 local tests.[VERIFIED: command probes] |
| `/home/samuel/dgx-spark-setup/.venv/bin/python` | BASE-02 environment reference | ✓ | Python 3.12.3; torch 2.11.0+cu130; transformers 5.8.0; bnb/trl missing | Report as warning; do not install in Phase 7.[VERIFIED: command probes] |
| `pytest` | Validation Architecture | ✓ | 9.0.3 installed | Use venv pytest/module invocation.[VERIFIED: command probes] |
| `uv` | package management if later needed | ✓ | 0.9.10 | No install needed in Phase 7.[VERIFIED: command probes] |
| NVIDIA GPU | Environment evidence | ✓ | NVIDIA GB10, driver 580.126.09 | Phase 7 should not require model load; GPU fact only evidence.[VERIFIED: command probes] |
| `scripts/dgx_spark/run_safe.sh` | DGX safe-wrapper evidence | ✓ | project script present | Use only if gate includes scope check; otherwise record path presence.[VERIFIED: command probes] |
| v1 q4 baseline artifact | BASE-03 | ✓ | 2,497,280,160 bytes, read-only file | None; blocking if missing.[VERIFIED: stat /home/samuel/TSC_CYCLE/runs/20260507T032419Z/gguf/model.q4_K_M.gguf] |
| v1 q4 gen_cache | BASE-03/Phase 11 handoff | Partial | actual `gguf_q4_k_m` exists; documented `gguf_q4km` absent | Discover actual path and report mismatch.[VERIFIED: find/stat command] |

**Missing dependencies with no fallback:**
- None for Phase 7 if it is implemented as code/config/tokenizer/baseline gate without full training smoke.[ASSUMED]

**Missing dependencies with fallback:**
- `bitsandbytes` and `trl` missing in `/home/samuel/dgx-spark-setup/.venv`; fallback is to report package matrix and defer training dependency resolution to Phase 9, while using project `.venv` for Phase 7 tests.[VERIFIED: command probes; ASSUMED]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 installed; project `pyproject.toml` uses pytest testpaths `tests` and `-q` addopts.[VERIFIED: command probes; /home/samuel/TSC_CYCLE/pyproject.toml] |
| Config file | `/home/samuel/TSC_CYCLE/pyproject.toml`[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Quick run command | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v4_phase7_protocol.py tests/test_v4_phase7_baseline_gate.py tests/test_v4_phase7_tokenizer_audit.py`[ASSUMED] |
| Full suite command | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q`[VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BASE-01 | exactly `Qwen/Qwen3-4B-Thinking-2507` accepted; Qwen3.5 rejected | unit | `pytest tests/test_v4_phase7_baseline_gate.py::test_model_lock_rejects_qwen35 -q` | ❌ Wave 0[VERIFIED: no existing file in find output] |
| BASE-02 | environment report records expected venvs/package versions and does not mutate/install | unit/smoke | `pytest tests/test_v4_phase7_baseline_gate.py::test_environment_report_is_read_only -q` | ❌ Wave 0[ASSUMED] |
| BASE-03 | baseline root before/after snapshot unchanged and output paths outside v1 root | unit | `pytest tests/test_v4_phase7_baseline_gate.py::test_v1_baseline_readonly_snapshot -q` | ❌ Wave 0[ASSUMED] |
| TAG-01 | parser/builders accept only slash close protocol | unit | `pytest tests/test_v4_phase7_protocol.py::test_accepts_slash_close_protocol -q` | ❌ Wave 0; current `test_prompt_builder.py` has opposite expectations[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py] |
| TAG-02 | bare close `<end_working_out>` rejected as malformed fixture | unit | `pytest tests/test_v4_phase7_protocol.py::test_rejects_bare_close_protocol -q` | ❌ Wave 0[ASSUMED] |
| TAG-03 | native `<think>`/`</think>` rejected in inputs/outputs and chat_template not used | unit | `pytest tests/test_v4_phase7_protocol.py::test_rejects_native_think_anywhere -q` | ❌ Wave 0; partial raw-text tests exist for v3 dataset path[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v3_dataset_raw_text.py] |
| TAG-04 | tokenizer audit records native IDs dynamically and custom tags multi-token for Qwen3-4B | unit/smoke | `pytest tests/test_v4_phase7_tokenizer_audit.py::test_tokenizer_audit_payload_contract -q` | ❌ Wave 0; helper tests exist for fake tokenizer[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_tokenizer_check.py] |

### Sampling Rate
- **Per task commit:** quick Phase 7 pytest subset plus `tests/test_prompt_builder.py` after protocol constants are corrected。[ASSUMED]
- **Per wave merge:** full pytest suite; existing lightweight subset ran green in research: `tests/test_prompt_builder.py tests/test_tokenizer_check.py tests/test_v3_env_gate.py tests/test_v3_phase1_report.py` returned 32 passing dots.[VERIFIED: pytest command]
- **Phase gate:** `phase7_gate_report.json` must have `ok=true`, all seven requirements covered, and `next_phase_allowed=true` before `/gsd-verify-work`。[ASSUMED]

### Wave 0 Gaps
- [ ] `tests/test_v4_phase7_protocol.py` — covers TAG-01/TAG-02/TAG-03 and intentionally flips current wrong expectations.[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_prompt_builder.py]
- [ ] `tests/test_v4_phase7_baseline_gate.py` — covers BASE-01/BASE-02/BASE-03 and cache path mismatch reporting.[ASSUMED]
- [ ] `tests/test_v4_phase7_tokenizer_audit.py` — covers TAG-04 payload contract with fake tokenizer plus optional live Qwen3-4B smoke mark.[ASSUMED]
- [ ] `scripts/run_v4_phase7_gate.sh` — fixed argv wrapper, no installs, writes only `artifacts/v4/phase7/`.[ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth/session surface in Phase 7 local gate.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| V3 Session Management | no | No web/session state.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| V4 Access Control | yes | Filesystem path guard: refuse output paths under v1 baseline root and report write bits.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |
| V5 Input Validation | yes | Validate model ID, protocol fixtures, path roots, JSON report schema, and native tag rejection.[VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |
| V6 Cryptography | yes | Use SHA-256 only for artifact integrity evidence; do not invent custom hashes.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py; /home/samuel/TSC_CYCLE/tsc_cycle/student/sft_v3.py] |

### Known Threat Patterns for local gate scripts

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal / writing into frozen baseline | Tampering | Resolve paths and reject any output path under `/home/samuel/TSC_CYCLE/runs/20260507T032419Z`.[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py] |
| Shell injection in wrapper args | Elevation of Privilege | Fixed argv arrays; reject shell metacharacters as existing v3 training wrapper/tests do.[VERIFIED: /home/samuel/TSC_CYCLE/tests/test_v3_sft_frozen.py; /home/samuel/TSC_CYCLE/scripts/run_v3_phase4_dry_run.sh] |
| Native thinking token leakage | Information Disclosure / Tampering | Dynamic native ID set plus literal `<think>`/`</think>` rejection in input/output fixtures.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py] |
| Environment drift hidden by successful console output | Repudiation | JSON artifact records executable paths/package versions and warnings; no console-only gate.[VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py] |

## Sources

### Primary (HIGH confidence)
- `/home/samuel/TSC_CYCLE/.planning/phases/07-4b-baseline-label-protocol-gate/07-CONTEXT.md` — Phase 7 locked decisions, discretion, deferred scope.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md` — BASE/TAG requirements and out-of-scope constraints.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/ROADMAP.md` — Phase 7 success criteria and phase boundaries.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/STATE.md` — v4 current state, v1 baseline metrics/path, route decisions.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/CLAUDE.md` — project constraints and DGX/vLLM/tokenizer requirements.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py` — current protocol constants/parser and current reversal bug.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/tokenizer_check.py` — dynamic tokenizer/native ID helper implementation.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase1_report.py` — aggregate gate/report pattern.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/env_smoke_v3.py` — v3 default Qwen3.5 model identity pattern to adapt, not reuse blindly.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tests/test_prompt_builder.py` — existing tests currently assert the wrong closing tag direction for v4.[VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tests/test_tokenizer_check.py` — fake-tokenizer dynamic native ID tests.[VERIFIED: Read]
- Filesystem probes under `/home/samuel/TSC_CYCLE/runs/20260507T032419Z` — baseline artifact exists/read-only and gen_cache path naming.[VERIFIED: Bash stat/find]
- [Qwen/Qwen3-4B-Thinking-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507) — exact model ID, Causal LM, transformers minimum, default chat template thinking behavior, native `</think>` ID example.[CITED: huggingface.co]
- [Transformers tokenizer docs](https://huggingface.co/docs/transformers/main_classes/tokenizer) — `AutoTokenizer.from_pretrained`, `encode`, `add_special_tokens` behavior.[CITED: huggingface.co]
- Context7 `/huggingface/transformers` docs query — chat templating and tokenizer references.[VERIFIED: Context7 CLI]

### Secondary (MEDIUM confidence)
- PyPI version probes via `python3 -m pip index versions transformers pytest torch` — current package versions at research time.[VERIFIED: command probes]
- Local venv package probes with `importlib.metadata` — installed package matrix for project and dgx venvs.[VERIFIED: command probes]

### Tertiary (LOW confidence)
- None; assumptions are isolated in Assumptions Log.[VERIFIED: Assumptions Log]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — package versions verified locally and current package versions probed; no new dependency required.[VERIFIED: command probes]
- Architecture: HIGH — derived from existing v3 gate/report code and Phase 7 requirements.[VERIFIED: codebase reads]
- Pitfalls: HIGH — major pitfalls are direct contradictions found in code/tests/filesystem vs requirements.[VERIFIED: grep/read/stat]
- External docs: HIGH for tokenizer/model-card facts; official HF docs/model card were fetched during research.[CITED: huggingface.co]

**Research date:** 2026-05-10  
**Valid until:** 2026-05-17 for package/version environment facts; 2026-06-09 for internal architecture findings unless planning files change.[ASSUMED]
