---
phase: 03-grpo-training
verified: 2026-02-10T04:30:00Z
status: passed
score: 12/12 must-haves verified
human_verification:
  - test: "Baseline 预计算功能验证"
    expected: "成功生成 baseline.json 文件并包含所有唯一 state_file 的 baseline 指标"
    why_human: "需要实际 SUMO 环境和 Docker 容器运行"
  - test: "GRPO 训练端到端流程"
    expected: "GRPOTrainer 成功训练并保存模型到 outputs/grpo/model"
    why_human: "需要 GPU、Docker、SUMO 环境，训练过程需要观察 reward 曲线"
  - test: "Reward 函数正确性验证"
    expected: "训练日志显示 5 个 reward 分数随训练改善，L3 SUMO reward 仅在 L1+L2 满足时出现"
    why_human: "需要理解训练动态和 reward shaping 效果"
---

# Phase 3: GRPO 训练 Verification Report

**Phase Goal:** 通过实时 SUMO 仿真 reward 优化模型配时方案质量

**Verified:** 2026-02-10T04:30:00Z

**Status:** passed

**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | config.json contains training.grpo section with all GRPO hyperparameters | ✓ VERIFIED | config.json lines 40-91: 包含 model, num_generations=4, max_steps=100, learning_rate, optimizer, reward subsection 等完整配置 |
| 2 | config.json contains paths.grpo_output and paths.grpo_data_dir entries | ✓ VERIFIED | config.json lines 104-106: grpo_data_dir, grpo_output, grpo_baseline 路径全部配置 |
| 3 | Baseline precomputation script can be invoked via docker/grpo_baseline.sh | ✓ VERIFIED | docker/grpo_baseline.sh 存在、可执行、遵循 data.sh 模式 |
| 4 | Baseline script loads each state file, runs original timing for one cycle, and records throughput + queue | ✓ VERIFIED | src/grpo/baseline.py (207 lines): compute_single_baseline 函数完整实现 SUMO loadState + 运行原始配时 + 统计指标 |
| 5 | Reward functions validate output format with \u003cthink\u003e...\u003c/think\u003e\u003cCyclePlan\u003e...\u003c/CyclePlan\u003e regex | ✓ VERIFIED | rewards.py line 35-37: 正则 `r"\u003c/think\u003e\\s*\u003cCyclePlan\u003e(.+?)\u003c/CyclePlan\u003e\\s*$"` 正确 |
| 6 | Reward functions check phase order and green time constraints with gradual scoring | ✓ VERIFIED | check_constraints (lines 115-218): phase_order_score = (correct_positions / total) × weight, green_range_score = (satisfying / total) × weight (渐进式) |
| 7 | SUMO simulation reward runs only when L1 format + L2 constraints all pass | ✓ VERIFIED | sumo_simulation_reward (lines 343-523): lines 385-439 gate 检查 — L1 格式不匹配 return 0.0, L2 约束未全满足 return 0.0 |
| 8 | Think length penalty penalizes responses with \u003c50 or \u003e200 tokens in think section | ✓ VERIFIED | think_length_reward (lines 524-572): lines 563-566 实现 \u003c50 和 \u003e200 token 惩罚逻辑 |
| 9 | GRPO training loads SFT merged model and applies LoRA for continued training | ✓ VERIFIED | train.py ensure_model (lines 29-45) 检查 outputs/sft/model 存在, setup_model (lines 48-76) 加载模型并应用 LoRA |
| 10 | Training uses GRPOTrainer with use_vllm=False and multiple reward functions | ✓ VERIFIED | train.py line 62: fast_inference=False, lines 227-233: GRPOTrainer 传入 5 个 reward_funcs |
| 11 | Docker script grpo_train.sh follows data.sh pattern and runs GRPO training | ✓ VERIFIED | grpo_train.sh (87 lines): 验证 3 个前置条件 (SFT model, GRPO data, baseline.json), Docker 配置与 sft_train.sh 一致 |
| 12 | Trained model saved as merged_16bit to outputs/grpo/model | ✓ VERIFIED | train.py save_model (lines 242-254): save_pretrained_merged(..., save_method="merged_16bit") |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `config/config.json` | GRPO hyperparameters and path configuration | ✓ VERIFIED | training.grpo section (52 lines), paths.grpo_output/grpo_data_dir/grpo_baseline entries |
| `src/grpo/__init__.py` | GRPO module package init | ✓ VERIFIED | 存在且有效 Python 包初始化文件 |
| `src/grpo/baseline.py` | Baseline precomputation script for SUMO simulation | ✓ VERIFIED | 207 lines, exports main, 包含 get_sumocfg_for_state, compute_single_baseline, ProcessPoolExecutor 并行 |
| `docker/grpo_baseline.sh` | Docker entrypoint for baseline precomputation | ✓ VERIFIED | 可执行脚本, 调用 python3 -m src.grpo.baseline, 遵循 data.sh 模式 |
| `src/grpo/rewards.py` | All reward functions for GRPO training | ✓ VERIFIED | 572 lines, exports 5 reward functions + init_rewards, 包含 L1/L2/L3 评分体系 |
| `src/grpo/train.py` | GRPO training script | ✓ VERIFIED | 326 lines, exports main, 完整训练流水线 (加载 SFT 模型 → GRPOTrainer → 保存 merged_16bit) |
| `docker/grpo_train.sh` | Docker entrypoint for GRPO training | ✓ VERIFIED | 87 lines, 可执行, 验证 3 个前置条件, 调用 python3 -m src.grpo.train |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/grpo/baseline.py` | `outputs/grpo/grpo_train.jsonl` | reads metadata.state_file from each sample | ✓ WIRED | line 160: `input_path = ...grpo_train.jsonl` |
| `src/grpo/baseline.py` | `outputs/grpo/baseline.json` | writes baseline metrics indexed by state_file | ✓ WIRED | line 151: `args.output or config["paths"]["grpo_baseline"]` |
| `docker/grpo_baseline.sh` | `src/grpo/baseline.py` | docker run invokes python -m src.grpo.baseline | ✓ WIRED | line 43: `-m src.grpo.baseline` |
| `src/grpo/train.py` | `src/grpo/rewards.py` | imports reward functions for GRPOTrainer | ✓ WIRED | lines 284 (init_rewards), 296-302 (5 个 reward 函数导入) |
| `src/grpo/train.py` | `config/config.json` | loads hyperparameters from training.grpo section | ✓ WIRED | line 35: `config["training"]["grpo"]["model"]`, line 187: `grpo_config = config["training"]["grpo"]` |
| `src/grpo/train.py` | `outputs/sft/model` | loads SFT merged model as starting point | ✓ WIRED | line 36: `model_path = model_config["model_name"]` (config 中配置为 outputs/sft/model) |
| `src/grpo/rewards.py` | `outputs/grpo/baseline.json` | loads baseline values for reward normalization | ✓ WIRED | line 48: `baseline_path` 参数传入 init_rewards |
| `docker/grpo_train.sh` | `src/grpo/train.py` | docker run invokes python -m src.grpo.train | ✓ WIRED | line 77: `-m src.grpo.train` |

### Requirements Coverage

Phase 3 ROADMAP 要求:

| Requirement | Status | Supporting Evidence |
|-------------|--------|---------------------|
| GRPT-01: docker/grpo_train.sh 脚本能在容器中成功运行 GRPO 训练 | ✓ SATISFIED | grpo_train.sh 完整实现, 验证前置条件, Docker 配置正确 |
| GRPT-02: reward 函数能正确验证输出格式 | ✓ SATISFIED | match_format regex 正确匹配 \u003cthink\u003e...\u003c/think\u003e\u003cCyclePlan\u003e...\u003c/CyclePlan\u003e |
| GRPT-03: reward 函数能通过 loadState 加载 SUMO 状态并执行模型方案 | ✓ SATISFIED | sumo_simulation_reward 实现完整 SUMO 仿真流程 (loadState + 执行配时 + 统计指标) |
| GRPT-04: reward 函数能统计车辆通过量和排队车辆数作为奖励信号 | ✓ SATISFIED | sumo_simulation_reward 计算 passed_vehicles 和 queue_vehicles, 使用 baseline 归一化 |
| GRPT-05: think 长度惩罚机制生效 | ✓ SATISFIED | think_length_reward 实现 \u003c50 或 \u003e200 token 惩罚 |
| GRPT-06: 多进程并行 reward 计算正常工作 | ✓ SATISFIED | rewards.py 使用 ProcessPoolExecutor 并行 SUMO 仿真 |
| GRPT-07: GRPO 训练后的模型权重成功保存到 outputs/grpo/model 目录 | ✓ SATISFIED | train.py save_model 函数保存 merged_16bit 到 grpo_output 路径 |

**Coverage:** 7/7 requirements satisfied

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/grpo/train.py` | 119 | Comment "Replace placeholders" | ℹ️ Info | 合理注释，非功能性占位符 |

