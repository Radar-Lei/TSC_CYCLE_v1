# Project Research Summary — TSC-CYCLE v3.0 9B 基座切换

**Project:** TSC-CYCLE — Qwen3.5-9B 学生模型蒸馏（v1.0 4B-Thinking → v3.0 9B 基座切换）
**Domain:** LLM 蒸馏离线批处理流水线 / QLoRA SFT / GGUF 本地部署
**Researched:** 2026-05-08
**Confidence:** **MEDIUM-HIGH**（环境/llama.cpp 注册/教师 pipeline HIGH；9B 显存峰值与 GatedDeltaNet 在 q4_K_M 下的保真度 MEDIUM-LOW，依赖 Phase 1 dry-run 兜底）

## Executive Summary

v3.0 是「**只换学生基座，其他全部冻结**」的增量里程碑：教师（GPT-5.5 high）、`data/labeled.jsonl`（v1.0 已 SHIPPED ~2700+ valid 样本）、80/10/10 split (seed=42)、prompt 协议（v2.0 Phase 7 锁定的 `<end_working_out>` 标签形式）、评测套件、GGUF 导出脚本、`/dgx-spark-training` 训练栈、本机 venv 全部沿用。**变更面集中在三处**：(1) 训练 batch_size 从 4 锁到 1 + grad_accum 调到 16；(2) tokenizer 从 Qwen3 (vocab 152K) 切到 Qwen3.5 (vocab 248K)、token id 全部偏移、自定义思考标签拆分行为需重新实测；(3) 评测加 v1.0 q4_K_M 作为第 4 个 baseline variant，决策门改为「v3 vs v1 ratio ≥ 1.0」三阈值并存。

**推荐方案**：完全沿用本机 `/home/samuel/TSC_CYCLE/.venv`（实测已 transformers 5.8.0 / peft 0.19.1 / trl 1.3.0 / bnb 0.48.0 / torch 2.11.0+cu130，远高于 Qwen3.5 最低要求 transformers ≥5.2.0）；本机 llama.cpp（`/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py:5036`）已注册 `Qwen3_5ForCausalLM` 并继承 `_LinearAttentionVReorderBase` 处理 GatedDeltaNet 张量重排；零安装零环境变更。建议 5-phase roadmap：**P1 Env+Tokenizer+Memory+llama.cpp 四合一硬门禁（不通过则 abort）→ P2 Dataset Rebuild（仅 retokenize，labeled.jsonl 不动）→ P3 QLoRA SFT（lr=1e-4 / alpha=64 / max_grad_norm=0.5 三件套，配合 200-step dry-run 与 500-sample 早期 OOD 验证）→ P4 Merge+GGUF Export（含 imatrix 校准，q4_K_M 在 GatedDeltaNet 上是 v3.0 新风险）→ P5 Eval Matrix + 三阈值决策门**。

**关键风险与缓解**：(a) **9B "贴合常识"反向 OOD 退化**——9B 世界知识可能让模型对 `min_green<15s` 这类 OOD 主动违反硬约束；用 500-sample 1h 缩比 dry-run 在投入 6h 全量训练前 early-exit；(b) **GatedDeltaNet 24/32 层在 q4_K_M 上的保真度未在 v1.0 dense Qwen3 上验证过**，必跑 imatrix（不再可选）+ 5-prompt smoke + 全 OOD eval 对比 fp16；(c) **target_modules 如沿用 v1.0 显式 7-projection 列表会漏 24 个 GatedDeltaNet linear-attention 层**，必须 dry-run 后改 `all-linear` 或扩展显式列表；(d) **9B 最大单点风险是自定义标签被 248K vocab 的 BPE merge 合并成单 token**——5 秒实测可决定，硬门禁。

## 跨研究文件不一致项的统一裁决

### 不一致 1：本机 transformers 实际版本
- STACK 实测 5.8.0 / peft 0.19.1 / trl 1.3.0；PITFALLS 建议锁 4.56.2（v1.0 文本快照）。
- **裁决**：4.56.2 不识别 `qwen3_5` model_type → 9B 加载直接 fail；**采用本机实测 5.8.0**，PITFALLS 该项过时。CLAUDE.md STACK section 待 v3.0 完成后刷新。

