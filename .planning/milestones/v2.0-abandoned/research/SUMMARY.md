# Project Research Summary

**Project:** TSC-CYCLE — GPT-5.5 high → Qwen3-4B-Thinking-2507 蒸馏（TSC 周期绿灯时长决策）
**Domain:** LLM 离线蒸馏批处理流水线（合成数据 → 教师标注 → QLoRA SFT → GGUF 部署 → 评测）
**Researched:** 2026-05-07
**Confidence:** HIGH

## Executive Summary

TSC-CYCLE 是单机离线 6 阶段批处理流水线：从 `reality.log` 抽取输入分布先验，合成 ~3000 条含 OOD 扩展输入，用 GPT-5.5 high（≤10 worker 并发）做教师标注，对 Qwen3-4B-Thinking-2507 跑 QLoRA r=64 SFT（自定义思考标签 `<start_working_out>` / `</end_working_out>` / `<SOLUTION>` / `</SOLUTION>`），merge → llama.cpp GGUF fp16 + q4_K_M 双精度产出，并在三个推理后端（HF bf16 / GGUF fp16 / GGUF q4_K_M）上做硬约束 / 与教师 MAE / OOD / reasoning 关键字四指标矩阵评测。

推荐方法：复用 `/home/samuel/dgx-spark-setup/.venv` 已知良好环境（natolambert 上游）+ TRL+PEFT+bitsandbytes 原生栈（**不引入 Unsloth**），教师客户端复用 EvoProgTSC `client.py` 模式 + Responses API 严格 reasoning_effort 校验，GGUF 走本机 `EvoProgTSC/llama.cpp` 已 build cuda 版（`Qwen3ForCausalLM` 已注册）。所有训练在 `run_safe.sh`（systemd-run scope MemoryMax=100G MemorySwapMax=0）内运行。

关键风险：(1) Thinking-2507 经过官方 RL 强化原生 `<think>` 先验，自定义标签 SFT 可能让模型继续输出 `<think>` 或乱码替代闭合标签（debugging.md 已发生过同型 GRPO 事故）；(2) DGX Spark UMA 128GB + swap 死亡螺旋；(3) 教师 reasoning_tokens 计费不透明，3000 样本量级且 SDK 易静默降档。所有 8 个 pitfall 都有 fail-fast 检测点。

## Key Findings

### Recommended Stack
- Python 3.12 + PyTorch ≥2.9.0+cu130（DGX Spark GB10 aarch64 已验证）
- transformers 4.56.2 + TRL 0.22.2 + PEFT ≥0.15.1 + bitsandbytes 0.48.0（Unsloth Spark 兼容矩阵锚点；sm_121 走 PTX JIT）
- Qwen3-4B-Thinking-2507 学生基座（原生 `<think>` 151667/151668 必须绕开）
- OpenAI SDK ≥1.50.0 + Responses API（避免 reasoning_effort 静默降档）
- 本机 llama.cpp `convert_hf_to_gguf.py` + `llama-quantize Q4_K_M`
- 强制 `attn_implementation="sdpa"`、swap=0、`run_safe.sh` 包裹、`TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas`

### Expected Features

**Must have (table stakes):**
- 合成输入生成器（reality.log 分布先验 + 形式化 OOD 扩展）
- 教师并发标注 + 双重 lint（格式 + 硬约束）+ 失败丢弃不重试 + 断点续跑
- 80/10/10 split + sample_id 全程去重 + 一次性 arrow tokenize
- QLoRA r=64 SFT + 自定义 chat template（绕开 apply_chat_template）+ loss masking + tokenizer sanity gate
- bf16 reload merge → GGUF (bf16/fp16) → q4_K_M 三步导出
- 三 backend 评测矩阵（HF bf16 / GGUF fp16 / GGUF q4_K_M）× 四指标

**Should have (差异化):**
- `runs/{ts}/` + manifest.json（config hash + git sha + stage status）
- raw_responses/ 内容寻址缓存（sha256(prompt+model+effort)）
- 评测 gen_cache 分层（生成与指标解耦）
- 全局 seed + tokenizer 单元测试 + dataset card

**Defer:** GRPO/RL、self-consistency、OOD 分维度细分、q5/q8 多档量化、imatrix（仅崩塌时触发）

