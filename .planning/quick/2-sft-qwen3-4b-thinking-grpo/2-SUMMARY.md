---
phase: quick-2
plan: 01
type: summary
subsystem: training-pipeline
tags: [grpo, qwen3-thinking, model-loading, workflow-optimization]

dependency_graph:
  requires:
    - "Phase 2 数据生成流程 (outputs/training/)"
  provides:
    - "直接从 Qwen3-4B-Thinking-2507 开始 GRPO 训练的能力"
    - "跳过 SFT 阶段的简化流程"
  affects:
    - "docker/run.sh 默认训练流程"
    - "GRPO 训练入口逻辑"

tech_stack:
  added:
    - component: "load_base_model 函数"
      purpose: "直接加载预训练 Thinking 模型并应用 LoRA"
  patterns:
    - "智能模型加载: --model-name 优先于 --sft-adapter"
    - "保留内置 chat template: 不覆盖 tokenizer 的 chat_template"
    - "向后兼容: 两种加载路径共存"

key_files:
  created: []
  modified:
    - path: "src/grpo/trainer.py"
      changes: "添加 load_base_model 函数"
    - path: "src/scripts/train_grpo.py"
      changes: "添加 --model-name 参数，智能模型加载逻辑"
    - path: "config/config.json"
      changes: "添加 training.grpo.model_name 配置"
    - path: "docker/grpo.sh"
      changes: "更新注释说明支持两种加载模式"
    - path: "docker/run.sh"
      changes: "默认 STAGE 改为 direct，支持跳过 SFT"

decisions:
  - id: "qwen3-thinking-direct-grpo"
    question: "是否跳过 SFT，直接用 Qwen3-4B-Thinking-2507 做 GRPO？"
    chosen: "是 - 直接使用 Thinking 模型"
    rationale: "Qwen3-4B-Thinking-2507 已内置思考能力和 <think> 标签支持，无需通过 SFT 从 Base 模型训练格式。节省训练时间，减少流程复杂度，同时利用模型已有的推理能力。"
    alternatives:
      - option: "保持 SFT -> GRPO 流程"
        pros: "训练流程完整，可能微调格式更精确"
        cons: "多一个训练阶段，耗时更长，Thinking 模型已有推理能力被浪费"

  - id: "preserve-sft-path"
    question: "是否保留 --sft-adapter 路径？"
    chosen: "是 - 保留向后兼容"
    rationale: "允许用户选择使用 SFT 模型或基础 Thinking 模型，灵活性更高。现有流程不受影响。"

  - id: "default-workflow"
    question: "docker/run.sh 默认流程是什么？"
    chosen: "direct (data -> grpo)"
    rationale: "对于 Thinking 模型，跳过 SFT 是更合理的默认选择。用户仍可通过 --stage all 走完整流程。"

metrics:
  duration: "7 minutes"
  tasks_completed: 2
  completed_date: "2026-02-08"
---

# Quick Task 2: 跳过 SFT，直接使用 Qwen3-4B-Thinking-2507 训练 GRPO

**一句话总结:** 添加直接从 Qwen3-4B-Thinking-2507 加载模型的能力，跳过 SFT 阶段，简化 GRPO 训练流程。

## 目标

跳过 SFT 阶段，改用 Qwen3-4B-Thinking-2507 直接进行 GRPO 训练。

**原因:** Qwen3-4B-Thinking-2507 已内置思考能力和 `<think>` 标签支持，无需通过 SFT 从 Base 模型训练格式。直接用 Thinking 模型做 GRPO 可以节省训练时间、减少流程复杂度，同时利用模型已有的推理能力。

## 实现细节

### Task 1: 添加 load_base_model 函数并更新 GRPO 数据加载

**文件修改:**
- `src/grpo/trainer.py`: 新增 `load_base_model()` 函数
- `config/config.json`: 添加 `training.grpo.model_name` 配置

**实现要点:**

1. **load_base_model 函数** (src/grpo/trainer.py):
   ```python
   def load_base_model(
       model_name: str = "unsloth/Qwen3-4B-Thinking-2507",
       lora_r: int = 32,
       lora_alpha: int = 64,
   ) -> Tuple[Any, Any]:
   ```
   - 使用 `FastLanguageModel.from_pretrained()` 加载基础模型
   - 使用 bf16 全精度（`load_in_4bit=False`）
   - 应用 LoRA 配置（r=32, alpha=64）
   - **关键:** 不调用 `setup_tokenizer()` - 保留模型内置 chat template
   - 不覆盖 `tokenizer.chat_template`

2. **配置更新** (config/config.json):
   - 在 `training.grpo` 下添加 `"model_name": "unsloth/Qwen3-4B-Thinking-2507"`

3. **向后兼容:**
   - 保留原有 `load_sft_model()` 函数不变
   - 两种加载路径可以共存

**验证通过:**
- ✓ trainer.py 语法正确
- ✓ load_base_model 函数存在并可导入
- ✓ config.json 包含 model_name 配置
- ✓ data_loader.py 不受影响

**提交:** `bce813d` - feat(quick-2): 添加 load_base_model 支持直接加载 Thinking 模型

### Task 2: 更新训练入口脚本和 Docker 流程

**文件修改:**
- `src/scripts/train_grpo.py`: 添加 `--model-name` 参数，智能模型加载
- `docker/grpo.sh`: 更新注释说明
- `docker/run.sh`: 默认流程改为 `direct`

