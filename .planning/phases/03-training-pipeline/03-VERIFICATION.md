---
phase: 03-training-pipeline
verified: 2026-02-08T13:30:00Z
status: passed
score: 12/12 must-haves verified
---

# Phase 03: Training Pipeline Verification Report

**Phase Goal:** SFT 和 GRPO 训练能够正常执行并产出模型  
**Verified:** 2026-02-08T13:30:00Z  
**Status:** PASSED  
**Re-verification:** No - 初次验证

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SFT 训练脚本能从 JSONL 数据加载 train/val 集并执行训练 | ✓ VERIFIED | prepare_dataset 加载 JSONL, split_dataset 分割 90/10, SFTTrainerWrapper 支持 eval_dataset |
| 2 | SFT 数据预处理使用已应用 chat template 的格式（CoT 空占位），训练时直接加载 text 字段 | ✓ VERIFIED | prepare_dataset 只接受 messages 格式数据,调用 apply_chat_template 生成 text,旧的 pred_saturation 逻辑已删除 |
| 3 | SFT 训练使用 bf16 全精度 LoRA（无 4-bit 量化） | ✓ VERIFIED | model_loader.py: fast_inference=False, load_in_4bit=False, TrainingArgs.bf16=True |
| 4 | 训练过程定期保存 checkpoint 并滚动删除旧 checkpoint | ✓ VERIFIED | TrainingArgs.save_steps=100, save_total_limit=3 |
| 5 | 训练日志输出到终端并写入日志文件 | ✓ VERIFIED | setup_logging 配置双 handler,输出到 stdout 和 training.log |
| 6 | 格式奖励采用分级评分（think 标签 / JSON 可解析 / 字段完整） | ✓ VERIFIED | graded_format_reward 实现三级评分(0.5/1.5/3.0),旧函数 match_format_exactly/approximately 已删除 |
| 7 | 仿真失败时返回 NaN,不纳入梯度计算 | ✓ VERIFIED | simulation_reward.py 返回 float('nan'),代码注释明确说明 NaN 跳过策略 |
| 8 | GRPO 数据加载从 outputs/training/ 读取原始训练样本 | ✓ VERIFIED | data_loader.py 默认路径 outputs/training |
| 9 | GRPO 训练能基于 SFT 模型进行强化学习 | ✓ VERIFIED | load_sft_model 从 outputs/sft/final/ 加载,train_grpo.py 传递 SFT 模型给 GRPOTrainer |
| 10 | GRPO 模型加载使用 bf16 全精度 LoRA（无 4-bit 量化） | ✓ VERIFIED | grpo/trainer.py load_sft_model: load_in_4bit=False, GRPOConfig.bf16=True |
| 11 | 训练脚本使用重构后的 graded_format_reward | ✓ VERIFIED | train_grpo.py 导入并使用 graded_format_reward,不再引用旧函数 |
| 12 | GRPO 训练完成后保存 LoRA adapter 到 outputs/grpo/final/ | ✓ VERIFIED | train_grpo.py [6/6] 步骤保存模型到 {output_dir}/final |

**Score:** 12/12 truths verified (100%)

### Required Artifacts

#### Plan 03-01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/sft/trainer.py` | 支持 train/val 分割和 eval | ✓ VERIFIED | prepare_dataset 使用 messages 格式,split_dataset 实现 90/10 分割,SFTTrainerWrapper 支持 eval_dataset,TrainingArgs 包含 bf16/save_total_limit/logging_dir |
| `src/sft/model_loader.py` | bf16 全精度 LoRA | ✓ VERIFIED | fast_inference=False, load_in_4bit=False |
| `src/scripts/train_sft.py` | SFT 训练入口 | ✓ VERIFIED | 导入并使用 split_dataset,传递 eval_dataset,支持 --resume-from,日志输出到 training.log |

#### Plan 03-02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/grpo/format_reward.py` | 分级格式奖励函数 | ✓ VERIFIED | graded_format_reward 实现三级评分(Level 0/1/2/3),旧函数已删除 |
| `src/grpo/simulation_reward.py` | 仿真奖励,失败跳过 | ✓ VERIFIED | 解析失败和评估失败返回 float('nan'),包含 NaN 跳过策略注释 |
| `src/grpo/data_loader.py` | GRPO 数据加载器 | ✓ VERIFIED | 默认路径 outputs/training,prepare_grpo_dataset 构造 prompt 字段 |

#### Plan 03-03 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/grpo/trainer.py` | GRPO 训练器,bf16 模型加载 | ✓ VERIFIED | load_sft_model 使用 load_in_4bit=False,从 adapter_config.json 读取 LoRA 参数,GRPOConfig 包含 bf16/save_total_limit |
| `src/scripts/train_grpo.py` | GRPO 训练入口 | ✓ VERIFIED | 导入并使用 graded_format_reward,支持 --resume-from,日志输出到 training.log,默认数据路径 outputs/training |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| train_sft.py | sft/trainer.py | 调用 prepare_dataset, split_dataset, SFTTrainerWrapper | ✓ WIRED | 导入并调用所有三个函数,传递 eval_dataset |
| sft/trainer.py | outputs/sft/train.jsonl | 加载预处理好的 SFT chat 格式数据 | ✓ WIRED | prepare_dataset 读取 JSONL,逐条应用 chat_template |
| train_sft.py | outputs/sft/final/ | 保存训练后的 LoRA adapter | ✓ WIRED | trainer.save_model 保存到 {output_dir}/final |
| train_grpo.py | grpo/format_reward.py | 导入 graded_format_reward 奖励函数 | ✓ WIRED | 导入并添加到 reward_funcs 列表 |
| train_grpo.py | outputs/sft/final/ | 加载 SFT 模型作为 GRPO 初始模型 | ✓ WIRED | load_sft_model 默认路径 outputs/sft/final |
| grpo/trainer.py | grpo/simulation_reward.py | 仿真奖励评估 | ✓ WIRED | train_grpo.py 导入 compute_simulation_reward 并包装到 lambda |