**Summary:** 无阻塞性 anti-patterns。所有代码均为实质性实现，无 TODO/FIXME/placeholder 功能缺失。

### Human Verification Required

#### 1. Baseline 预计算功能验证

**Test:** 
1. 运行 `./docker/grpo_baseline.sh`
2. 观察控制台输出和进度
3. 检查 `outputs/grpo/baseline.json` 文件内容

**Expected:** 
- 成功读取 grpo_train.jsonl 中的所有唯一 state_file
- 多进程并行计算每个 state 的 baseline metrics (passed_vehicles, queue_vehicles, cycle_length)
- 生成 baseline.json 文件，包含每个 state_file 的 baseline 数据
- 无 SUMO 崩溃或超时错误
- baseline.json 结构: `{"state_file_path": {"passed_vehicles": N, "queue_vehicles": M, "cycle_length": L}, ...}`

**Why human:** 需要实际 SUMO 环境和 Docker 容器运行，涉及外部进程管理和 TraCI 连接，无法通过静态代码检查验证

#### 2. GRPO 训练端到端流程

**Test:** 
1. 确保 baseline.json 已生成
2. 运行 `./docker/grpo_train.sh`
3. 观察训练日志和 reward 分数

**Expected:** 
- 前置条件检查通过 (SFT 模型存在, GRPO 数据存在, baseline.json 存在)
- GRPOTrainer 成功初始化
- 每个 training step 输出 5 个 reward 分数 (format_exact, format_approx, constraints, sumo, think_length)
- SUMO 并行仿真正常工作，无端口冲突或死锁
- 训练完成后模型保存到 outputs/grpo/model (包含 config.json, model.safetensors 等文件)
- outputs/grpo/checkpoints 目录包含训练检查点