### Architecture Approach

单机 6 stage 离线批处理 + 内容寻址缓存 + run-manifest 单一真理源。每个 stage 是 `(Config, InputArtifacts) → OutputArtifacts` 纯函数；`prompt_builder.py` 在训练 / 教师 / 评测三处共用。统一 CLI `tsc-cycle <stage>`，单包 src layout。

**Major components:**
1. Sampler（distribution_fit + sample_inputs）
2. Teacher Labeler（OpenAI Responses + raw_responses 缓存 + constraint_lint）
3. Dataset Builder（split + 一次性 tokenize → arrow）
4. Trainer（QLoRA SFT + tokenizer sanity gate + checkpoint resume）
5. Exporter（bf16 reload merge → GGUF → q4_K_M）
6. Evaluator（三 variant runner + gen_cache + report.md）

### Critical Pitfalls

1. **Thinking-2507 拒绝放弃原生 `<think>`** — 绕开 `apply_chat_template`，纯 raw text 拼接；prompt 末尾预填 `<start_working_out>`；loss-mask 只算 assistant 段；首 epoch 末 5 prompt smoke test，<50% 立即加 epoch + alpha=192；fallback 推理期 `--logit-bias 151667-100 --logit-bias 151668-100`
2. **DGX Spark UMA OOM 死亡螺旋** — `swapoff -a` + `run_safe.sh`（systemd-run MemoryMax=100G MemorySwapMax=0）+ 显式 SDPA + flash_attn ImportError 校验 + `dataloader_num_workers≤1` + bnb dummy forward 预热
3. **教师 reasoning 静默降档 / 成本失控** — Responses API + 断言 `usage.reasoning_tokens > 100` + 50 样本 smoke 外推成本 + token bucket 限速（先 5 RPM 起步）+ JSONL flush+fsync 续跑
4. **LoRA→GGUF 链断**（merge nan / fp16 range / q4_K_M 长 thinking 崩塌）— merge 前 reload bf16 base、导出 bf16 GGUF、20 prompt greedy parity test、MAE>3s 触发 imatrix
5. **OOD val 退化 / 评测假阳** — `data/ood_spec.md` 形式化（phase_count / 范围 / 饱和度跨度）+ KS test 每维 p<0.01 + sample_id 去重 + 排除 trivial（min==max）+ 三 variant 共用 greedy seed=42

## Implications for Roadmap

### Phase 1: 环境就绪 + Foundations
**Rationale:** Pitfall 1/4 必须在烧钱前 fail-fast；prompt_builder/constraint_lint/tokenizer_check 是后续基石
**Delivers:** 克隆 venv + verify.py 全绿 + foundations 模块 + 单元测试 + dist_prior.json + 5–10 sample 教师 smoke
**Avoids:** Pitfall 1, 4, 7（成本外推）

### Phase 2: 合成数据生成
**Rationale:** OOD 必须在教师烧钱前形式化；3000 规模分布 bug 不可逆
**Delivers:** sample_inputs.py + ood_spec.md + inputs.jsonl(~2700) + ood_inputs.jsonl(~300) + KS test 报告
**Avoids:** Pitfall 3, 6

### Phase 3: 教师标注（4–6h 后台）
**Rationale:** 最贵段，可与后续工程并行；断点续跑保证中断成本低
**Delivers:** raw_responses/ + labeled.jsonl ≥2700 + rejected.jsonl + 违反类型分布
**Avoids:** Pitfall 2, 7

### Phase 4: 数据集装配 + QLoRA SFT
**Rationale:** 6h 硬预算（Pitfall 8）；tokenizer sanity 是 boot 第一步
**Delivers:** tokenized arrow + LoRA adapter + train_log + 首 epoch 自定义标签 smoke
**Avoids:** Pitfall 1, 4, 8

### Phase 5: Merge + GGUF 导出
**Rationale:** 短阶段（~30min）但 merge dtype silent killer
**Delivers:** merged_bf16/ + model.bf16.gguf + model.q4_K_M.gguf + tokenize sanity + 20 prompt parity
**Avoids:** Pitfall 5

