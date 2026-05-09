# Milestone v4.0 Requirements — 4B 回退 + 扩展数据重训 + 标签协议修复

**Version:** v4.0
**Goal:** 回到 v1 已验证的 Qwen3-4B-Thinking-2507 基座，复用 v3 扩展数据重新构建 4B 训练集，并把思考标签协议固定为 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`。
**Created:** 2026-05-10

---

## v4.0 Requirements

### BASE — 4B 基座回退

- [ ] **BASE-01**: 学生模型固定为 `Qwen/Qwen3-4B-Thinking-2507`，不再使用 Qwen3.5-9B 作为本里程碑训练基座
- [ ] **BASE-02**: 训练栈沿用 `/dgx-spark-training` 与 `/home/samuel/dgx-spark-setup/.venv` 的已验证 4B 路径，不升级 PyTorch/Transformers/训练框架
- [ ] **BASE-03**: v1.0 baseline artifact 与 gen_cache 以只读方式引用，v4.0 流程不得写入 `runs/20260507T032419Z/`

### TAG — 标签协议修复

- [ ] **TAG-01**: 全链路思考协议固定为 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`
- [ ] **TAG-02**: 数据清洗/重建必须把错误的 `<end_working_out>` 结束标签规范化为 `</end_working_out>`，并报告替换数量
- [ ] **TAG-03**: 训练与评测 prompt builder 禁止注入原生 `<think>`/`</think>` 或 chat_template thinking token
- [ ] **TAG-04**: Qwen3-4B tokenizer audit 证明 4 个自定义标签均为多 sub-token，且 native `<think>`/`</think>` token id 被动态记录用于泄漏检查

### DATA4B — 扩展数据 4B rebuild

- [x] **DATA4B-01**: v4.0 数据源 = v1.0 valid labeled data ∪ v3 新增 lint-pass labeled data，去重后生成 manifest 与样本哈希
- [x] **DATA4B-02**: 使用 Qwen3-4B tokenizer 重新执行 80/10/10 split/tokenize，seed=42，输出到 v4 隔离路径
- [x] **DATA4B-03**: OOD val 保留 v1.0 OOD 可比子集，并加入 v3 扩展 OOD 子集
- [x] **DATA4B-04**: 截断率 ≤5%，且任一样本不得包含 native `<think>`/`</think>` token id
- [x] **DATA4B-05**: dataset card 记录数据来源、标签规范化、split 哈希、v1/v3/v4 artifact 边界

### SFT4B — 4B QLoRA 重训

- [ ] **SFT4B-01**: QLoRA r=64 训练配置沿用 v1 已验证 4B 路线，packing=False，raw-text protocol 不走 chat_template
- [ ] **SFT4B-02**: 训练前 smoke gate 覆盖 tokenizer leakage、样本格式、最小训练步、SOLUTION parse 与硬约束 lint
- [ ] **SFT4B-03**: 全量训练产物写入 `runs/v4.0-4B-{utc_timestamp}/`，与 v1/v3 物理隔离
- [ ] **SFT4B-04**: 训练报告记录 loss 曲线、训练时长、显存峰值、adapter hash、数据 manifest hash

### GGUF4B — merge + GGUF 导出

- [ ] **GGUF4B-01**: LoRA merge → HF bf16/fp16 safetensors → GGUF fp16 → q4_K_M GGUF 全链路通过
- [ ] **GGUF4B-02**: HF / GGUF fp16 / GGUF q4_K_M 三精度 smoke 均输出完整 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` 结构
- [ ] **GGUF4B-03**: HF tokenizer ↔ llama-tokenize parity 在固定 prompt fixture 上通过
- [ ] **GGUF4B-04**: q4_K_M 相对 HF/fp16 的格式与硬约束 smoke 不崩塌；失败时记录 q5_K_M fallback 决策点

### EVAL4B — v1 baseline 对比决策门

- [ ] **EVAL4B-01**: 评测矩阵至少包含 v4 HF、v4 q4_K_M、v1 q4_K_M baseline，并保持 v1 baseline read-only 不重生成
- [ ] **EVAL4B-02**: 报告 OOD hard-constraint pass、teacher MAE、format pass、q4-vs-HF ratio、bootstrap CI、p99/max-abs tail metrics
- [ ] **EVAL4B-03**: 决策门要求 v4 q4_K_M hard-constraint pass ≥98%，q4-vs-HF ratio ≥0.95，且相对 v1 baseline 不显著回退
- [ ] **EVAL4B-04**: `decision.md` 明确给出 GO / NO-GO / 用户决策，并解释扩展数据与 `</end_working_out>` 标签修复的贡献

---

## Future Requirements

- 重新评估更大基座时，优先使用远程/更强 GPU，而不是在本机继续 9B 长训练
- thinking on/off 双跑评测，量化显式思考标签对最终绿灯决策的边际收益
- 自动 q4_K_M → q5_K_M fallback 与 imatrix 量化路线

## Out of Scope

- Qwen3.5-9B 继续训练（本机太慢，当前路线停止）
- Qwen3.6/27B+ 基座（超出本地小模型部署目标）
- 原生 `<think>`/`</think>` 协议
- 使用 `<end_working_out>` 作为结束标签
- 重新调用 GPT-5.5 标注 v1/v3 已 lint-pass 数据
- 在线/RL 优化（GRPO 等）
- 全参 SFT
- vLLM 推理
- 引入新训练栈或升级底层 CUDA/PyTorch 环境

## Traceability

Traceability populated during v4.0 roadmap creation.

| REQ ID | Phase | Status |
|--------|-------|--------|
| BASE-01 | Phase 7 | Pending |
| BASE-02 | Phase 7 | Pending |
| BASE-03 | Phase 7 | Pending |
| TAG-01 | Phase 7 | Pending |
| TAG-02 | Phase 7 | Pending |
| TAG-03 | Phase 7 | Pending |
| TAG-04 | Phase 7 | Pending |
| DATA4B-01 | Phase 8 | Complete |
| DATA4B-02 | Phase 8 | Complete |
| DATA4B-03 | Phase 8 | Complete |
| DATA4B-04 | Phase 8 | Complete |
| DATA4B-05 | Phase 8 | Complete |
| SFT4B-01 | Phase 9 | Pending |
| SFT4B-02 | Phase 9 | Pending |
| SFT4B-03 | Phase 9 | Pending |
| SFT4B-04 | Phase 9 | Pending |
| GGUF4B-01 | Phase 10 | Pending |
| GGUF4B-02 | Phase 10 | Pending |
| GGUF4B-03 | Phase 10 | Pending |
| GGUF4B-04 | Phase 10 | Pending |
| EVAL4B-01 | Phase 11 | Pending |
| EVAL4B-02 | Phase 11 | Pending |
| EVAL4B-03 | Phase 11 | Pending |
| EVAL4B-04 | Phase 11 | Pending |

**Coverage:**
- v4.0 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-05-10*
*Last updated: 2026-05-10 after v4.0 roadmap creation*