### 不一致 2：vocab 248K 可信度
- STACK 直接拉 config.json：`vocab_size=248320` (HIGH)；FEATURES 早期判定 LOW（已被驳回）；PITFALLS 与 STACK 一致。
- **裁决**：**vocab=248320 是 HIGH confidence 事实**；自定义标签拆分行为仍需 P1 实测确认（STACK 已离线观察 4 标签拆 3-5 sub-tokens，最终以 P1 audit 为准）。

### 不一致 3：9B 训练显存预算
- STACK：18-25 GB peak（不含 vision 误加载，含 OS headroom 后 ~30-40 GB）；假设 grad_ckpt ON、max_seq=2048、bs=1、AdamW8bit paged、GatedDeltaNet 24/32 层无 KV cache、bnb 不量化 embedding。
- PITFALLS/FEATURES/ARCHITECTURE：50-75 GB peak；假设含 dequant 临时 buffer + LoRA 7 模块全量。
- **裁决**：两端共识 100GB cap 内有头室；**P1 必跑 `memory_budget_v3.py`** 在 5 候选 max_seq ∈ {1536, 2048, 2560, 3072, 4096} 实测 peak，选 peak<85GB 最大值。预期落点 35-55 GB。

### 不一致 4：本机 llama.cpp 是否已支持 Qwen3.5
- STACK/ARCHITECTURE：直接 grep 验证 line 5036 已注册（HIGH）。
- PITFALLS 9-5：担忧 EvoProgTSC build 早于 Qwen3.5 release。
- **裁决**：**已支持，无需 rebuild**；PITFALLS 担忧已被 grep 证据驳回。P1 仍跑 5min micro-convert dry-run 作防御性硬门禁（dummy LoRA → bf16 GGUF → q4_K_M GGUF → llama-cli 推理 5 token + HF/llama-tokenize parity）。

## Key Findings

### Recommended Stack
完全沿用本机 venv 零变更。Core: Python 3.12 / PyTorch 2.11.0+cu130 / Transformers 5.8.0 / TRL 1.3.0 / PEFT 0.19.1 / bitsandbytes 0.48.0 / OpenAI SDK ≥1.50 / 本机 llama.cpp（line 5036 注册 Qwen3_5ForCausalLM）/ systemd-run --scope MemoryMax=100G + swap off。详见 STACK.md。

### Expected Features
v3.0 只覆盖切换增量；v1.0 已验证特性原样保留。

**Must have (P1 hard gates):** F-T2 Tokenizer audit / F-T3 标签拆分不退化 / F-G1+G2 llama.cpp Qwen3.5 + GatedDeltaNet GGUF / F-M1+M2 9B 显存实测 + multimodal text-only 加载 / F-TH1-3 thinking 适配（绕开 chat_template, raw text 拼接, logit-bias 屏蔽 native think）/ F-G3 q4_K_M 在长 thinking 链稳定性。

**Should have:** F-D2 imatrix 校准（v3.0 升为必须）/ F-D4 v1.0 vs v3.0 delta + 95% bootstrap CI / F-D1 max_seq → 4096（视显存）。

**Defer:** F-D3 量化分级 / F-D5 thinking on-off 双跑 / F-D6 样本扩到 6000。详见 FEATURES.md。

### Architecture Approach
**Frozen-Data, Floating-Base Distillation Refresh**：6-stage 流水线骨架完全可复用。变更集中在 (Stage 4 训练参数 + Stage 6 评测对比表)。

主要组件:
1. **Stage 3 Dataset Builder** — `MODEL_NAME` 切 9B、retokenize、`data/tokenized/v3/` 与 v1.0 隔离、split seed=42 哈希校验
2. **Stage 4 Trainer** — bs=1 + grad_accum=16 / lr=1e-4 / alpha=64 / scheduler=cosine / use_reentrant=False / target_modules="all-linear"（**绝不**沿用 v1.0 显式列表）
3. **Stage 6 Evaluator** — 4 variant matrix（hf_bf16_v3 / gguf_q4_v3 / gguf_q4_v1_baseline read-only mount / optional gguf_fp16_v3）+ ratio_vs_v1 + p99/max-abs tail metrics
4. **Decision Gate** — 三阈值并存：`q4_v3 vs fp16_v3 ≥ 0.95` AND `q4_v3 vs q4_v1 ≥ 1.00` AND `q4_v3 hard_constraint_pass ≥ 98%`

