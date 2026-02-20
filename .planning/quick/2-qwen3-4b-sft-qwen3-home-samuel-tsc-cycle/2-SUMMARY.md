---
phase: quick-2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle
plan: 2
subsystem: training
tags: [qwen3-4b, sft, lora, unsloth, gguf, llama-cpp]

requires: []
provides:
  - Qwen3-4B SFT 配置切换与 LoRA 参数统一（r=16/alpha=16/dropout=0）
  - 可复现的 Qwen3-4B SFT 训练输出目录（包含完整模型权重）
  - F16 与 Q4_K_M 两种 GGUF 导出产物
affects: [sft-inference, gguf-deploy, grpo-bootstrap]

tech-stack:
  added: []
  patterns:
    - Unsloth 优先 + HF 回退双路径参数一致化
    - SFT 后合并 LoRA 再导出 GGUF 的稳定流程
    - GGUF 量化 outtype 统一标准化（大小写归一）

key-files:
  created:
    - .planning/quick/2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle/2-SUMMARY.md
  modified:
    - config/config.json
    - src/sft/train.py
    - docker/convert_gguf.sh

key-decisions:
  - "SFT 基座切换到本地 model/Qwen3-4B-Base，并使用 model_id=Qwen/Qwen3-4B-Base 作为下载标识"
  - "将 train_on_responses_only 的边界改为 Qwen3 模板的 <|im_start|>user / <|im_start|>assistant"
  - "SFT 保存阶段输出合并后的完整模型权重，以确保 GGUF 导出包含真实张量"

patterns-established:
  - "Qwen3 SFT 响应掩码模式：instruction_part=<|im_start|>user\\n, response_part=<|im_start|>assistant\\n"
  - "GGUF 二次量化模式：输入 outtype 标准化为大写后传递 llama-quantize"

requirements-completed: [QUICK-2]
duration: 28min
completed: 2026-02-20
---

# Phase quick-2 Plan 2: Qwen3-4B SFT 与双 GGUF 导出 Summary

**完成 Qwen3-4B 的 SFT 训练迁移，打通完整模型导出链路，并产出可用的 F16/Q4_K_M GGUF 文件。**

## Performance

- **Duration:** 28 min
- **Started:** 2026-02-20T11:15:29Z
- **Completed:** 2026-02-20T11:43:31Z
- **Tasks:** 3/3
- **Files modified:** 3

## Accomplishments
- 将 `training.sft.model` 从 GLM 切换到 Qwen3-4B，并统一 LoRA 参数为 `r=16`、`alpha=16`、`dropout=0`。
- 成功执行 Qwen3-4B SFT 训练，输出目录包含 `config.json` 与 `model.safetensors` 等导出所需文件。
- 成功生成 `model-f16.gguf` 与 `model-q4_k_m.gguf`，并验证两个文件均为非空。

## Task Commits

1. **Task 1: 切换 SFT 到 Qwen3-4B 并统一 LoRA 配置** - `1cb6b89` (feat)
2. **Task 2: 执行 Qwen3-4B SFT 训练并产出模型目录** - `c757d7d` (fix)
3. **Task 3: 导出 F16 与 Q4_K_M 两个 GGUF 版本** - `7735de6` (fix)

## Files Created/Modified
- `/home/samuel/TSC_CYCLE/config/config.json` - SFT 模型切换到 Qwen3-4B，LoRA rank 调整为 16。
- `/home/samuel/TSC_CYCLE/src/sft/train.py` - 对齐 Unsloth/HF LoRA 参数、修复 Qwen3 响应掩码、保存合并模型用于 GGUF 导出。
- `/home/samuel/TSC_CYCLE/docker/convert_gguf.sh` - 量化 outtype 标准化，修复 `q4_k_m` 小写输入的转换失败。