### Phase 6: 评测套件
**Rationale:** 三 backend × 四指标矩阵；fp16/q4_K_M 退化是部署 go/no-go gate
**Delivers:** gen_cache/ + per_sample.jsonl + report.md（trivial 排除 + p99 + 按 phase_count 分桶）
**Avoids:** Pitfall 5d, 6

### Phase Ordering Rationale
- 数据流强依赖：reality.log → dist_prior → inputs → labeled → tokenized → adapter → merged → gguf → eval
- 资源调度：Phase 3（API 4–6h）和 Phase 4（GPU 6h）独立等候期；可与 Phase 4/5/6 工程开发并行
- 失败成本递增：P1 分钟 → P2 分钟 → P3 小时+USD → P4 6h GPU → P5 30min → P6 1h；P1 必须 hard gate

### Research Flags

**Needs deeper research during planning:**
- **Phase 4 (Training):** Thinking-2507 自定义标签 unlearn epoch 数无对照；需 200 样本冒烟实测
- **Phase 5 (Export):** Qwen3-Thinking + 自定义标签 + bf16 GGUF parity 无公开 benchmark；需研究 llama.cpp 版本下限
- **Phase 6 (Eval):** q4_K_M 长 thinking 退化率是项目独有未知；可能需 imatrix 最佳实践研究

**Standard patterns (skip research):**
- Phase 1：`/dgx-spark-training` skill + EvoProgTSC 是权威模板
- Phase 2：纯 Python + KS test 标准统计
- Phase 3：EvoProgTSC client + ThreadPoolExecutor 成熟，仅 Responses API + 限速器为增量

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | 本机 venv + llama.cpp 双重产物验证；natolambert dgx-spark-setup + NVIDIA Spark playbook 双源版本锚定 |
| Features | HIGH | 全部从 PROJECT.md Active Requirements / Out of Scope 反推 |
| Architecture | HIGH | 单机离线无服务化复杂度；EvoProgTSC + dgx-spark-setup 双源验证 |
| Pitfalls | HIGH | 8 条中 2 条已发生过（MEMORY/debugging.md）；其余三角验证 |

**Overall confidence:** HIGH

### Gaps to Address
- Thinking-2507 unlearn 原生 `<think>` 所需 epoch 数：Phase 4 entry 前 200 样本冒烟实测
- GPT-5.5 high 实际 reasoning_tokens 量级：Phase 1 末 50 样本 smoke 外推；超预算 owner 确认
- DGX Spark sm_121 PTX JIT 多 worker 竞态：`dataloader_num_workers=1` + dummy forward 预热
- q4_K_M 长 thinking SOLUTION 数值漂移：Phase 6 必跑 parity，MAE>3s 触发 imatrix
- OpenAI 账户 tier RPM/TPM 实际限额：`max_workers=5` 起步，30min 观测后再升

## Sources

**Primary (HIGH):**
- `/home/samuel/dgx-spark-setup/` + 上游 https://github.com/natolambert/dgx-spark-setup
- `/home/samuel/.claude/skills/dgx-spark-training/SKILL.md`
- `/home/samuel/projects/EvoProgTSC/llama.cpp/{convert_hf_to_gguf.py:4551, llama-quantize}`
- `/home/samuel/projects/EvoProgTSC/evoprog/llm/client.py`
- `/home/samuel/.claude/projects/-home-samuel-TSC-CYCLE/memory/{MEMORY.md, debugging.md}`
- `/home/samuel/TSC_CYCLE/{PROJECT.md, reality.log}`
- HuggingFace Qwen3-4B-Thinking-2507 model card
- Unsloth on Spark 官方文档 + NVIDIA build.nvidia.com Spark playbook
- OpenAI Responses API 官方文档

**Secondary (MEDIUM):**
- bitsandbytes Releases（aarch64 sm_121 PTX JIT）
- Qwen llama.cpp quantization guide（Q4_K_M + imatrix）

**Explicitly NOT used:** ~~waybarrios/dgx-spark-finetune-llm~~（用户明确排除）

---

### Synthesis Summary for Roadmapper

- **Suggested phases:** 6（环境/Foundations → 数据合成 → 教师标注 → 训练 → 导出 → 评测）
- **Research flags:** Phase 4 / Phase 5 / Phase 6 需 deeper research；Phase 1/2/3 标准模板可跳过
- **Overall confidence:** HIGH