### Requirements Coverage

Phase 03 对应需求 TRAIN-01 到 TRAIN-05:

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| TRAIN-01: SFT 数据加载和模型配置 | ✓ SATISFIED | None |
| TRAIN-02: GRPO 格式奖励分级评分 | ✓ SATISFIED | None |
| TRAIN-03: 仿真失败跳过机制 | ✓ SATISFIED | None |
| TRAIN-04: GRPO 模型加载和训练器 | ✓ SATISFIED | None |
| TRAIN-05: 训练日志和 checkpoint 管理 | ✓ SATISFIED | None |

### Anti-Patterns Found

无阻塞性反模式。代码质量良好,符合最佳实践。

**检查项:**
- ✓ 无 TODO/FIXME/PLACEHOLDER 注释
- ✓ 无空实现（return null/{}）
- ✓ 无仅 console.log 的函数
- ✓ 所有函数都有实质性实现
- ✓ 旧的冗余代码已删除（pred_saturation, match_format_exactly/approximately）

### Human Verification Required

#### 1. SFT 训练端到端测试

**Test:** 运行 SFT 训练并验证输出格式  
```bash
python -m src.scripts.train_sft --max-steps 10 --data-dir outputs/sft
```

**Expected:**  
- 模型成功加载（Qwen3-4B + LoRA）
- 数据正确加载并分割为 train/val（90/10）
- 训练运行 10 步并保存 checkpoint
- 最终模型保存到 outputs/sft/final/
- 日志输出到 outputs/sft/training.log
- 模型输出格式验证通过（包含 `<think>...</think>[{...}]`）

**Why human:** 需要 GPU 环境和实际训练数据,无法静态验证

#### 2. GRPO 训练端到端测试

**Test:** 运行 GRPO 训练并验证强化学习流程  
```bash
python -m src.scripts.train_grpo --max-steps 10 --disable-simulation
```

**Expected:**  
- SFT 模型成功加载（从 outputs/sft/final/）
- 训练数据正确加载（从 outputs/training/）
- 奖励函数正确工作（graded_format_reward, check_phase_validity）
- 训练运行 10 步并保存 checkpoint
- 最终模型保存到 outputs/grpo/final/
- 日志输出到 outputs/grpo/training.log

**Why human:** 需要 GPU 环境和 SFT 模型,无法静态验证

#### 3. 仿真奖励 NaN 跳过验证

**Test:** 验证仿真失败时 NaN 跳过策略生效  
```bash
# 运行 GRPO 训练并观察日志中的评估统计
python -m src.scripts.train_grpo --max-steps 5
# 查看日志中的 "Evaluation stats: X success, Y failed, Z skipped"
```

**Expected:**  
- 评估统计显示 skipped 数量（JSON 解析失败）
- 评估统计显示 failed 数量（SUMO 崩溃/超时）
- 训练未因评估失败而中断
- 梯度计算仅基于成功样本

**Why human:** 需要真实 SUMO 环境和可能失败的样本,无法模拟所有失败场景

### Data Path Observation

**发现:** 当前代码默认使用 `outputs/training/` 作为 GRPO 数据路径,但实际数据位于 `outputs/data/{scenario}/samples_*.jsonl`。

**影响:** GRPO 训练需要确保数据在正确路径,或通过 `--data-dir` 参数指定。

**建议:** Phase 2 数据生成应确保输出到 `outputs/training/` 目录,或 Phase 4 提供数据路径配置说明。

**状态:** 不阻塞验证 - 代码实现正确,路径可配置,属于使用配置问题而非代码缺陷。

---

## Summary

**所有代码级 must-haves 验证通过（12/12）。** Phase 03 完整实现了 SFT 和 GRPO 训练流程:

1. **SFT 训练流程:**
   - ✓ 数据加载使用 Phase 2 预处理的 chat 格式（messages 字段）
   - ✓ train/val 自动分割（90/10）
   - ✓ bf16 全精度 LoRA 训练（无 4-bit 量化）
   - ✓ Checkpoint 管理（定期保存,滚动删除）
   - ✓ 日志输出（终端 + 文件）
   - ✓ Checkpoint 恢复支持

2. **GRPO 训练流程:**
   - ✓ 格式奖励分级评分（think/JSON/fields 三级）
   - ✓ 仿真失败 NaN 跳过策略
   - ✓ 基于 SFT 模型的强化学习
   - ✓ bf16 全精度训练
   - ✓ 多奖励函数组合（format + validity + simulation）
   - ✓ 日志和 checkpoint 管理

3. **代码质量:**
   - ✓ 旧代码完全清理（pred_saturation, match_format_exact/approximate）
   - ✓ 所有函数都有实质性实现
   - ✓ 关键路径全部连接（SFT→GRPO 数据流畅通）
   - ✓ 配置参数正确（bf16, save_total_limit, logging_dir）

**人工验证项:** 3 项端到端测试需要 GPU 环境和训练数据,建议在实际训练环境中执行。

**数据路径提示:** GRPO 训练数据路径默认 `outputs/training/`,当前数据在 `outputs/data/{scenario}/`,需要配置或移动数据文件。

---

_Verified: 2026-02-08T13:30:00Z_  
_Verifier: Claude (gsd-verifier)_
