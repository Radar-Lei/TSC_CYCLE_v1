# Requirements: TSC-CYCLE

**Defined:** 2026-02-09
**Core Value:** 给定交叉口实时交通状态,大模型输出的信号配时方案能最大化车辆通过量、最小化排队车辆数

## v1 Requirements

### SFT 数据

- [ ] **SFT-01**: 从 train.jsonl 均匀抽取 100 条样本(覆盖不同场景、交叉口、饱和度分布)
- [ ] **SFT-02**: 每条样本包含中文短思考(50-200 token),分析各相位饱和度并推算合理的 final 绿灯时长
- [ ] **SFT-03**: 输出格式为 `<think>...<think><solution>[{"phase_id": <int>, "final": <int>}, ...]<solution>`
- [ ] **SFT-04**: final 值满足硬约束(min_green ≤ final ≤ max_green,整数秒)
- [ ] **SFT-05**: 生成的 SFT 数据保存为 JSONL 格式,供 SFT 训练脚本使用

### SFT 训练

- [ ] **SFTT-01**: Docker shell 脚本(docker/sft_train.sh)遵循 data.sh 的运行模式
- [ ] **SFTT-02**: Python 训练脚本使用 unsloth 加载 Qwen3-4B-Base 并进行 LoRA 微调
- [ ] **SFTT-03**: 自定义 chat template 定义 `<think>...<think><solution>...<solution>` 标签
- [ ] **SFTT-04**: SFT 后的模型权重保存到 outputs/sft/model 目录

### GRPO 数据

- [ ] **GRPD-01**: 从 train.jsonl 提取 GRPO 训练集(prompt + state_file),不包含思考过程
- [ ] **GRPD-02**: prompt 包含 system(角色设定)和 user(交通状态+任务说明)两部分

### GRPO 训练

- [ ] **GRPT-01**: Docker shell 脚本(docker/grpo_train.sh)遵循 data.sh 的运行模式
- [ ] **GRPT-02**: Python 训练脚本加载 SFT 后的模型继续 GRPO 训练
- [ ] **GRPT-03**: 格式正确性 reward:正则匹配 `<think>...<think><solution>...<solution>` 结构
- [ ] **GRPT-04**: SUMO 仿真 reward:loadState → 执行大模型方案(设置相位+时长)→ 统计车辆通过量和排队车辆数
- [ ] **GRPT-05**: think 长度 reward:对过短(<50 token)或过长(>200 token)的思考进行惩罚
- [ ] **GRPT-06**: 多进程并行 reward 计算(每个候选方案独立启动 SUMO 进程)
- [ ] **GRPT-07**: GRPO 后的模型权重保存到 outputs/grpo/model 目录

## v2 Requirements

### 评估与验证

- **EVAL-01**: 训练后模型在测试场景上的性能评估脚本
- **EVAL-02**: 与 Max-Pressure 基准策略的对比报告

### 扩展

- **EXT-01**: 支持更大模型(Qwen3-8B 等)
- **EXT-02**: 多交叉口协调优化

## Out of Scope

| Feature | Reason |
|---------|--------|
| 基础数据生成程序修改 | 已完成,无需改动 |
| Docker 镜像修改 | 现有镜像已包含所有依赖 |
| 模型推理/部署服务 | 当前只做训练 |
| 在线学习 | 离线训练即可 |
| Web UI | 不需要界面 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SFT-01 | Phase 1 | Pending |
| SFT-02 | Phase 1 | Pending |
| SFT-03 | Phase 1 | Pending |
| SFT-04 | Phase 1 | Pending |
| SFT-05 | Phase 1 | Pending |
| SFTT-01 | Phase 1 | Pending |
| SFTT-02 | Phase 1 | Pending |
| SFTT-03 | Phase 1 | Pending |
| SFTT-04 | Phase 1 | Pending |
| GRPD-01 | Phase 2 | Pending |
| GRPD-02 | Phase 2 | Pending |
| GRPT-01 | Phase 3 | Pending |
| GRPT-02 | Phase 3 | Pending |
| GRPT-03 | Phase 3 | Pending |
| GRPT-04 | Phase 3 | Pending |
| GRPT-05 | Phase 3 | Pending |
| GRPT-06 | Phase 3 | Pending |
| GRPT-07 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-09*
*Last updated: 2026-02-09 after roadmap creation*
