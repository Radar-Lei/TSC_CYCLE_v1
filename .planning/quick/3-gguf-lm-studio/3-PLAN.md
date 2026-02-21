---
phase: quick-3
plan: 1
type: execute
wave: 1
depends_on: []
files_modified: []
autonomous: true
must_haves:
  truths:
    - "LM Studio 模型目录中无断裂符号链接"
    - "model-f16.gguf 符号链接指向正确的 GGUF 文件"
    - "model-q4_k_m.gguf 符号链接指向正确的 GGUF 文件"
  artifacts:
    - path: "/home/samuel/.lmstudio/models/DeepSignal/DeepSignal_CyclePlan/model-f16.gguf"
      provides: "F16 GGUF 模型符号链接"
    - path: "/home/samuel/.lmstudio/models/DeepSignal/DeepSignal_CyclePlan/model-q4_k_m.gguf"
      provides: "Q4_K_M GGUF 模型符号链接"
  key_links:
    - from: "model-f16.gguf (symlink)"
      to: "/home/samuel/TSC_CYCLE/outputs/sft/model/model-f16.gguf"
      via: "symbolic link"
    - from: "model-q4_k_m.gguf (symlink)"
      to: "/home/samuel/TSC_CYCLE/outputs/sft/model/model-q4_k_m.gguf"
      via: "symbolic link"
---

<objective>
重新链接 GGUF 模型到 LM Studio 模型目录。

Purpose: Quick task 2 完成了 Qwen3-4B SFT 并导出了 F16 和 Q4_K_M 两个 GGUF 文件到新路径 (`outputs/sft/model/`)，但 LM Studio 模型目录中的旧符号链接仍指向已删除的 `outputs/sft/merged/` 路径。需要清理断裂链接并创建指向正确路径的新链接。
Output: LM Studio 模型目录中包含两个有效的 GGUF 符号链接。
</objective>

<context>
目标目录: /home/samuel/.lmstudio/models/DeepSignal/DeepSignal_CyclePlan/
GGUF 源文件:
  - /home/samuel/TSC_CYCLE/outputs/sft/model/model-f16.gguf (7.5 GB)
  - /home/samuel/TSC_CYCLE/outputs/sft/model/model-q4_k_m.gguf (2.3 GB)
当前状态: 一个断裂符号链接 model-Q4_K_M.gguf -> outputs/sft/merged/model-Q4_K_M.gguf (目标已删除)
</context>

<tasks>

<task type="auto">
  <name>Task 1: 清理断裂符号链接并创建新链接</name>
  <files></files>
  <action>
    1. 删除 `/home/samuel/.lmstudio/models/DeepSignal/DeepSignal_CyclePlan/model-Q4_K_M.gguf` 断裂符号链接
    2. 创建符号链接 `model-f16.gguf` -> `/home/samuel/TSC_CYCLE/outputs/sft/model/model-f16.gguf`
    3. 创建符号链接 `model-q4_k_m.gguf` -> `/home/samuel/TSC_CYCLE/outputs/sft/model/model-q4_k_m.gguf`
    注意: Q4_K_M 链接名使用小写 `model-q4_k_m.gguf`（与源文件一致）
  </action>
  <verify>
    运行 `ls -la /home/samuel/.lmstudio/models/DeepSignal/DeepSignal_CyclePlan/` 确认:
    - 无断裂符号链接
    - model-f16.gguf 指向正确目标
    - model-q4_k_m.gguf 指向正确目标
    运行 `file` 命令确认两个链接目标均为有效的 GGUF 文件
  </verify>
  <done>LM Studio 模型目录包含两个有效符号链接，分别指向 F16 和 Q4_K_M GGUF 文件</done>
</task>

</tasks>

<verification>
ls -la /home/samuel/.lmstudio/models/DeepSignal/DeepSignal_CyclePlan/
确认目录中恰好有两个符号链接，且均指向存在的目标文件。
</verification>

<success_criteria>
- 断裂的 model-Q4_K_M.gguf 符号链接已移除
- model-f16.gguf 符号链接有效，指向 /home/samuel/TSC_CYCLE/outputs/sft/model/model-f16.gguf
- model-q4_k_m.gguf 符号链接有效，指向 /home/samuel/TSC_CYCLE/outputs/sft/model/model-q4_k_m.gguf
</success_criteria>