## Decisions Made
- 使用 `model/Qwen3-4B-Base` 作为本地基座路径，保留 `Qwen/Qwen3-4B-Base` 作为模型来源标识。
- `train_on_responses_only` 必须匹配 Qwen3 chat template 的 assistant 边界，否则会触发全标签 `-100` 错误。
- 为满足 GGUF 导出，SFT 产物需包含合并后的完整权重，不能仅保存 adapter。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 移除 Unsloth 不兼容参数 `unsloth_force_compile`**
- **Found during:** Task 2
- **Issue:** Unsloth 加载 Qwen3 时抛出 `unexpected keyword argument 'unsloth_force_compile'`。
- **Fix:** 删除该参数，恢复兼容加载。
- **Files modified:** `/home/samuel/TSC_CYCLE/src/sft/train.py`
- **Verification:** 训练流程可继续进入数据处理与训练阶段。
- **Committed in:** `c757d7d`

**2. [Rule 1 - Bug] 修复 Qwen3 响应掩码边界导致全标签 -100**
- **Found during:** Task 2
- **Issue:** `train_on_responses_only` 使用 GLM 边界，触发 `ZeroDivisionError: All labels ... are -100`。
- **Fix:** 改为 Qwen3 边界：`<|im_start|>user\n` / `<|im_start|>assistant\n`。
- **Files modified:** `/home/samuel/TSC_CYCLE/src/sft/train.py`
- **Verification:** 训练命令退出码为 0。
- **Committed in:** `c757d7d`

**3. [Rule 2 - Missing Critical] 补齐导出前所需的模型配置文件**
- **Found during:** Task 2
- **Issue:** 训练输出目录缺少 `config.json`，阻塞 `convert_gguf.sh` 前置检查。
- **Fix:** 在保存阶段补齐 `config.json`，并确保输出目录导出可读。
- **Files modified:** `/home/samuel/TSC_CYCLE/src/sft/train.py`
- **Verification:** `outputs/sft/model` 存在 `config.json` 与权重文件。
- **Committed in:** `c757d7d`

**4. [Rule 2 - Missing Critical] SFT 产物从 adapter-only 改为可导出的合并模型**
- **Found during:** Task 3
- **Issue:** 仅 adapter 导出会得到 metadata-only F16 GGUF（`n_tensors = 0`），不满足可部署产物要求。
- **Fix:** 保存阶段执行 `merge_and_unload` 并输出完整模型权重。
- **Files modified:** `/home/samuel/TSC_CYCLE/src/sft/train.py`
- **Verification:** F16 导出日志显示 `n_tensors = 398`，文件大小约 7.5G。
- **Committed in:** `7735de6`

**5. [Rule 3 - Blocking] 修复 `q4_k_m` 小写输入导致量化失败**
- **Found during:** Task 3
- **Issue:** 脚本将小写 `q4_k_m` 直接传给 `convert_hf_to_gguf.py`，触发 invalid choice。
- **Fix:** 引入 `OUTTYPE_NORM` 并在二次量化路径传递 `Q4_K_M`。
- **Files modified:** `/home/samuel/TSC_CYCLE/docker/convert_gguf.sh`
- **Verification:** `model-q4_k_m.gguf` 成功生成，文件大小约 2.4G。
- **Committed in:** `7735de6`

---

**Total deviations:** 5 auto-fixed（Rule 1: 2, Rule 2: 2, Rule 3: 1）
**Impact on plan:** 偏差均为保证训练/导出可完成所必需，无额外功能扩展。

## Issues Encountered
- 本地 Python 环境缺少 `torch/transformers`，按计划通过 Docker 入口完成训练与导出验证。

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Qwen3-4B SFT 与 GGUF 双格式产物已就绪，可直接用于后续推理测试或部署。
- 产物路径：`/home/samuel/TSC_CYCLE/outputs/sft/model/model-f16.gguf`、`/home/samuel/TSC_CYCLE/outputs/sft/model/model-q4_k_m.gguf`。

## Self-Check: PASSED
- FOUND: `/home/samuel/TSC_CYCLE/.planning/quick/2-qwen3-4b-sft-qwen3-home-samuel-tsc-cycle/2-SUMMARY.md`
- FOUND commit: `1cb6b89`
- FOUND commit: `c757d7d`
- FOUND commit: `7735de6`
