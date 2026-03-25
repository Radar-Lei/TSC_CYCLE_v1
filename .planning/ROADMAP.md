# Roadmap: TSC-CYCLE v2 — GLM-5 SFT 数据生成

## Overview

从 API 客户端搭建到大规模数据生成再到训练验证与模型导出，三个阶段递进交付。Phase 1 建立可靠的 GLM-5 调用基础和数据采样管道；Phase 2 执行 5000 条推理链的批量生成，含约束校验和断点续传；Phase 3 将生成结果组装为 SFT 训练格式、验证训练效果，并导出 GGUF 量化模型。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: API 客户端与数据采样** - 搭建 GLM-5 并发调用客户端，从 train.jsonl 均匀抽样 5000 条
- [ ] **Phase 2: 批量推理链生成** - 用 GLM-5 批量生成 think 链 + solution，含约束校验、重试和断点续传
- [ ] **Phase 3: 数据组装、训练验证与模型导出** - 组装 SFT 训练数据，验证训练可行性，导出 GGUF 量化模型

## Phase Details

### Phase 1: API 客户端与数据采样
**Goal**: 用户可以通过一个可靠的客户端调用 GLM-5 API，并获得从 train.jsonl 中均匀抽取的 5000 条样本
**Depends on**: Nothing (first phase)
**Requirements**: API-01, API-02, API-03, API-04, SAMP-01, SAMP-02
**Success Criteria** (what must be TRUE):
  1. 运行客户端可以向 GLM-5 发送请求并收到合法响应（单条测试）
  2. 客户端能以 4 并发发送请求，且失败时自动指数退避重试
  3. 从 train.jsonl 中抽样的 5000 条数据覆盖高/中/低饱和度场景，分布可通过统计输出验证
**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md — GLM-5 API 客户端 (并发 + 重试 + max_tokens)
- [x] 01-02-PLAN.md — 分层抽样器 (5000 条, 覆盖所有交叉口和饱和度)

### Phase 2: 批量推理链生成
**Goal**: 用户运行一个命令即可批量生成 5000 条含 think 链和 solution 的数据，过程可中断恢复
**Depends on**: Phase 1
**Requirements**: GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, GEN-06, PROG-01, PROG-02, PROG-03
**Success Criteria** (what must be TRUE):
  1. GLM-5 为每条样本生成约 500 token 的 think 链和符合 JSON 格式的 solution
  2. 生成的 solution 通过约束校验（相位顺序一致、绿灯时间在合法范围内），违反者自动重试最多 3 次
  3. 程序中断后重启可从断点恢复，不重复调用已成功的条目
  4. 运行时可看到实时进度（完成数/总数、成功率、平均 think 长度）
**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md — Prompt 构建器 + 输出解析/约束校验器
- [x] 02-02-PLAN.md — 批量生成编排器 + CLI 入口

### Phase 3: 数据组装、训练验证与模型导出
**Goal**: 生成结果被组装为可直接训练的 SFT 数据，通过实际训练验证数据质量，并导出三种 GGUF 量化格式供部署使用
**Depends on**: Phase 2
**Requirements**: ASM-01, ASM-02, ASM-03, TRAIN-01, TRAIN-02, EXPORT-01, EXPORT-02, EXPORT-03
**Environment**: 训练验证和模型导出必须在项目 Unsloth Docker 容器中执行（`docker/Dockerfile`，基于 `unsloth/unsloth:dgxspark-latest`）。使用 `docker/sft_train.sh` 启动训练，容器内已包含 Unsloth、CUDA、SUMO 等全部依赖。
**Success Criteria** (what must be TRUE):
  1. 输出的 sft_train.jsonl 为标准 messages 格式，assistant 内容使用 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>` 标签
  2. `src/sft/train.py` 可以直接加载生成的数据文件开始训练（1 epoch），无格式错误（通过 `docker/sft_train.sh` 在 Docker 容器中执行）
  3. 训练 loss 曲线正常收敛，无明显过拟合模式（loss 不会在前几步骤急剧下降后停滞）
  4. 训练后的模型成功导出为 Q4_K_M、Q8_0、F16 三种 GGUF 文件，每个文件可被 llama.cpp 加载
**Plans:** 3 plans

Plans:
- [ ] 03-01-PLAN.md — SFT 数据组装 (results.jsonl -> sft_train.jsonl)
- [ ] 03-02-PLAN.md — Docker SFT 训练验证 (1 epoch + loss 检查)
- [ ] 03-03-PLAN.md — GGUF 模型导出 (Q4_K_M + Q8_0 + F16)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. API 客户端与数据采样 | 0/2 | Not started | - |
| 2. 批量推理链生成 | 0/2 | Not started | - |
| 3. 数据组装、训练验证与模型导出 | 0/3 | Not started | - |
