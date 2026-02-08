---
phase: quick-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/grpo/trainer.py
  - src/grpo/data_loader.py
  - src/scripts/train_grpo.py
  - config/config.json
  - docker/grpo.sh
  - docker/run.sh
autonomous: true

must_haves:
  truths:
    - "GRPO 训练可以直接加载 Qwen3-4B-Thinking-2507 模型，无需先运行 SFT"
    - "模型使用自身内置 chat template（含 <think> 支持），不覆盖为自定义模板"
    - "docker/run.sh 默认流程跳过 SFT，直接 data -> grpo"
    - "仍可通过 --sft-adapter 参数走旧的 SFT->GRPO 路径（向后兼容）"
  artifacts:
    - path: "src/grpo/trainer.py"
      provides: "load_base_model 函数 + 原 load_sft_model 保留"
      exports: ["load_base_model", "load_sft_model"]
    - path: "src/scripts/train_grpo.py"
      provides: "--model-name 参数，智能选择加载路径"
    - path: "config/config.json"
      provides: "training.grpo.model_name 配置项"
      contains: "Qwen3-4B-Thinking"
  key_links:
    - from: "src/scripts/train_grpo.py"
      to: "src/grpo/trainer.py"
      via: "load_base_model 或 load_sft_model 调用"
      pattern: "load_base_model|load_sft_model"
    - from: "src/grpo/data_loader.py"
      to: "tokenizer.apply_chat_template"
      via: "使用 tokenizer 内置模板，不覆盖"
      pattern: "apply_chat_template"
---

<objective>
跳过 SFT 阶段，改用 Qwen3-4B-Thinking-2507 直接进行 GRPO 训练。

Purpose: Qwen3-4B-Thinking-2507 已内置思考能力和 <think> 标签支持，无需通过 SFT 从 Base 模型训练格式。直接用 Thinking 模型做 GRPO 可以节省训练时间、减少流程复杂度，同时利用模型已有的推理能力。

Output: 修改后的 GRPO 训练流程，支持直接从预训练 Thinking 模型加载并训练。
</objective>

<execution_context>
@/home/samuel/.claude/get-shit-done/workflows/execute-plan.md
@/home/samuel/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/grpo/trainer.py
@src/grpo/data_loader.py
@src/scripts/train_grpo.py
@src/sft/chat_template.py
@src/sft/model_loader.py
@config/config.json
@docker/grpo.sh
@docker/run.sh
</context>

<tasks>

<task type="auto">
  <name>Task 1: 添加 load_base_model 函数并更新 GRPO 数据加载</name>
  <files>
    src/grpo/trainer.py
    src/grpo/data_loader.py
    config/config.json
  </files>
  <action>
**src/grpo/trainer.py** - 添加 `load_base_model` 函数（保留原 `load_sft_model` 不变）:

```python
def load_base_model(
    model_name: str = "unsloth/Qwen3-4B-Thinking-2507",
    lora_r: int = 32,
    lora_alpha: int = 64,
) -> Tuple[Any, Any]:
```

实现要点:
1. 用 `FastLanguageModel.from_pretrained(model_name=model_name, max_seq_length=2048, load_in_4bit=False, device_map=None, fast_inference=False, gpu_memory_utilization=0.9)` 加载模型
2. 用 `FastLanguageModel.get_peft_model(model, r=lora_r, lora_alpha=lora_alpha, target_modules=[...同现有列表...], lora_dropout=0.0, bias="none", use_gradient_checkpointing="unsloth", random_state=3407)` 应用 LoRA
3. 关键: **不要**调用 `setup_tokenizer(tokenizer)` — Qwen3-4B-Thinking-2507 已有内置 chat template，使用模型自带的即可
4. 不要设置 `tokenizer.chat_template = ...`
5. 打印加载信息: `f"Model {model_name} loaded (bf16, LoRA r={lora_r}, alpha={lora_alpha})"`
6. 返回 `(model, tokenizer)`

**src/grpo/data_loader.py** - 添加 `use_builtin_template` 参数:

修改 `prepare_grpo_dataset` 函数签名，添加参数 `use_builtin_template: bool = True`:
- 当 `use_builtin_template=True`（默认）: 使用 tokenizer 自带的 `apply_chat_template`，**不要**从 `src.sft.chat_template` 导入或使用 `SYSTEM_PROMPT`。直接构建 messages（仍包含 system role，但 content 用 `SYSTEM_PROMPT`），然后 `tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)`。实际上 SYSTEM_PROMPT 内容本身仍然有用（任务描述），只是不再覆盖 tokenizer 的 chat_template。所以仍然导入 SYSTEM_PROMPT 用于 system message 的 content。
- 当 `use_builtin_template=False`: 保持现有行为不变（向后兼容）

