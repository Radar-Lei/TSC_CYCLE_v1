# Roadmap: 交通信号周期优化 GRPO 训练系统

## Overview

从零开始构建一个基于 GRPO 的交通信号控制模型训练系统。首先处理 SUMO 相位冲突确保数据有效性,然后并行生成训练数据,接着通过 SFT 让模型学会输出格式,再用 GRPO 让模型从仿真反馈中自主学习推理策略,最后打包成 Docker 一键运行环境。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: 相位处理系统** - 从 SUMO 网络文件提取、验证、过滤相位,解决绿灯冲突
- [ ] **Phase 2: 训练数据生成** - 并行 SUMO 仿真生成 ~10,000 条 GRPO 训练数据
- [ ] **Phase 3: SFT 预训练** - 手工编写示例,训练 Qwen3-4B 学会输出格式
- [ ] **Phase 4: GRPO 强化学习** - 实现奖励函数,通过仿真反馈训练模型推理能力
- [ ] **Phase 5: Docker 部署环境** - 一键运行脚本,整合完整训练流程

## Phase Details

### Phase 1: 相位处理系统
**Goal**: SUMO 场景中的所有路口都有可用的互斥相位配置
**Depends on**: Nothing (first phase)
**Requirements**: PHASE-01, PHASE-02, PHASE-03, PHASE-04, PHASE-05, PHASE-06, PHASE-07
**Success Criteria** (what must be TRUE):
  1. 能够从 chengdu.net.xml 解析出所有信号灯的相位定义
  2. 无效相位(仅黄灯或红灯)被正确过滤,不出现在最终配置中
  3. 每个路口至少有 2 个互斥的有效相位(绿灯车道不重叠)
  4. 冲突相位按规则解决(保留绿灯数多的,相等时随机保留)
  5. 每个相位都有明确的最小绿/最大绿时间配置
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md - 基础设施 (数据模型 + 日志配置 + XML 解析器)
- [ ] 01-02-PLAN.md - 相位处理核心 (无效过滤 + 冲突检测解决 + 验证)
- [ ] 01-03-PLAN.md - 主处理流程 (时间配置 + 处理器编排 + CLI)

### Phase 2: 训练数据生成
**Goal**: 生成覆盖不同时段和交叉口的 ~10,000 条 GRPO 训练数据
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07
**Success Criteria** (what must be TRUE):
  1. 能够并行启动多个 SUMO 实例生成训练数据(利用 multiprocessing)
  2. 数据覆盖早高峰(7-9am)、平峰、晚高峰(17-19pm)三个时段
  3. 每条数据包含模拟预测的排队车辆数(真实值加波动)
  4. 每条数据包含带波动的最小绿/最大绿时间(±2-5秒)
  5. 生成约 10,000 条数据并保存为 JSON 格式
**Plans**: TBD

Plans:
- [ ] 02-01: TBD during plan-phase

### Phase 3: SFT 预训练
**Goal**: Qwen3-4B 模型学会输出 `<think>...</think>[{phase_id, final}...]` 格式
**Depends on**: Phase 2
**Requirements**: SFT-01, SFT-02, SFT-03, SFT-04, SFT-05, SFT-06
**Success Criteria** (what must be TRUE):
  1. 手工编写的 50-100 条示例数据格式正确且包含推理过程
  2. 模型能够加载 Qwen3-4B 基础模型并配置 LoRA 参数
  3. 训练后的模型能够输出符合格式的响应(包含 <think> 和 JSON 数组)
  4. SFT 模型和 tokenizer 保存在指定路径可供后续使用
**Plans**: TBD

Plans:
- [ ] 03-01: TBD during plan-phase

### Phase 4: GRPO 强化学习
**Goal**: 模型从 SUMO 仿真反馈中学会推理最优信号周期
**Depends on**: Phase 3
**Requirements**: GRPO-01, GRPO-02, GRPO-03, GRPO-04, GRPO-05, GRPO-06, GRPO-07
**Success Criteria** (what must be TRUE):
  1. 格式奖励函数能够验证模型输出格式正确性
  2. 仿真奖励函数能够并行启动 SUMO 评估方案效果(等待时间、通行量等)
  3. 多个奖励函数成功组合为综合奖励信号
  4. GRPO 训练循环正常运行(生成 → 评估 → 更新)
  5. 训练指标被记录(reward, reward_std, completion_length, kl)
  6. 最终 GRPO 模型保存在指定路径
**Plans**: TBD

Plans:
- [ ] 04-01: TBD during plan-phase

### Phase 5: Docker 部署环境
**Goal**: 一键运行完整的训练流程(数据生成 → SFT → GRPO)
**Depends on**: Phase 4
**Requirements**: DOCKER-01, DOCKER-02, DOCKER-03, DOCKER-04, DOCKER-05, DOCKER-06
**Success Criteria** (what must be TRUE):
  1. Docker 镜像包含所有依赖(CUDA, SUMO, Python packages)
  2. 环境变量正确配置(SUMO_HOME, HF_HOME, PARALLEL 等)
  3. 数据和模型目录正确挂载到容器
  4. 执行 docker/publish.sh 能够一键运行完整流程(依赖检查 → 数据生成 → SFT → GRPO)
  5. 训练完成后输出摘要(数据量、训练时间、模型路径)
**Plans**: TBD

Plans:
- [ ] 05-01: TBD during plan-phase

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. 相位处理系统 | 0/3 | Planned | - |
| 2. 训练数据生成 | 0/? | Not started | - |
| 3. SFT 预训练 | 0/? | Not started | - |
| 4. GRPO 强化学习 | 0/? | Not started | - |
| 5. Docker 部署环境 | 0/? | Not started | - |
