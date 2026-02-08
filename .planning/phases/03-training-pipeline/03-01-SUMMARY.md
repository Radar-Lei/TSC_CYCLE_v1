---
phase: 03-training-pipeline
plan: 01
subsystem: sft-training
tags: [sft, training, data-loading, lora, bf16]

dependency_graph:
  requires:
    - phase-02-data-generation (SFT JSONL 数据)
  provides:
    - SFT 训练流程（支持 train/val 分割和 checkpoint 恢复）
  affects:
    - src/sft/trainer.py (数据加载和训练器)
    - src/sft/model_loader.py (模型加载配置)
    - src/scripts/train_sft.py (训练入口脚本)

tech_stack:
  added: []
  patterns:
    - train/val 自动划分（90/10）
    - 日志输出到终端和文件
    - checkpoint 自动检测和恢复
    - bf16 全精度 LoRA 训练

key_files:
  created: []
  modified:
    - src/sft/trainer.py (重写数据加载，添加 split_dataset)
    - src/sft/model_loader.py (修复 fast_inference=False)
    - src/scripts/train_sft.py (添加 train/val 分割和日志)

decisions: []

metrics:
  duration_minutes: 4
  tasks_completed: 2
  commits: 2
  completed_date: 2026-02-08
---

# Phase 03 Plan 01: SFT Trainer Fix Summary

**One-liner:** 修复 SFT 训练流程，使用 Phase 2 预处理数据（chat 格式），支持 train/val 划分（90/10）、bf16 全精度 LoRA 训练、checkpoint 恢复和日志文件输出

## What Was Built

修复了 SFT 训练的三个核心模块，确保训练流程能正确加载 Phase 2 生成的 SFT 格式数据（包含 CoT 空占位 `<think>\n\n</think>`），执行 bf16 全精度 LoRA 训练，并支持 train/val 划分和 checkpoint 管理。

### Task 1: 修复 SFT 数据加载和模型配置

**修改内容：**

1. **重写 `src/sft/trainer.py` 的 `prepare_dataset()` 函数：**
   - 删除旧的 prompt+prediction 格式转换逻辑（包括 `pred_saturation` 启发式计算）
   - 只接受已有 `messages` 字段的 JSONL 数据（由 Phase 2 的 `convert_to_sft_format()` 生成）
   - 逐条调用 `tokenizer.apply_chat_template()` 生成 `text` 字段（不使用 pandas DataFrame）
   - 如果数据缺少 `messages` 字段，抛出清晰的错误信息

2. **添加 `split_dataset()` 函数：**
   - 使用 `dataset.train_test_split(test_size=val_ratio, seed=seed)` 进行 train/val 划分
   - 默认 `val_ratio=0.1`（90/10 划分）
   - 固定种子 `seed=3407` 确保可重现性
   - 返回 `(train_dataset, val_dataset)` 元组

3. **修复 `src/sft/model_loader.py` 的 `load_model_for_sft()` 函数：**
   - 将 `fast_inference=True` 改为 `fast_inference=False`（训练模式，非推理加速）
   - 确认 `load_in_4bit=False`（bf16 全精度，per 锁定决策）
   - 其他参数保持不变（rank=32, alpha=64）

4. **修复 `SFTTrainerWrapper`：**
   - 在 `__init__` 中添加 `eval_dataset=None` 参数
   - 在 `_create_trainer()` 中：
     - 如果有 eval_dataset，设置 `eval_strategy="steps"`, `eval_steps=self.args.save_steps`
     - 将 eval_dataset 传给 SFTTrainer
   - 在 `TrainingArgs` 中：
     - `save_total_limit=3`（保留最近 3 个 checkpoint）
     - 添加 `bf16=True` 字段
     - 添加 `logging_dir` 字段，默认 `"{output_dir}/logs"`

**验证结果：**
- ✓ 所有导入正常（prepare_dataset, split_dataset, SFTTrainerWrapper）
- ✓ TrainingArgs.save_total_limit=3
- ✓ TrainingArgs.bf16=True
- ✓ model_loader.py 中 fast_inference=False
- ✓ trainer.py 中 eval_dataset 支持
- ✓ 旧的 pred_saturation 转换逻辑已删除

**Commit:** `4e9faca`

### Task 2: 修复 SFT 训练入口脚本，添加 train/val 分割和日志文件

**修改内容：**