关键区别: 之前代码在 SFT 阶段通过 `setup_tokenizer` 覆盖了 tokenizer 的 chat_template 为自定义模板。现在用 Thinking 模型时，tokenizer 自带的 chat_template 已经正确处理 `<think>` 标签，所以 `apply_chat_template` 的输出格式会不同但是正确的。不需要改 `apply_chat_template` 的调用方式，只需确保 tokenizer 的 chat_template 没被覆盖。

实际上仔细看代码，`prepare_grpo_dataset` 并没有覆盖 tokenizer 的 chat_template——它只是调用 `tokenizer.apply_chat_template`。覆盖发生在 `load_model_for_sft` -> `setup_tokenizer` 中。所以 `data_loader.py` 实际上不需要改动逻辑，因为它已经正确地调用了 `tokenizer.apply_chat_template`。只要 tokenizer 的 template 没被覆盖（load_base_model 不覆盖），输出就会使用模型内置格式。

所以 `data_loader.py` 的实际改动: 无需功能性修改。但建议更新 docstring 说明支持两种模式。`SYSTEM_PROMPT` 的导入保留（用于 system message 内容）。

**config/config.json** - 在 `training.grpo` 下添加:
```json
"model_name": "unsloth/Qwen3-4B-Thinking-2507"
```
  </action>
  <verify>
运行 `python -c "from src.grpo.trainer import load_base_model, load_sft_model, GRPOConfig; print('imports ok')"` 确认导入成功。

运行 `python -c "from src.grpo.data_loader import prepare_grpo_dataset; print('data_loader ok')"` 确认不影响现有功能。

运行 `python -c "import json; c=json.load(open('config/config.json')); assert c['training']['grpo']['model_name'] == 'unsloth/Qwen3-4B-Thinking-2507'; print('config ok')"` 确认配置正确。
  </verify>
  <done>
    - load_base_model 函数存在并可导入，接受 model_name 参数
    - load_sft_model 函数保持不变（向后兼容）
    - config.json 包含 model_name 配置
    - data_loader 使用 tokenizer 内置 chat template（不覆盖）
  </done>
</task>

<task type="auto">
  <name>Task 2: 更新训练入口脚本和 Docker 流程</name>
  <files>
    src/scripts/train_grpo.py
    docker/grpo.sh
    docker/run.sh
  </files>
  <action>
**src/scripts/train_grpo.py** 修改:

1. 更新 import: 添加 `load_base_model` 到导入列表:
   ```python
   from src.grpo.trainer import GRPOConfig, load_sft_model, load_base_model, create_grpo_trainer
   ```

2. 在 `parse_args()` 中添加 `--model-name` 参数:
   ```python
   parser.add_argument(
       "--model-name",
       type=str,
       default=None,
       help="基础模型名称，直接加载（跳过 SFT）。默认: unsloth/Qwen3-4B-Thinking-2507"
   )
   ```

3. 在 `apply_config()` 中添加 model_name 的配置读取:
   ```python
   if args.model_name is None:
       args.model_name = get_nested(config, "training", "grpo", "model_name", default=None)
   ```
   注意: default=None，不设默认值——如果 config 里也没有，则 model_name 为 None。

4. 修改 `main()` 中的模型加载逻辑（步骤 [1/6]）:

   替换现有的 SFT 检查和加载逻辑为智能选择:
   ```python
   # 1. 加载模型
   if args.model_name:
       # 直接加载基础模型（跳过 SFT）
       print(f"[1/6] Loading base model: {args.model_name}...")
       logging.info(f"[1/6] Loading base model: {args.model_name}...")
       try:
           model, tokenizer = load_base_model(args.model_name)
           print(f"  Model loaded (skip SFT)")
           logging.info(f"  Model loaded (skip SFT)")
       except Exception as e:
           print(f"  Failed to load model: {e}")
           logging.error(f"  Failed to load model: {e}")
           return 1
   else:
       # 从 SFT adapter 加载（原有路径）
       print(f"[1/6] Loading SFT model from {args.sft_adapter}...")
       logging.info(f"[1/6] Loading SFT model from {args.sft_adapter}...")
       sft_path = Path(args.sft_adapter)
       if not sft_path.exists():
           error_msg = (f"SFT adapter not found: {args.sft_adapter}\n"
                       f"Please run SFT training first, or use --model-name to load a base model directly")
           print(f"  {error_msg}")
           logging.error(error_msg)
           return 1
       try:
           model, tokenizer = load_sft_model(args.sft_adapter)
           print(f"  Model loaded successfully")
           logging.info(f"  Model loaded successfully")
       except Exception as e:
           print(f"  Failed to load model: {e}")
           logging.error(f"  Failed to load model: {e}")
           return 1
   ```

