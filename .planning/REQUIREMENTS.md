# Requirements: TSC_CYCLE

**Defined:** 2026-02-07
**Core Value:** 能够一键执行完整的训练流水线（数据生成 → SFT → GRPO），稳定地从 SUMO 仿真数据生成到强化学习微调，输出可用的交通信号控制模型。

## v1 Requirements

### Data Generation (数据生成)

- [ ] **DATA-01**: 系统能够自动扫描 `sumo_simulation/environments/` 发现所有场景子文件夹
- [ ] **DATA-02**: 系统能够解析每个场景的信控交叉口配置
- [ ] **DATA-03**: 系统能够以交叉口为单位并行生成数据（单层并行，不嵌套）
- [ ] **DATA-04**: 每个场景运行固定 3600 秒仿真
- [ ] **DATA-05**: 系统能够检测信号周期边界并采样状态快照
- [ ] **DATA-06**: 系统能够将原始仿真数据保存为 JSONL 格式
- [ ] **DATA-07**: 系统能够将原始数据转换为 CoT 格式的训练数据（二度生成）

### Training Pipeline (训练流程)

- [ ] **TRAIN-01**: SFT 训练能够从 JSONL 数据学习输出格式
- [ ] **TRAIN-02**: SFT 训练后模型输出符合预期的信号周期格式
- [ ] **TRAIN-03**: GRPO 训练能够基于 SFT 模型进行强化学习
- [ ] **TRAIN-04**: GRPO 训练使用奖励函数评估控制策略质量
- [ ] **TRAIN-05**: 训练过程能够在 GPU 上正常运行并保存 checkpoint

### Execution Entry (执行入口)

- [ ] **EXEC-01**: `run.sh --stage=data` 仅执行数据生成阶段
- [ ] **EXEC-02**: `run.sh --stage=sft` 仅执行 SFT 训练阶段
- [ ] **EXEC-03**: `run.sh --stage=grpo` 仅执行 GRPO 训练阶段
- [ ] **EXEC-04**: `run.sh --stage=all` 执行完整流程（data → sft → grpo）
- [ ] **EXEC-05**: 所有执行都在 Docker 容器中进行
- [ ] **EXEC-06**: 执行失败时能够输出清晰的错误信息

### Code Cleanup (代码清理)

- [ ] **CLEAN-01**: 移除时段配置相关的代码和参数
- [ ] **CLEAN-02**: 清理重复的数据生成逻辑（统一为单层并行）
- [ ] **CLEAN-03**: 移除不使用的中间文件生成逻辑
- [ ] **CLEAN-04**: 统一配置文件结构，消除冗余配置项
- [ ] **CLEAN-05**: 代码中移除注释掉的旧逻辑

### Validation (验证机制)

- [ ] **VALID-01**: 支持小规模验证模式（1-2 场景 × 1-2 交叉口）
- [ ] **VALID-02**: 数据生成后自动验证 JSONL 格式正确性
- [ ] **VALID-03**: 能够执行端到端流程验证（data → sft → grpo 完整跑通）
- [ ] **VALID-04**: 验证模式能够快速完成（< 10 分钟）

## v2 Requirements

### Advanced Features (高级功能)

- **PERF-01**: 支持多 GPU 并行训练
- **PERF-02**: 数据生成支持增量模式（跳过已生成数据）
- **MONITOR-01**: 训练过程可视化（loss、reward 曲线）
- **MONITOR-02**: 数据生成进度实时监控
- **EVAL-01**: 模型评估脚本（在测试集上评估控制策略）
- **EVAL-02**: 与固定时长控制策略的对比基准测试

### Robustness (鲁棒性)

- **ERROR-01**: 单个交叉口失败不影响其他交叉口的数据生成
- **ERROR-02**: 训练中断后支持断点续训
- **CONFIG-01**: 配置文件支持 schema 验证
- **CONFIG-02**: 支持多套配置（dev、prod）

## Out of Scope

| Feature | Reason |
|---------|--------|
| 多时段仿真支持 | 所有仿真固定 3600 秒，时段配置增加复杂度但无实际价值 |
| 非 Docker 环境运行 | 统一容器化部署，避免环境依赖问题 |
| 实时在线控制 | 当前专注离线训练流水线，在线控制是未来方向 |
| 模型压缩和部署优化 | 先确保流程稳定，模型优化是后续工作 |
| 多模型对比实验 | 当前专注 Qwen3-4B，多模型对比不在 v1 范围 |
| 分布式训练 | 单机 GPU 足够，分布式训练增加复杂度 |

## Traceability

<!-- 由 roadmapper 填充 -->

| Requirement | Phase | Status |
|-------------|-------|--------|
| (待路线图创建后填充) | | |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: (待填充)
- Unmapped: (待填充)

---
*Requirements defined: 2026-02-07*
*Last updated: 2026-02-07 after initial definition*
