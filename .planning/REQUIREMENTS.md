# Requirements: TSC-CYCLE v2 — GLM-5 SFT 数据生成

**Defined:** 2026-03-25
**Core Value:** 生成足够多样和深度的 SFT 训练数据，使 Qwen3-4B 学会真正的交通配时推理

## v1 Requirements

### API 客户端

- [x] **API-01**: GLM-5 客户端使用 OpenAI 兼容接口（openai SDK），配置端点 `open.bigmodel.cn/api/coding/paas/v4`
- [x] **API-02**: 支持并发 4 个请求（asyncio/线程池）
- [x] **API-03**: 失败时指数退避重试，最多 3 次
- [x] **API-04**: 设置 max_tokens=8192，确保长推理链不被截断

### 数据采样

- [x] **SAMP-01**: 从 train.jsonl (16,788 条) 中均匀抽样 5,000 条，覆盖所有场景和交叉口
- [x] **SAMP-02**: 抽样策略保证饱和度分布多样性（高/中/低饱和度均有覆盖）

### 推理链生成

- [x] **GEN-01**: 构建 prompt 让 GLM-5 根据交通数据生成 think 链 + solution
- [x] **GEN-02**: think 链目标长度约 500 token，prompt 中明确约束
- [x] **GEN-03**: solution 格式为 JSON 数组 `[{"phase_id": N, "final": N}, ...]`
- [x] **GEN-04**: GLM-5 输出经过约束校验：相位顺序一致 + min_green ≤ final ≤ max_green
- [ ] **GEN-05**: 约束违反时丢弃该条重试，单条最多重试 3 次
- [ ] **GEN-06**: 3 次均失败的样本记录日志并跳过

### 容错与进度

- [ ] **PROG-01**: 支持断点续传——已成功生成的条目不会重复调用 API
- [ ] **PROG-02**: 实时显示进度（已完成/总数、成功率、平均 think 长度）
- [ ] **PROG-03**: 中间结果保存到文件，程序中断后可恢复

### 数据组装

- [ ] **ASM-01**: 将 GLM-5 生成的结果组装为 SFT 训练格式 (messages: system/user/assistant)
- [ ] **ASM-02**: assistant 内容格式：`<start_working_out>{think}<end_working_out><SOLUTION>{json}</SOLUTION>`
- [ ] **ASM-03**: 最终输出 `outputs/sft/sft_train.jsonl`，可直接用于 `src/sft/train.py`

### 训练验证

- [ ] **TRAIN-01**: 用新生成的 5000 条数据在 Unsloth Docker 容器中运行 SFT 训练（1 epoch，通过 `docker/sft_train.sh`），确认数据格式兼容
- [ ] **TRAIN-02**: 检查训练 loss 曲线正常收敛（非过拟合模式）

### 模型导出

- [ ] **EXPORT-01**: 将训练后的 LoRA 模型导出为 Q4_K_M 量化 GGUF 格式
- [ ] **EXPORT-02**: 将训练后的 LoRA 模型导出为 Q8_0 量化 GGUF 格式
- [ ] **EXPORT-03**: 将训练后的 LoRA 模型导出为 F16 GGUF 格式

## v2 Requirements

### 数据增强

- **AUG-01**: 对同一样本用不同 temperature 生成多条推理链
- **AUG-02**: 引入更多 SUMO 场景增加数据多样性

### 质量提升

- **QUAL-01**: 用 SUMO 仿真验证 GLM-5 生成的 solution 质量（不仅是约束校验）
- **QUAL-02**: 自动筛选 think 链质量（连贯性、逻辑性评分）

## Out of Scope

| Feature | Reason |
|---------|--------|
| GRPO 训练调整 | 本里程碑聚焦 SFT 数据，GRPO 后续进行 |
| 新 SUMO 场景 | 现有 16,788 条覆盖足够 |
| Benchmark 评估 | 训练后独立评估 |
| 多模型对比 | 先用 GLM-5 跑通流程 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | Phase 1 | Complete |
| API-02 | Phase 1 | Complete |
| API-03 | Phase 1 | Complete |
| API-04 | Phase 1 | Complete |
| SAMP-01 | Phase 1 | Complete |
| SAMP-02 | Phase 1 | Complete |
| GEN-01 | Phase 2 | Complete |
| GEN-02 | Phase 2 | Complete |
| GEN-03 | Phase 2 | Complete |
| GEN-04 | Phase 2 | Complete |
| GEN-05 | Phase 2 | Pending |
| GEN-06 | Phase 2 | Pending |
| PROG-01 | Phase 2 | Pending |
| PROG-02 | Phase 2 | Pending |
| PROG-03 | Phase 2 | Pending |
| ASM-01 | Phase 3 | Pending |
| ASM-02 | Phase 3 | Pending |
| ASM-03 | Phase 3 | Pending |
| TRAIN-01 | Phase 3 | Pending |
| TRAIN-02 | Phase 3 | Pending |
| EXPORT-01 | Phase 3 | Pending |
| EXPORT-02 | Phase 3 | Pending |
| EXPORT-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 after revision (5000 samples, 1 epoch, GGUF export)*
