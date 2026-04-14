---
phase: 05-simple-grpo-train
plan: 01
subsystem: rl-training-pipeline
tags: [grpo, docker, unsloth, data-pipeline, training-entry]

requires:
  - phase: 04-simple-grpo-reward
    provides: "src/grpo_simple/rewards.py and reward tests"
provides:
  - "src/scripts/generate_grpo_simple_data.py — 简化版 GRPO 数据生成脚本"
  - "src/grpo_simple/train.py — 简化版训练入口"
  - "docker/grpo_simple_data.sh — Docker 数据生成入口"
  - "docker/grpo_simple_train.sh — Docker 训练入口"
affects: [grpo-simple-training, future-evaluation]

tech-stack:
  added: [python, bash, docker]
  patterns: [docker-wrapper, isolated-output-paths, preflight-validation]

key-files:
  created:
    - src/grpo_simple/train.py
    - src/scripts/generate_grpo_simple_data.py
    - docker/grpo_simple_data.sh
    - docker/grpo_simple_train.sh
  modified:
    - config/config.json

key-decisions:
  - "简化版 GRPO 数据直接来自 outputs/data/train.jsonl，不复用 GLM-5 SFT 样本"
  - "初始化模型默认固定为 outputs/sft/model"
  - "所有输出固定落到 outputs/grpo_simple/，与旧版 outputs/grpo/ 分离"

patterns-established:
  - "Docker 包装脚本只做前置检查和容器调用，训练逻辑保留在 Python 模块"
  - "grpo_simple 路径集中放在 config.paths 中，便于后续 benchmark 或训练扩展复用"

requirements-completed: [PIPE-00, PIPE-01, PIPE-02, PIPE-03, VERI-01]

duration: 28min
completed: 2026-04-02
---

# Phase 05 Plan 01: Simplified Training Pipeline Summary

**完成了简化版 GRPO 的数据生成、训练入口与 Docker 包装，使新流程与旧版 `src/grpo/`、`outputs/grpo/` 完全隔离。**

## Performance

- **Duration:** 28 min
- **Completed:** 2026-04-01T16:21:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- 创建 `src/scripts/generate_grpo_simple_data.py`，可从 `outputs/data/train.jsonl` 生成 `outputs/grpo_simple/grpo_train.jsonl`
- 创建 `src/grpo_simple/train.py`，默认读取 `outputs/sft/model` 与 `outputs/grpo_simple/` 路径
- 创建 `docker/grpo_simple_data.sh` 和 `docker/grpo_simple_train.sh`，统一通过 Unsloth Docker 执行
- 实际在本机 Docker 镜像中跑通了简化版数据生成，产出 16,788 条 GRPO-simple 训练数据

## Files Created/Modified

- `src/scripts/generate_grpo_simple_data.py` - 简化版 GRPO 数据生成
- `src/grpo_simple/train.py` - 简化版训练入口
- `docker/grpo_simple_data.sh` - Docker 数据生成脚本
- `docker/grpo_simple_train.sh` - Docker 训练脚本
- `config/config.json` - `training.grpo_simple` 与 `paths.grpo_simple_*` 配置

## Decisions Made

- 训练入口与 reward 一起放在 `src/grpo_simple/`，与旧版完整 GRPO 保持物理隔离
- 数据生成阶段直接从原始 `train.jsonl` 取样，避免沿用旧 SFT 样本分布
- Docker 训练入口增加模型与数据前置检查，先挡住环境问题再进入长训练

## Deviations from Plan

None - plan executed as intended.

## Issues Encountered

- 在无 GPU 的容器中直接导入 `unsloth` 会抛出 “You need a GPU” 错误；这是 Unsloth 的环境要求，不是训练入口逻辑缺陷。

## User Setup Required

- 真正启动训练前，需要保证 Docker 运行时可见 GPU（`docker run --gpus all ...`）并且 `outputs/sft/model` 已存在。

## Next Phase Readiness

- `outputs/grpo_simple/grpo_train.jsonl` 已可由 Docker 直接生成
- `docker/grpo_simple_train.sh` 已具备训练前置检查与输出目录隔离
- 后续可直接围绕 benchmark 接回和 reward 调参开启下一里程碑

---
*Phase: 05-simple-grpo-train*
*Completed: 2026-04-02*
