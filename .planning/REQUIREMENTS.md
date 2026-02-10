# Requirements: TSC-CYCLE

**Defined:** 2026-02-10
**Core Value:** 给定交叉口实时交通状态，大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数

## v1.1 Requirements

Requirements for v1.1 milestone. Each maps to roadmap phases.

### Reward

- [ ] **RWD-01**: SUMO reward 公式去掉 `min(combined, 1.0)` 的 cap，用非线性压缩函数（如 log/sqrt）替代，使不同质量的方案获得有区分度的分数
- [ ] **RWD-02**: Baseline 策略从"默认信号周期仿真"改为"饱和度启发式基准"（按各相位 pred_saturation 比例分配绿灯时间，饱和度>1 给 max_green），提高比较基准让 reward 不再轻松到满分
- [ ] **RWD-03**: 修改 baseline.py 预计算脚本，支持新的饱和度启发式 baseline 策略，重新生成 baseline.json

### Data

- [ ] **DAT-01**: 新增 GRPO 数据过滤脚本，从 grpo_train.jsonl 中剔除 baseline passed=0 且 queue=0 的空交叉口样本，生成过滤后的训练集
- [ ] **DAT-02**: 过滤后的数据集统计信息输出（过滤前后样本数、各场景分布、过滤原因统计）

### Integration

- [ ] **INT-01**: config.json 中新增 reward 相关配置项（非线性压缩函数类型和参数），保持配置驱动
- [ ] **INT-02**: GRPO 训练脚本 train.py 适配新的数据加载逻辑（加载过滤后的数据集）
- [ ] **INT-03**: Docker 入口脚本适配新流程（baseline 重新计算 + 数据过滤 + 训练）

## Future Requirements

### v2 及以后

- **RWD-F01**: 动态 baseline — 随训练进行更新 baseline（当前模型最佳方案作为新 baseline）
- **RWD-F02**: 多维度 reward — 加入延误时间、通行效率等更多 SUMO 指标
- **DAT-F01**: 在线数据筛选 — 训练中动态跳过 zero-std 步

## Out of Scope

| Feature | Reason |
|---------|--------|
| 场景均衡抽样 | 当前 21 个场景已均衡（788-800 条/场景） |
| 低区分度样本过滤 | 根源是 reward 二值化，改进 reward 后自然缓解 |
| 修改 GRPO 数据生成脚本 generate_grpo_data.py | 过滤在下游做，不改数据生成源头 |
| 修改 SFT 相关代码 | v1.1 只改 GRPO 链路 |
| num_generations 调整 | 当前 4 已合理，暂不改 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RWD-01 | — | Pending |
| RWD-02 | — | Pending |
| RWD-03 | — | Pending |
| DAT-01 | — | Pending |
| DAT-02 | — | Pending |
| INT-01 | — | Pending |
| INT-02 | — | Pending |
| INT-03 | — | Pending |

**Coverage:**
- v1.1 requirements: 8 total
- Mapped to phases: 0
- Unmapped: 8 ⚠️

---
*Requirements defined: 2026-02-10*
*Last updated: 2026-02-10 after initial definition*
