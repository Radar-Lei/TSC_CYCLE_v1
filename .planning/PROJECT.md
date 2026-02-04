# 交通信号周期优化 GRPO 训练系统

## What This Is

一个基于 GRPO (Group Relative Policy Optimization) 的交通信号周期优化模型训练系统。通过 SUMO 仿真生成数据,先用 SFT 让 Qwen3-4B 模型学会输出格式,再用 GRPO 强化学习让模型自主学习推理最优信号周期的能力,无需人工标注 thinking 过程。

## Core Value

**让模型自己学会"思考"如何优化交通信号周期** - 通过 GRPO 从仿真反馈中学习推理过程,而不是依赖人工标注的专家推理数据。

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **PHASE-01**: 相位验证和过滤系统 - 从 SUMO 网络文件中提取相位,过滤无效相位,检测并解决绿灯车道重叠冲突,确保每个路口至少有2个互斥的有效相位
- [ ] **DATA-01**: GRPO 数据生成 - 并行运行 SUMO 仿真生成 ~10,000 条训练数据,覆盖早高峰/平峰/晚高峰时段
- [ ] **DATA-02**: 数据特征生成 - 从 SUMO 默认配置读取最小绿/最大绿并添加 ±2-5秒波动,生成模拟预测的排队车辆数
- [ ] **SFT-01**: SFT 数据集创建 - 手工编写 50-100 条带 thinking 过程的示例数据
- [ ] **SFT-02**: SFT 预训练 - 让 Qwen3-4B 学会输出 `<think>...</think>[{phase_id, final}...]` 格式
- [ ] **GRPO-01**: 奖励函数实现 - 并行启动 SUMO 评估方案效果(等待时间、通行量),计算格式奖励 + 效果奖励
- [ ] **GRPO-02**: GRPO 训练 - 使用仿真奖励引导模型学习最优推理策略
- [ ] **DOCKER-01**: Docker 环境配置 - 改写 docker/publish.sh 实现一键运行完整流程

### Out of Scope

- 实时在线控制系统 — 当前专注于离线模型训练
- 多场景扩展 — 只使用 chengdu 场景
- 真实预测模型 — 用真实值加波动模拟预测,不实现真正的预测算法
- 分布式训练 — 使用单机 multiprocessing,不引入 Ray/Dask

## Context

**现有资源**:
- 参考实现: `/home/samuel/TSC_CYCLE/grpo_reference_only/` - 包含类似项目的代码结构
- 示例 notebook: `Qwen3_(4B)_GRPO.ipynb` - Unsloth GRPO 训练流程参考
- SUMO 场景: `sumo_simulation/environments/chengdu/` - 成都路网 + 分时段路由文件
- Prompt 示例: `sample_prompt_result.md` - 输入输出格式参考

**技术环境**:
- 模型: Qwen3-4B (via Unsloth)
- 框架: transformers, trl, unsloth, vllm
- 仿真: SUMO 1.22.0
- 并行: Python multiprocessing
- 容器: Docker

**关键技术点**:
1. **相位冲突处理**:
   - 只保留有绿灯的相位 (state 含 'G' 或 'g')
   - 检测绿灯车道重叠,保留绿灯数多的相位,删除少的
   - 如果绿灯数相等,随机保留一个
   - 最终每个路口必须至少有 2 个互斥的有效相位

2. **数据生成策略**:
   - 时段覆盖: 早高峰 (7-9am) / 平峰 / 晚高峰 (17-19pm)
   - 最小绿/最大绿: 从 SUMO phase 定义读取,加 ±2-5秒随机波动
   - 排队车辆数: 使用真实值 + 合理范围波动 (模拟预测误差)
   - 目标数据量: ~10,000 条

3. **GRPO 无监督学习**:
   - SFT 阶段只需学会格式,不要求推理质量
   - GRPO 通过仿真奖励信号让模型自主探索推理策略
   - 不需要人工标注 thinking 过程

## Constraints

- **Tech stack**: Python 3.10+, PyTorch, Unsloth, TRL, SUMO
- **Hardware**: 需要 NVIDIA GPU (至少 16GB VRAM for Qwen3-4B)
- **Scenario**: 仅使用 chengdu 场景,不扩展其他城市
- **Data volume**: ~10,000 条训练数据 (平衡质量和训练时间)
- **Model base**: 必须基于 Qwen3-4B,不使用其他模型架构
- **Docker compatibility**: 必须兼容现有 docker/publish.sh 的环境依赖

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 使用 GRPO 而非监督学习 | 无法获取高质量的 thinking 过程标注,GRPO 可从仿真反馈中自主学习 | — Pending |
| 相位冲突用简单策略(保留绿灯多的) | 避免复杂的相位拆分逻辑,优先保证互斥性 | — Pending |
| 用 multiprocessing 并行 SUMO | 相比分布式框架更轻量,单机性能足够 | — Pending |
| SFT 阶段手工编写示例 | 50-100 条足够让模型学会格式,避免大量标注成本 | — Pending |
| 只用 chengdu 场景 | 专注于单场景深度优化,避免多场景泛化复杂性 | — Pending |

---
*Last updated: 2026-02-04 after initialization*