Run path 强制 `runs/v3.0-9B-<timestamp>/`；v1.0 production artifact `runs/20260507T032419Z/` 标记 FROZEN.md + chmod -w。详见 ARCHITECTURE.md。

### Critical Pitfalls (Top 5 — P1 hard gates)
1. **Pitfall 9-1: 自定义标签被 248K vocab 合并成单 token** — 5 秒实测决定 v3.0 假设；备选标签池 `<<TSC_PLAN>>` 等 fallback。**Phase: P1**
2. **Pitfall 9-5: llama.cpp Qwen3.5 GGUF 全链路** — grep + micro-convert dry-run；line 5036 已 grep 命中。**Phase: P1**
3. **Pitfall 9-4: 9B + max_seq 显存峰值非线性** — 5 候选 seq 实测；use_reentrant=False；优先 adamw_torch_fused 避免 8-bit underflow。**Phase: P1+P3**
4. **Pitfall 9-6: "9B 优于 4B" 免费午餐幻觉 / OOD 反向退化** — 500-sample 1h 缩比 dry-run；P5 决策报告必须含 v3-v1 差值 + 95% bootstrap CI + p99/max-abs tail metrics。**Phase: P3+P5**
5. **Pitfall 9-2: native `<think>` 泄漏（id 偏移到 248068）** — 绕开 chat_template + 动态查表 logit-bias（**绝不**硬编码 151667/151668）+ smoke 断言无 `<think>`。**Phase: P1+P3+P4**

详见 PITFALLS.md（v3.0 8 条新增 + v1.0 8 条继承）。

## Implications for Roadmap

### Phase 1: Env + Tokenizer + Memory + llama.cpp 四合一硬门禁
**Rationale:** 4 项必须在投入训练前同时解决；任一失败 fallback 决策树清晰；总耗时 ≤1 day GPU。
**Delivers:** tokenizer_audit.json / memory_budget.csv / llama_cpp_microconvert.log / forward_smoke.log / 选定 max_seq_length（预期 2048-2560）
**Addresses:** F-T2/T3, F-G1/G2, F-M1/M2, F-V1-V4
**Avoids:** Pitfalls 9-1, 9-2, 9-4, 9-5
**Exit (fatal gates):** 4 标签全部 ≥3 sub-tokens / forward smoke peak<85GB / llama-tokenize ↔ HF tokenize 一致 / micro-convert 5-token 推理无 segfault

### Phase 2: Dataset Rebuild
**Rationale:** P1 通过后纯 CPU (<10min)；与 P3 解耦保护 6h GPU 预算；split seed=42 严格命中 v1.0 同集合。
**Delivers:** `data/tokenized/v3/{train,val,ood_val}.arrow` + p99 token 长度统计
**Implements:** Stage 3 Dataset Builder（仅改 MODEL_NAME 常量）
**Exit:** split 哈希匹配 v1.0 / 截断率 ≤5% / labeled.jsonl 未变（git diff clean）

### Phase 3: QLoRA SFT (9B, batch=1) + 500-sample dry-run + full 6h
**Rationale:** P3 是唯一 6h GPU bottleneck；500-sample 1h dry-run 早期 early-exit；超参三件套 lr=1e-4/alpha=64/max_grad_norm=0.5 不同于 v1.0。
**Delivers:** `runs/v3.0-9B-<ts>/lora/` adapter + wandb run + grad_norm jsonl
**Implements:** Stage 4 Trainer（bs=1, grad_accum=16, target_modules="all-linear", lora_dropout=0.0, use_reentrant=False, save_steps=200）
**Avoids:** Pitfalls 9-3, 9-6, 9-8
**Exit:** 200-step grad_norm p99<3.0 + 无 NaN / 500-sample dry-run OOD 硬约束 ≥95% / 全量 SFT 6h 内 2 epoch / 无 unrecovered loss spike

### Phase 4: Merge + GGUF Export + imatrix
**Rationale:** Export 与训练解耦；imatrix 在 v3.0 升级为必须（GatedDeltaNet 24/32 层 q4_K_M 保真度未验证）。
**Delivers:** merged_bf16/ + model.fp16.gguf (~18GB) + model.q4_K_M.gguf (~5.5GB) + imatrix.dat + 20-prompt parity smoke report
**Implements:** Stage 5 Exporter（v1.0 流程 + imatrix 必跑）
**Exit:** 5-prompt smoke 三精度均生成合法 SOLUTION 段 / llama-tokenize ↔ HF tokenize parity