5. 更新脚本顶部 docstring 中的使用方法，添加:
   ```
   # 直接使用 Thinking 模型（跳过 SFT）:
   python -m src.scripts.train_grpo --model-name unsloth/Qwen3-4B-Thinking-2507
   ```

**docker/grpo.sh** 修改:
1. 更新头部注释:
   ```
   # 输入: 基础模型 (默认: Qwen3-4B-Thinking-2507，跳过 SFT)
   #        或 outputs/sft/model/final/ (通过 --sft-adapter 使用 SFT 模型)
   ```
2. 其他部分不变 — `"$@"` 已经支持传递 `--model-name` 参数

**docker/run.sh** 修改:
1. 更新头部注释，说明默认流程为 data -> grpo（跳过 SFT）
2. 修改 `--stage` 参数帮助信息，支持 `data|sft|grpo|all|direct`
3. 默认 STAGE 改为 `"direct"`（或可保持 `"all"`，但添加 `"direct"` 选项）

   实际上更简单的方案: 保持 --stage 逻辑不变，但将默认 STAGE 从 `"all"` 改为 `"direct"`。添加 direct 模式:
   ```bash
   # 默认流程: data -> grpo (跳过 SFT)
   STAGE="direct"

   # ... 解析参数部分 ...

   # 阶段 1: 数据生成
   if [[ "${STAGE}" == "all" || "${STAGE}" == "direct" || "${STAGE}" == "data" ]]; then
       echo "[阶段 1] 数据生成"
       bash "${SCRIPT_DIR}/data.sh"
   fi

   # 阶段 2: SFT 训练 (仅 all 模式)
   if [[ "${STAGE}" == "all" || "${STAGE}" == "sft" ]]; then
       echo "[阶段 2] SFT 训练"
       bash "${SCRIPT_DIR}/sft.sh"
   fi

   # 阶段 3: GRPO 训练
   if [[ "${STAGE}" == "all" || "${STAGE}" == "direct" || "${STAGE}" == "grpo" ]]; then
       echo "[阶段 3] GRPO 训练"
       bash "${SCRIPT_DIR}/grpo.sh"
   fi
   ```
4. 更新末尾输出信息，direct 模式下不显示 SFT 输出目录
  </action>
  <verify>
运行 `python -m src.scripts.train_grpo --help` 确认:
- `--model-name` 参数存在
- `--sft-adapter` 参数仍存在

运行 `bash -n docker/grpo.sh && bash -n docker/run.sh && echo "shell syntax ok"` 确认 shell 脚本语法正确。

运行 `python -c "from src.scripts.train_grpo import parse_args; print('train_grpo imports ok')"` 确认导入正常。
  </verify>
  <done>
    - train_grpo.py 支持 --model-name 参数，指定时跳过 SFT 检查直接加载模型
    - train_grpo.py 不指定 --model-name 时走原 SFT adapter 路径（向后兼容）
    - config.json 中配置了 model_name 时，无需命令行传参也能使用
    - docker/run.sh 默认流程为 data -> grpo（跳过 SFT）
    - docker/grpo.sh 注释已更新
  </done>
</task>

</tasks>

<verification>
1. 导入验证: `python -c "from src.grpo.trainer import load_base_model, load_sft_model; print('OK')"`
2. CLI 验证: `python -m src.scripts.train_grpo --help` 显示 --model-name 和 --sft-adapter
3. 配置验证: config.json 中 training.grpo.model_name 为 "unsloth/Qwen3-4B-Thinking-2507"
4. Shell 语法: `bash -n docker/run.sh && bash -n docker/grpo.sh`
5. 向后兼容: `--sft-adapter` 路径仍然可用

注意: 完整的端到端测试（实际加载模型并训练）需要 GPU 环境和 Docker，在计划验证阶段不执行。
</verification>

<success_criteria>
- GRPO 训练入口支持直接从 Qwen3-4B-Thinking-2507 加载（跳过 SFT）
- 模型的内置 chat template 被保留使用（不被自定义模板覆盖）
- 向后兼容: --sft-adapter 路径仍然完全可用
- docker/run.sh 默认流程为 data -> grpo
- config.json 包含 model_name 配置
</success_criteria>

<output>
After completion, create `.planning/quick/2-sft-qwen3-4b-thinking-grpo/2-SUMMARY.md`
</output>
