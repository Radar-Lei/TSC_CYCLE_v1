# Requirements: TSC-CYCLE v2.0 强化版

**Defined:** 2026-05-08
**Core Value:** 学生模型在 OOD（reality.log 分布之外的合成输入）上仍然满足全部硬约束（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），并在数值决策上接近 GPT-5.5 high 教师 —— 不是过拟合到 reality.log。

## v2.0 Requirements

### 标签协议

- [ ] **TAG-01**: 全链路 prompt、数据生成、训练、推理测试、reward/eval 输出协议统一使用 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`。
- [ ] **TAG-02**: 解析器和 lint 能拒绝旧的 `</end_working_out>` 输出，并验证新标签完整可解析。

### 数据扩容

- [ ] **DATA-01**: 系统能生成 10K 规模候选输入，覆盖同分布、OOD/边界、v1.0 错误/高 MAE targeted 样本。
- [ ] **DATA-02**: 数据集构建报告记录三类样本比例、字段分布、边界覆盖和与 v1.0 的差异。
- [ ] **DATA-03**: GPT-5.5 high 教师标注结果通过硬约束 lint 后形成可复现 10K 训练集与 val/OOD split。

### 重训导出

- [ ] **TRAIN-01**: 学生使用扩容数据在 DGX Spark 上完成 QLoRA r=64 重训，并保留可复现实验配置与日志。
- [ ] **TRAIN-02**: 训练后的 adapter 能 merge 为 HF fp16，并导出 GGUF fp16 与 q4_K_M。

### 评测门槛

- [ ] **EVAL-01**: v2.0 q4_K_M 在 OOD 硬约束满足率上严格高于 v1.0 q4_K_M 98.7%。
- [ ] **EVAL-02**: v2.0 q4_K_M 的教师 MAE 严格优于 v1.0 baseline。
- [ ] **EVAL-03**: v2.0 q4_K_M 的思考格式完整率严格优于 v1.0 baseline，并且输出只使用新结束标签。
- [ ] **EVAL-04**: 最终报告并列展示 v1.0 vs v2.0 的 HF bf16 与 q4_K_M 指标，给出部署 go/no-go 裁决。

## Future Requirements

### 后训练增强

- **POST-01**: 在 SFT 扩容收益验证后，再评估 DPO/RLHF/GRPO 是否值得作为下一里程碑。

### 量化增强

- **QUANT-01**: 若 q4_K_M 仍明显弱于 HF bf16，再追加 imatrix 重量化。

## Out of Scope

| Feature | Reason |
|---------|--------|
| 更换学生基座 | v2.0 目标是验证 10K 数据扩容收益，避免模型切换混淆因果。 |
| 更换教师模型 | 保持 GPT-5.5 high baseline 可比性。 |
| 在线/RL 后训练 | 本里程碑先完成 SFT 扩容闭环，后训练留到扩容收益确认后。 |
| vLLM 推理 | 本机现状不可用，最终部署仍走 llama.cpp / GGUF。 |
| 使用旧结束标签 `</end_working_out>` | 用户已明确要求全链路改为 `<end_working_out>`，旧标签应被拒绝。 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TAG-01 | TBD | Pending |
| TAG-02 | TBD | Pending |
| DATA-01 | TBD | Pending |
| DATA-02 | TBD | Pending |
| DATA-03 | TBD | Pending |
| TRAIN-01 | TBD | Pending |
| TRAIN-02 | TBD | Pending |
| EVAL-01 | TBD | Pending |
| EVAL-02 | TBD | Pending |
| EVAL-03 | TBD | Pending |
| EVAL-04 | TBD | Pending |

**Coverage:**
- v2.0 requirements: 11 total
- Mapped to phases: 0
- Unmapped: 11 ⚠️

---
*Requirements defined: 2026-05-08*
*Last updated: 2026-05-08 after milestone v2.0 requirements definition*