**实现要点:**

1. **train_grpo.py 更新:**
   - 导入 `load_base_model` 到 import 列表
   - 添加 `--model-name` 参数（CLI）
   - 在 `apply_config()` 中读取 `training.grpo.model_name` 配置
   - 修改 `main()` 中的模型加载逻辑:
     ```python
     if args.model_name:
         # 直接加载基础模型（跳过 SFT）
         model, tokenizer = load_base_model(args.model_name)
     else:
         # 从 SFT adapter 加载（原有路径）
         model, tokenizer = load_sft_model(args.sft_adapter)
     ```
   - 优先级: `--model-name` > `--sft-adapter`
   - 更新 docstring 添加使用示例

2. **docker/grpo.sh 更新:**
   - 更新注释说明输入可以是基础模型或 SFT 模型
   - 脚本本身无需改动（`"$@"` 已支持传递参数）

3. **docker/run.sh 更新:**
   - 默认 `STAGE="direct"`（而非 `"all"`）
   - 添加 `direct` 模式到阶段判断逻辑:
     - 阶段 1 (数据): `all || direct || data`
     - 阶段 2 (SFT): `all || sft`（direct 模式跳过）
     - 阶段 3 (GRPO): `all || direct || grpo`
   - 更新输出信息: direct 模式不显示 SFT 输出
   - 更新注释说明支持 `direct` 和 `all` 两种流程

**验证通过:**
- ✓ train_grpo.py 语法正确
- ✓ `--model-name` 参数存在
- ✓ `--sft-adapter` 参数保留（向后兼容）
- ✓ shell 脚本语法正确

**提交:** `1d1abc0` - feat(quick-2): 更新 GRPO 训练流程支持 Thinking 模型

## 使用方法

### 方式 1: 直接使用 Thinking 模型（推荐）

```bash
# 单独运行 GRPO 训练
python -m src.scripts.train_grpo --model-name unsloth/Qwen3-4B-Thinking-2507

# 完整流程（data -> grpo，跳过 SFT）
./docker/run.sh                    # 默认使用 direct 模式
./docker/run.sh --stage direct     # 显式指定
```

### 方式 2: 使用 SFT 模型（向后兼容）

```bash
# 单独运行 GRPO 训练
python -m src.scripts.train_grpo --sft-adapter outputs/sft/model/final

# 完整流程（data -> sft -> grpo）
./docker/run.sh --stage all
```

### 配置文件模式

在 `config/config.json` 中配置了 `training.grpo.model_name` 后，无需命令行传参:

```bash
python -m src.scripts.train_grpo   # 自动使用 config 中的 model_name
```

## 成功标准验证

- ✅ GRPO 训练入口支持直接从 Qwen3-4B-Thinking-2507 加载（跳过 SFT）
- ✅ 模型的内置 chat template 被保留使用（不被自定义模板覆盖）
- ✅ 向后兼容: --sft-adapter 路径仍然完全可用
- ✅ docker/run.sh 默认流程为 data -> grpo
- ✅ config.json 包含 model_name 配置

## 偏差记录

无偏差 - 计划执行完全符合预期。

## 提交记录

| Task | 提交哈希 | 提交信息 |
|------|---------|---------|
| 1 | `bce813d` | feat(quick-2): 添加 load_base_model 支持直接加载 Thinking 模型 |
| 2 | `1d1abc0` | feat(quick-2): 更新 GRPO 训练流程支持 Thinking 模型 |

## 影响范围

**核心改动:**
- GRPO 训练流程现在可以跳过 SFT 阶段
- 默认训练流程从 `data -> sft -> grpo` 改为 `data -> grpo`

**向后兼容性:**
- 完全保留：SFT 模型路径仍然可用
- 用户可以通过 `--stage all` 或 `--sft-adapter` 走原有流程

**配置变更:**
- `config/config.json` 新增 `training.grpo.model_name` 字段

## 后续工作

1. **实际训练验证:** 在 GPU 环境中实际运行一次 GRPO 训练，确认:
   - 模型加载成功
   - Tokenizer 的内置 chat template 正确工作
   - 训练过程正常收敛

2. **性能对比（可选）:** 对比 SFT -> GRPO 和 Direct GRPO 两种路径的效果差异

3. **文档更新（可选）:** 在项目文档中说明两种训练路径的选择建议

## Self-Check: PASSED

**文件存在性检查:**
- ✓ src/grpo/trainer.py (已修改，包含 load_base_model)
- ✓ src/scripts/train_grpo.py (已修改，包含 --model-name)
- ✓ config/config.json (已修改，包含 model_name)
- ✓ docker/grpo.sh (已修改)
- ✓ docker/run.sh (已修改)

**提交存在性检查:**
- ✓ bce813d: feat(quick-2): 添加 load_base_model 支持直接加载 Thinking 模型
- ✓ 1d1abc0: feat(quick-2): 更新 GRPO 训练流程支持 Thinking 模型

**功能验证:**
- ✓ load_base_model 函数存在并语法正确
- ✓ --model-name 和 --sft-adapter 参数都存在
- ✓ config.json 包含 training.grpo.model_name 配置
- ✓ Shell 脚本语法正确

所有检查项通过，计划执行成功。