### Phase 5: Eval Matrix + 三阈值决策门
**Rationale:** 评测扩展独立节奏；v1.0 baseline gen_cache read-only mount 不重跑；跨里程碑严格可比。
**Delivers:** report.md + decision.md + per_sample.jsonl + 含 v3-v1 差值 95% bootstrap CI + p99/max-abs tail metrics
**Implements:** Stage 6 Evaluator + 三阈值 Decision Gate
**Exit:** 600 prompt × 3 variant 完成（v1 mount） / decision.md 给出 GO/NO-GO/用户决策三态结论

### Phase Ordering Rationale
- P1 在 P2 前：tokenizer 失败必须早 abort
- P2 与 P3 解耦：保护 6h GPU 预算
- P4 单独 phase：GatedDeltaNet GGUF 失败需独立调试
- P5 拆出：v1 baseline mount 保跨里程碑可比
- Critical path: P3 是唯一 6h GPU bottleneck

### Phases NOT Needed
- 数据生成 phase（v1.0 SHIPPED）
- 教师重标 phase（教师固定，重调引入随机性）
- v2.0 Phase 7 标签迁移（已落地，与 v3.0 兼容）

### Research Flags
- **P1 (强)**：4 硬门禁是成败核心；GatedDeltaNet bs=1 显存无 Spark 公开实测，建议 P1 plan 时 light research（Unsloth Qwen3.5 docs / llama.cpp Qwen3.5 issues）
- **P3 (中)**：500-sample dry-run OOD 阈值 95%/90% 是研究推断，无 9B-on-TSC 公开数据
- **P4 (中)**：imatrix 校准集大小（50/100/200）对 GatedDeltaNet q4_K_M 影响无公开数据
- **Standard patterns (skip research):** P2（标准 retokenize）、P5（v1.0 evaluator 增量）

## Hard NOT-TODO List (v3.0 锁定)

| 禁止项 | 原因 |
|--------|------|
| `batch_size > 1` | PROJECT.md 用户明确锁定 |
| 重装 transformers/peft/trl/bnb | 本机 venv 已 Qwen3.5-ready |
| `transformers==4.56.2` | 不识别 `qwen3_5`，9B 直接 fail |
| 沿用 v1.0 硬编码 think id 151667/151668 | Qwen3.5 偏移到 248068/248069；必须动态查表 |
| 沿用 v1.0 显式 target_modules 7-proj 列表 | 漏 24 个 GatedDeltaNet 层；必须 all-linear |
| 沿用 v1.0 lr=2e-4 / alpha=128 | 9B + bs=1 必踩 loss spike；锁 lr=1e-4/alpha=64/max_grad_norm=0.5 |
| Qwen3.5-9B-Instruct 的 native `<think>` 模式 | 与 v1.0 同陷阱 |
| `Qwen3_5ForConditionalGeneration` 加载 | 浪费 0.8GB + mrope_section 干扰；用 Qwen3_5ForCausalLM |
| chat_template 拼训练数据 | `<think>` 注入；raw text 起手 `<start_working_out>` |
| add_special_tokens=True 把标签加 vocab | resize_token_embeddings → q4_K_M 崩塌 |
| packing=True | 跨 `</SOLUTION>` 边界破坏思考结构 |
| swap 开 / 不用 systemd-run | UMA 死亡螺旋；9B 比 4B 更敏感 |
| 重调 GPT-5.5 重生成 labeled.jsonl | 引入随机性 → v1/v3 不可比 |
| split seed != 42 | ratio_vs_v1 含义漂移 |
| 写 `runs/<timestamp>/` 不带 v3.0 prefix | 与 v1.0 production artifact 混淆 |
| flash-attn / vLLM / Unsloth / Axolotl | PROJECT.md Out of Scope / 本机不可用 |
| Qwen3.6 / 全参 SFT | PROJECT.md Out of Scope |
| wandb 同 v1.0 project | 9B vs 4B token-level CE 系统性差 ~0.5 nat → 误读；用 `tsc-cycle-v3-9b` 隔离 |
| 跳过 P1 直接 P3 | 5 秒 tokenizer 实测保 6h 训练 |

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | 本机 venv import 实测；llama.cpp line 5036 grep；config.json HIGH source |
| Features | **MEDIUM-HIGH** | 架构/thinking HIGH；标签拆分 STACK 离线实测，P1 复现确认；vocab 248K 已升级 HIGH |
| Architecture | **HIGH** | v1.0 SHIPPED；变更面集中；llama.cpp 注册直接证据；Frozen-Data 模式跨基座已实证 |
| Pitfalls | **HIGH (列表) / MEDIUM (缓解)** | v1.0 8 + v3.0 8 条；9B + GatedDeltaNet + bs=1 在 Spark 无公开数据，P1 dry-run 兜底 |