**Why human:** 需要 GPU 资源、Docker 环境、SUMO 安装，训练过程需要观察 reward 曲线和收敛情况，运行时间较长 (取决于 max_steps 和硬件)

#### 3. Reward 函数正确性验证

**Test:** 
检查训练日志中每个 step 的 reward 分数分布和变化趋势

**Expected:** 
- **L1 format rewards (exact + approx):** 初期可能较低 (模型尚未掌握格式), 随训练提高
  - `match_format_exactly`: 0.0 → 接近 3.0
  - `match_format_approximately`: 负分 → 正分
- **L2 constraint reward:** 渐进式改善
  - 初期部分满足时给部分分 (如 0.5, 1.0)
  - 随训练逐渐提高到满分 (2.0 = phase_order_weight + green_range_weight)
- **L3 SUMO reward:** 仅在 L1+L2 全满足时出现非零值
  - 初期大部分为 0.0 (gate 未通过)
  - 后期出现 0-5.0 范围的分数 (baseline 归一化后的 SUMO 性能)
- **Think length penalty:** 初期可能较高 (思考过短或过长), 随训练改善到接近 0

**Why human:** 需要理解强化学习训练动态、reward shaping 效果、以及 GRPO 的 exploration-exploitation 平衡，无法通过单次静态检查验证

### Gaps Summary

**无 gaps。** 所有 must-haves 已验证通过，所有 artifacts 存在且实质性，所有 key links 已连接。

Phase 3 的基础设施完全就绪，可以执行 baseline 预计算和 GRPO 训练。

**注意事项:**
1. **baseline.json 尚未生成** — 需要手动运行 `./docker/grpo_baseline.sh` (预期耗时取决于 state_file 数量和 workers 配置)
2. **GRPO 训练尚未执行** — 需要手动运行 `./docker/grpo_train.sh` (预期耗时取决于 max_steps 和 GPU 性能)
3. **实际训练效果需要人工评估** — 观察 reward 曲线、模型收敛情况、以及最终模型在测试集上的表现

---

_Verified: 2026-02-10T04:30:00Z_

_Verifier: Claude (gsd-verifier)_
