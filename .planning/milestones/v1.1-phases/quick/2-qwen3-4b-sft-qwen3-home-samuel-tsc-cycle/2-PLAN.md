---
phase: quick-2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle
plan: 2
type: execute
wave: 1
depends_on: []
files_modified:
  - config/config.json
  - src/sft/train.py
  - outputs/sft/model
  - outputs/sft/model/model-f16.gguf
  - outputs/sft/model/model-q4_k_m.gguf
autonomous: true
requirements: [QUICK-2]
user_setup: []

must_haves:
  truths:
    - "SFT 使用 Qwen3-4B 作为基座模型完成训练并产出可加载的 LoRA 模型目录"
    - "SFT 后能得到 F16 GGUF 文件"
    - "SFT 后能得到 Q4_K_M GGUF 文件"
  artifacts:
    - path: "config/config.json"
      provides: "SFT 模型配置切换到 Qwen3-4B，并固定 LoRA r=16/alpha=16/dropout=0"
      contains: "training.sft.model"
    - path: "src/sft/train.py"
      provides: "训练代码对 LoRA dropout=0 的一致实现（Unsloth + HF 回退）"
      contains: "lora_dropout"
    - path: "outputs/sft/model/model-f16.gguf"
      provides: "F16 GGUF 导出产物"
    - path: "outputs/sft/model/model-q4_k_m.gguf"
      provides: "Q4_K_M GGUF 导出产物"
  key_links:
    - from: "config/config.json"
      to: "src/sft/train.py"
      via: "--config config/config.json"
      pattern: "training\.sft\.model"
    - from: "docker/sft_train.sh"
      to: "src/sft/train.py"
      via: "python3 -m src.sft.train"
      pattern: "-m src\.sft\.train"
    - from: "docker/convert_gguf.sh"
      to: "outputs/sft/model"
      via: "--model-path outputs/sft/model --outtype {f16|q4_k_m}"
      pattern: "convert_hf_to_gguf|llama-quantize"
---

<objective>
将 SFT 基座模型切换为 Qwen3-4B，完成一次可复现的 SFT 训练，并导出 F16 与 Q4_K_M 两个 GGUF 版本。

Purpose: 满足模型迁移目标，确保训练与部署产物一次到位（训练产物 + 双量化导出）。
Output: 更新后的训练配置/代码、SFT 产物目录、F16 与 Q4_K_M GGUF 文件。
</objective>

<execution_context>
@/home/samuel/.claude/get-shit-done/workflows/execute-plan.md
@/home/samuel/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@config/config.json
@src/sft/train.py
@docker/sft_train.sh
@docker/convert_gguf.sh
@/home/samuel/TSC_CYCLE/glm_flash_a100(80gb).py
</context>

<tasks>

<task type="auto">
  <name>Task 1: 切换 SFT 到 Qwen3-4B 并统一 LoRA 配置</name>
  <files>config/config.json, src/sft/train.py</files>
  <action>
将 `config/config.json` 中 `training.sft.model` 切换为 Qwen3-4B（按现有项目命名规范填写 `model_name`/`model_id`），并确保 LoRA 为 `r=16`、`lora_alpha=16`。

同时修改 `src/sft/train.py`，让 Unsloth 路径与 Hugging Face 回退路径都显式使用 `lora_dropout=0` 与 `bias="none"`，避免两条加载路径行为不一致。保留现有双重加载策略（Unsloth 优先，HF 回退），不要移除回退逻辑。

不要修改标签体系（继续使用 `<start_working_out>/<end_working_out>/<SOLUTION></SOLUTION>`）。
  </action>
  <verify>
`python3 -m src.sft.train --config config/config.json --help` 可正常输出帮助；并通过静态检查确认：
1) `config/config.json` 中 SFT 模型字段已是 Qwen3-4B；
2) `src/sft/train.py` 中 Unsloth 与 HF 两条 LoRA 路径都包含 `lora_dropout=0`。
  </verify>
  <done>
- SFT 模型配置已从 GLM 切换到 Qwen3-4B。
- LoRA 参数满足 r=16、alpha=16、dropout=0（两条加载路径一致）。
- 训练脚本仍可通过原入口加载配置并启动。
  </done>
</task>

<task type="auto">
  <name>Task 2: 执行 Qwen3-4B SFT 训练并产出模型目录</name>
  <files>outputs/sft/model</files>
  <action>
使用现有 Docker 入口运行训练：`docker/sft_train.sh --config config/config.json`。

训练完成后确认 `outputs/sft/model` 下存在可用于导出的模型文件（至少 `config.json` 与 `.safetensors`/adapter 相关文件）。如遇模型拉取失败，先修正配置中的模型标识后重跑，不要引入新的训练入口脚本。
  </action>
  <verify>
训练命令退出码为 0；`outputs/sft/model` 目录存在且包含 `config.json` 与至少一个模型权重相关文件（`.safetensors` 或等价 adapter 文件）。
  </verify>
  <done>
- Qwen3-4B SFT 训练完整跑通。
- 训练产物已写入 `outputs/sft/model`。
  </done>
</task>

<task type="auto">
  <name>Task 3: 导出 F16 与 Q4_K_M 两个 GGUF 版本</name>
  <files>outputs/sft/model/model-f16.gguf, outputs/sft/model/model-q4_k_m.gguf</files>
  <action>
基于 `outputs/sft/model` 连续执行两次转换：
1) `docker/convert_gguf.sh --model-path outputs/sft/model --outtype f16`
2) `docker/convert_gguf.sh --model-path outputs/sft/model --outtype q4_k_m`

确保输出文件保存在同一目录下，文件名分别为 `model-f16.gguf` 和 `model-q4_k_m.gguf`。如脚本提示覆盖，按最新训练结果覆盖。
  </action>
  <verify>
`outputs/sft/model/model-f16.gguf` 与 `outputs/sft/model/model-q4_k_m.gguf` 均存在且文件大小大于 0。
  </verify>
  <done>
- 成功生成 F16 GGUF。
- 成功生成 Q4_K_M GGUF。
- 两个文件均位于 `outputs/sft/model`。
  </done>
</task>

</tasks>

<verification>
1. 配置核对：Qwen3-4B + LoRA(r16/alpha16/dropout0) 生效。
2. 训练核对：SFT 训练日志正常结束，模型目录可读。
3. 导出核对：F16 与 Q4_K_M 两个 GGUF 文件均可见且非空。
</verification>

<success_criteria>
- [ ] SFT 基座模型已切换到 Qwen3-4B。
- [ ] SFT 训练成功完成并写出 `outputs/sft/model`。
- [ ] `model-f16.gguf` 已生成。
- [ ] `model-q4_k_m.gguf` 已生成。
</success_criteria>

<output>
After completion, create `.planning/quick/2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle/2-SUMMARY.md`
</output>