**Overall: MEDIUM-HIGH。** 唯一 LOW 区是 GatedDeltaNet 在 q4_K_M 下保真度（v3.0 新风险），通过 imatrix 必跑 + tail metrics + decision gate 三层防御覆盖。

### Gaps to Address
- 9B + GatedDeltaNet + bs=1 在 Spark peak memory 无公开数据 → P1 memory_budget_v3.py 5 候选实测
- q4_K_M 在 GatedDeltaNet 24/32 层保真度无 v1.0 经验 → imatrix 必跑 + 三阈值决策；崩塌回 q5_K_M (+25% size)
- Qwen3.5 native `<think>` 在 248K vocab 精确 id → P1 动态查表写入 audit.json
- target_modules="all-linear" 在 GatedDeltaNet 命名下命中数 → P3 dry-run 枚举 model.named_modules()
- 500-sample OOD 阈值 95%/90% 是推断 → P3 plan light research
- v1.0 split 索引文件是否仍在仓库 → P2 退出门显式校验，丢失则 git log 恢复

## Sources

### Primary (HIGH)
- 本机 `/home/samuel/TSC_CYCLE/.venv` 实测 — transformers 5.8.0 / peft 0.19.1 / trl 1.3.0 / bnb 0.48.0 / torch 2.11.0+cu130
- 本机 `/home/samuel/projects/EvoProgTSC/llama.cpp/convert_hf_to_gguf.py:5036` — Qwen3_5ForCausalLM + Qwen3_5TextModel(_LinearAttentionVReorderBase)
- [Qwen/Qwen3.5-9B/config.json](https://huggingface.co/Qwen/Qwen3.5-9B/raw/main/config.json) — vocab=248320 / 32 layers / hidden=4096 / 24 linear+8 full
- [Qwen3.5-9B HF model card](https://huggingface.co/Qwen/Qwen3.5-9B), [transformers qwen3_5 doc](https://huggingface.co/docs/transformers/main/model_doc/qwen3_5) — 最低 5.2.0
- v1.0 SHIPPED `.planning/milestones/v1.0-ROADMAP.md`；v2.0 abandoned Phase 7 SUMMARY (29 测试 PASS)
- `/home/samuel/.claude/skills/dgx-spark-training/SKILL.md`；[natolambert/dgx-spark-setup](https://github.com/natolambert/dgx-spark-setup)
- [Unsloth Qwen3.5 fine-tune docs](https://unsloth.ai/docs/models/qwen3.5/fine-tune) — bf16 LoRA 9B peak 22GB
- [QLoRA paper arXiv:2305.14314](https://arxiv.org/pdf/2305.14314) — ≥13B lr=1e-4
- TSC-CYCLE MEMORY.md — Qwen3 added-token 陷阱

### Secondary (MEDIUM)
- [vLLM Qwen3.5 recipes](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html), [llama.cpp PR #19408 / Issue #15940 / Issue #20099]
- [Unsloth LoRA hyperparameters guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide)
- [Qwen llama.cpp quantization guide](https://qwen.readthedocs.io/en/latest/quantization/llama.cpp.html)
- [Artificial Analysis Qwen3.5 small models]; [stable-learn.com Qwen3.5 family]
- [Unsloth Issue #4867 / #3861 / #3482]; [bitsandbytes Releases]

### Tertiary (LOW — needs P1 verify)
- [awesomeagents.ai Qwen3.5-9B] (vocab 248K，已被 STACK config.json 升级 HIGH)
- [Oflight Qwen3.5-9B fine-tuning guide]; [unsloth/Qwen3.5-9B-GGUF HF repo]

---
*Research completed: 2026-05-08*
*Ready for roadmap: yes — 5-phase, P1 hard gates explicit*