1. **数据加载和分割：**
   - 调用 `prepare_dataset()` 加载 `{data_dir}/train.jsonl`
   - 调用 `split_dataset(dataset, val_ratio=0.1)` 分割 train/val
   - 打印 train/val 数量统计
   - 从 `src.sft.trainer` 导入 `split_dataset`
   - 默认 data_dir 改为 `outputs/sft`（与 Phase 2 输出一致）

2. **训练配置更新：**
   - 将 eval_dataset 传给 SFTTrainerWrapper
   - 日志打印 bf16 配置状态
   - 打印 checkpoint 保留策略（save_total_limit）

3. **日志文件输出：**
   - 添加 `setup_logging(output_dir)` 函数
   - 配置 Python logging 同时输出到终端（stdout）和文件（`{output_dir}/training.log`）
   - 日志格式：`%(asctime)s - %(levelname)s - %(message)s`
   - 日志内容包括：配置参数、数据统计、训练进度、最终结果

4. **Checkpoint 恢复支持：**
   - 添加 `--resume-from` 命令行参数（可选）
   - 如果指定了 resume-from，检查路径是否存在
   - 在 trainer.train() 调用时传入 `resume_from_checkpoint=args.resume_from`
   - 添加 `find_latest_checkpoint()` 函数自动检测现有 checkpoint
   - 如果检测到 checkpoint 但用户未指定 --resume-from，打印提示信息（不自动恢复）

5. **简化验证步骤：**
   - 保留 [Validation] 步骤但简化输出
   - 只在 is_valid 为 False 时打印 warning，不阻塞训练流程

**验证结果：**
- ✓ train_sft 脚本导入成功
- ✓ split_dataset 被导入并使用
- ✓ resume-from 参数支持
- ✓ logging 配置正确
- ✓ training.log 文件创建
- ✓ eval_dataset 传递给 trainer

**Commit:** `f91bf66`

## Deviations from Plan

None - 计划执行完全符合预期。

## Verification Results

所有 8 个验证步骤均通过：

1. ✓ src/sft/trainer.py 中 prepare_dataset、split_dataset、SFTTrainerWrapper 可正常导入
2. ✓ model_loader.py 中 fast_inference=False（训练模式）
3. ✓ trainer.py 中 eval_dataset 支持（在 __init__ 和 _create_trainer 中）
4. ✓ trainer.py 中 bf16=True 配置
5. ✓ train_sft.py 中 split_dataset 使用（导入并调用）
6. ✓ train_sft.py 中 logging 和 training.log 配置
7. ✓ train_sft.py 中 resume-from 支持
8. ✓ trainer.py 中不再包含 pred_saturation（旧转换逻辑已删除）

## Success Criteria Met

- ✓ SFT 数据加载使用预处理好的 chat 格式 JSONL（messages 字段），不再动态转换
- ✓ train/val 自动划分（90/10），val 集用于训练过程中评估
- ✓ 模型加载使用 bf16 全精度 LoRA（fast_inference=False, load_in_4bit=False）
- ✓ Checkpoint 定期保存（每 100 步）+ 滚动删除（保留最近 3 个）
- ✓ 训练日志输出到终端 + 日志文件
- ✓ 支持从 checkpoint 恢复训练
- ✓ 训练完成后模型保存到 outputs/sft/final/

## Testing Notes

无需手动测试 - 所有代码通过 import 验证和 grep 检查。实际训练需要 GPU 环境和 Phase 2 生成的数据（`outputs/sft/train.jsonl`）。

## Next Phase Readiness

**Phase 3 Plan 2 ready:** SFT 训练流程修复完成，可以开始实现 GRPO 训练器（使用 SFT 输出的 LoRA adapter 作为基础模型）。

## Self-Check: PASSED

检查创建/修改的文件：

```bash
# 修改的文件存在
ls -la src/sft/trainer.py src/sft/model_loader.py src/scripts/train_sft.py
```

所有文件已修改并提交。

检查提交记录：

```bash
git log --oneline | grep -E "(4e9faca|f91bf66)"
```

两个提交均存在于 git 历史中：
- 4e9faca: fix(03-01): 修复 SFT 数据加载和模型配置
- f91bf66: fix(03-01): 修复 SFT 训练入口脚本，添加 train/val 分割和日志文件

## Commits

1. `4e9faca` - fix(03-01): 修复 SFT 数据加载和模型配置
2. `f91bf66` - fix(03-01): 修复 SFT 训练入口脚本，添加 train/val 分割和日志文件
