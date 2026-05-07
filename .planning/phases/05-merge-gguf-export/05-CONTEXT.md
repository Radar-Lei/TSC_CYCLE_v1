---
phase: 5
status: ready_for_planning
mode: skip_discuss (auto-generated)
gathered: 2026-05-07
---

# Phase 5: Merge + GGUF Export - Context

<domain>
## Phase Boundary

LoRA adapter merge 到 bf16 base（**非 4-bit**），转 GGUF bf16 与 Q4_K_M，三精度 parity 验证学生在量化后数值漂移可控。

**Success Criteria** (来自 ROADMAP):
1. `runs/{ts}/merged_bf16/` 存在（bf16 reload + LoRA merge_and_unload，**不是** 4-bit base merge），vocab_size = 151936（无 embedding resize）
2. `runs/{ts}/gguf/model.bf16.gguf`（本机 EvoProgTSC/llama.cpp `convert_hf_to_gguf.py`）+ `runs/{ts}/gguf/model.q4_K_M.gguf`（`llama-quantize` preset 15）写出
3. GGUF tokenize sanity：`llama-tokenize` 对四个自定义标签输出与 HF tokenizer 一致的多 sub-token 序列
4. 20-prompt greedy（seed=42, temperature=0.0）parity 测试：HF bf16 vs GGUF bf16 vs GGUF q4_K_M，q4_K_M 对 HF bf16 SOLUTION 数值 MAE ≤ 3s（>3s 触发 imatrix 重量化预案）

</domain>

<existing_state>
## 已有产物（来自 watchdog 第一次运行 TS=20260507T032419Z）

| Artifact | Path | Status |
|---|---|---|
| Merged bf16 HF dir | `runs/20260507T032419Z/merged_bf16/` | ✓ 完整（含 model.safetensors, config.json, tokenizer_config.json, chat_template.jinja） |
| GGUF bf16 | `runs/20260507T032419Z/gguf/model.bf16.gguf` (7.5G) | ✓ 写出 |
| GGUF q4_K_M | `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (2.4G) | ✓ 写出 |
| `export_summary.json` | `runs/20260507T032419Z/export_summary.json` | ✓ 写出 |
| GGUF tokenize sanity check | — | ❌ 未执行 |
| 20-prompt parity test | — | ❌ **失败：llama-cli 180s 超时** |

**Sub-criteria 1 / 2 已满足**；剩 **3 (tokenize sanity)** 与 **4 (parity)** 未达成。

</existing_state>

<known_failure>
## 已知失败：parity test llama-cli 超时

**症状：** watchdog 在第 1 个 prompt 上调用 `llama-cli -m model.bf16.gguf -p '<2KB Chinese prompt>' -n 768 --temp 0 --top-k 1 --seed 42 --no-display-prompt` 时 `subprocess.TimeoutExpired: ... timed out after 180 seconds`。

**可能根因：**
1. CPU-only 推理：watchdog 可能没传 `-ngl <N>` 把 layer 卸载到 GPU，bf16 7.5G 模型在 CPU 上 768 token greedy 极慢（远超 180s）
2. 无 GPU 卸载：本机 GB10 有 GPU，应使用 `-ngl 99` 全卸载（学生 4B 完全可放进 GPU）
3. 首次启动有 model warm-up + KV cache 分配开销
4. prompt 太长（~2KB）+ n_predict=768 导致 token budget 大

**修复路径（plan 阶段决定）：**
- A. 加 `-ngl 99 --threads 4` 让 GPU 接管，预期 768 token < 30s
- B. 把 timeout 从 180s 提到 600s（保险但治标不治本）
- C. 缩短 n_predict（评测语境下 256-384 已够 SOLUTION 输出）
- D. 同时实现 `llama-tokenize` sanity check（criterion 3）

</known_failure>

<decisions>
## Implementation Decisions

### Claude's Discretion
- Phase 5 不重做 merge 与 quantize（产物已通过 sub-criteria 1+2，重做浪费 5min+）
- **直接重跑** parity 测试，但用修过的 llama-cli 调用（带 GPU 卸载）
- tokenize sanity check 用本机 `EvoProgTSC/llama.cpp/build/bin/llama-tokenize` 跑四个自定义标签
- 输出 `runs/20260507T032419Z/gguf/parity_report.json`（含 per-prompt MAE、HF/bf16/q4_K_M 三方 SOLUTION 字典）
- 若 q4_K_M MAE > 3s，记录到 STATE.md 并提示 imatrix 重量化（不在 Phase 5 内完成；属 backlog）

### From CLAUDE.md
- 不重新装 PyTorch / vllm / flash-attn
- 训练/推理脚本必须可在 `.venv` 内直接 `python -m ...`
- DGX Spark unified memory 风险：parity 是推理而非训练，不强制 `systemd-run`，但 swap 应保持 off

</decisions>

<code_context>
## Existing Code Insights

- `tsc_cycle/student/export_gguf.py`（已存在，watchdog 调用过）：负责 merge + convert + quantize；产物已生成
- `tsc_cycle/student/parity.py`（推测路径，待 plan 验证存在性）：parity 测试入口；当前不带 `-ngl` 是疑似 bug
- `scripts/run_export_eval_watchdog.sh`：含失败的 llama-cli 调用栈
- `EvoProgTSC/llama.cpp/build/bin/llama-cli` 与 `llama-tokenize`：本机已 build，二进制可用
- `tsc_cycle/shared/prompt_builder.py`：所有 prompt 构造统一入口，HF 与 GGUF 路径必须共用

</code_context>

<specifics>
## Specific Ideas

1. **修 parity 调用的 llama-cli 命令**：plan 阶段定位 `parity.py`（或 watchdog 嵌入的代码），加 `-ngl 99` + 提高 timeout 至 600s 双重保险
2. **tokenize sanity 单独实现**：调用 `llama-tokenize` 四个自定义标签 + 原生 `<think>`/`</think>`，与 HF tokenizer 对比，写 `gguf/tokenize_sanity.json`
3. **20-prompt 选取**：从 `data/labeled.jsonl` 取 10 个 same-distribution + 10 个 OOD（`split_hint` 字段），seed=42 抽样，固化 sample_id 列表到 `runs/{ts}/gguf/parity_prompts.jsonl`
4. **三精度对齐**：HF bf16 用 `merged_bf16/`（transformers AutoModelForCausalLM bf16 + SDPA）；GGUF 两个用 llama-cli
5. **MAE 计算**：解析每个响应中 `<SOLUTION>{...}</SOLUTION>` JSON，按 phase_id 对齐计算每相位 |bf16 - q4| 的均值；若 SOLUTION 解析失败计入 parse_failure 字段
6. **不写 PHASE 5 imatrix 路径**：MAE >3s 时仅 flag，留 backlog；imatrix 流程在 Phase 5 之外

</specifics>

<deferred>
## Deferred Ideas

- imatrix 重量化（仅 MAE > 3s 时触发，属于条件 backlog）
- 学生 chat_template 与 GGUF metadata 一致性（运行期 OK 即可，不在 Phase 5 success criteria）
- llama-server HTTP 模式 parity（CLI 模式已够用）

</deferred>
