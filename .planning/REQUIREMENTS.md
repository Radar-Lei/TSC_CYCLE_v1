# Requirements: 交通信号周期优化 GRPO 训练系统

**Defined:** 2026-02-04
**Core Value:** 让模型自己学会"思考"如何优化交通信号周期

## v1 Requirements

### 相位处理 (Phase Processing)

- [x] **PHASE-01**: 从 SUMO .net.xml 文件解析所有信号灯的相位定义
- [x] **PHASE-02**: 过滤无效相位(只有黄灯 'y' 或红灯 'r' 的相位)
- [x] **PHASE-03**: 提取每个相位的绿灯控制车道列表
- [x] **PHASE-04**: 检测相位间绿灯车道重叠冲突
- [x] **PHASE-05**: 冲突解决 - 保留绿灯车道数多的相位,删除少的,相等时随机保留
- [x] **PHASE-06**: 验证每个路口至少有 2 个互斥的有效相位,不满足则跳过该路口
- [x] **PHASE-07**: 从相位定义读取或推断最小绿/最大绿时间

### 数据生成 (Data Generation)

- [ ] **DATA-01**: 实现 multiprocessing 并行 SUMO 仿真框架
- [ ] **DATA-02**: 从 chengdu_daily/*.rou.xml 文件中识别早/平/晚高峰时段
- [ ] **DATA-03**: 为每个相位的最小绿/最大绿添加 ±2-5秒随机波动
- [ ] **DATA-04**: 从 SUMO 获取真实排队车辆数,添加合理范围波动生成"模拟预测值"
- [ ] **DATA-05**: 生成 GRPO 训练数据格式(prompt + 状态信息)
- [ ] **DATA-06**: 目标生成 ~10,000 条训练数据,覆盖不同时段和交叉口
- [ ] **DATA-07**: 保存 GRPO 数据集为 JSON 格式

### SFT 数据和训练 (Supervised Fine-Tuning)

- [ ] **SFT-01**: 手工编写 50-100 条示例,格式为 `<think>推理过程</think>[{phase_id: 1, final: 40}, ...]`
- [ ] **SFT-02**: 将手工示例转换为 Unsloth SFT 训练格式
- [ ] **SFT-03**: 加载 Qwen3-4B 基础模型
- [ ] **SFT-04**: 配置 LoRA 训练参数(rank, alpha, target_modules)
- [ ] **SFT-05**: 训练模型学会输出格式(2 epochs 左右)
- [ ] **SFT-06**: 保存 SFT 后的模型和 tokenizer

### GRPO 训练 (Reinforcement Learning)

- [ ] **GRPO-01**: 实现格式奖励函数 - 验证输出格式正确性
- [ ] **GRPO-02**: 实现仿真效果奖励 - 并行启动 SUMO 评估方案效果
- [ ] **GRPO-03**: 组合多个奖励函数(格式 + 等待时间 + 通行量等)
- [ ] **GRPO-04**: 配置 GRPO 训练参数(learning_rate, num_generations, sampling_params)
- [ ] **GRPO-05**: 实现 GRPO 训练循环(生成 → 评估 → 更新)
- [ ] **GRPO-06**: 记录训练指标(reward, reward_std, completion_length, kl)
- [ ] **GRPO-07**: 保存最终 GRPO 模型

### Docker 部署 (Deployment)

- [ ] **DOCKER-01**: 检查依赖(CUDA, SUMO, Python packages)
- [ ] **DOCKER-02**: 配置 Docker 镜像(基于现有 Dockerfile 改写)
- [ ] **DOCKER-03**: 实现一键运行脚本(依赖检查 → 数据生成 → SFT → GRPO)
- [ ] **DOCKER-04**: 配置环境变量(SUMO_HOME, HF_HOME, PARALLEL等)
- [ ] **DOCKER-05**: 挂载数据和模型目录到容器
- [ ] **DOCKER-06**: 输出训练摘要(数据量, 训练时间, 模型路径)

## v2 Requirements

### 可视化和监控

- **VIS-01**: 训练过程可视化(loss curves, reward curves)
- **VIS-02**: SUMO 仿真可视化(可选 GUI 模式)
- **VIS-03**: 模型输出示例展示

### 模型评估

- **EVAL-01**: 在测试集上评估模型性能
- **EVAL-02**: 对比 baseline 策略(如 MaxPressure)
- **EVAL-03**: 生成评估报告

### 多场景支持

- **SCENE-01**: 支持添加新的 SUMO 场景
- **SCENE-02**: 跨场景泛化能力测试

## Out of Scope

| Feature | Reason |
|---------|--------|
| 实时在线控制 | 专注于离线模型训练,实时部署是后续工作 |
| 真实预测模型 | 用模拟预测降低复杂度,真实预测需要额外的时序模型 |
| 分布式训练 | 单机 multiprocessing 足够,避免引入 Ray/Dask 复杂性 |
| 多城市场景 | 只使用 chengdu,避免多场景泛化问题 |
| Web UI | 命令行工具优先,UI 是未来增强 |
| 模型 serving API | 训练完成后的部署不在 v1 范围 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PHASE-01 | Phase 1 | Complete |
| PHASE-02 | Phase 1 | Complete |
| PHASE-03 | Phase 1 | Complete |
| PHASE-04 | Phase 1 | Complete |
| PHASE-05 | Phase 1 | Complete |
| PHASE-06 | Phase 1 | Complete |
| PHASE-07 | Phase 1 | Complete |
| DATA-01 | Phase 2 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| DATA-04 | Phase 2 | Pending |
| DATA-05 | Phase 2 | Pending |
| DATA-06 | Phase 2 | Pending |
| DATA-07 | Phase 2 | Pending |
| SFT-01 | Phase 3 | Pending |
| SFT-02 | Phase 3 | Pending |
| SFT-03 | Phase 3 | Pending |
| SFT-04 | Phase 3 | Pending |
| SFT-05 | Phase 3 | Pending |
| SFT-06 | Phase 3 | Pending |
| GRPO-01 | Phase 4 | Pending |
| GRPO-02 | Phase 4 | Pending |
| GRPO-03 | Phase 4 | Pending |
| GRPO-04 | Phase 4 | Pending |
| GRPO-05 | Phase 4 | Pending |
| GRPO-06 | Phase 4 | Pending |
| GRPO-07 | Phase 4 | Pending |
| DOCKER-01 | Phase 5 | Pending |
| DOCKER-02 | Phase 5 | Pending |
| DOCKER-03 | Phase 5 | Pending |
| DOCKER-04 | Phase 5 | Pending |
| DOCKER-05 | Phase 5 | Pending |
| DOCKER-06 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-04*
*Last updated: 2026-02-04 after Phase 1 completion*
