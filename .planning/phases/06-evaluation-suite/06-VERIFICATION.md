---
phase: 06-evaluation-suite
verified: 2026-05-07T16:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 6: Evaluation Suite 验证报告

**Phase 目标:** 三 backend × 四指标 × 两 split 矩阵评测，给出部署 go/no-go 决策
**验证时间:** 2026-05-07
**状态:** passed
**复验:** 否 — 初次验证

## Goal Achievement

### Observable Truths（Success Criteria 对齐）

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | gen_cache 1800 = 600×3 backend | ✓ VERIFIED | `runs/20260507T032419Z/eval/gen_cache/{hf_bf16,gguf_bf16,gguf_q4_k_m}/` 各 600 文件，共 1800；`eval_prompts.jsonl` = 600 行（300 id + 300 ood） |
| 2 | per_sample.jsonl 含 4 指标逐样本（trivial 排除、phase_count 分桶） | ✓ VERIFIED | `per_sample.jsonl` = 1800 行；schema 含 `lint_ok / violations / mae / exact_match / reasoning_tier / hit_count / phase_count / trivial`；report.md 含 phase_count 分桶表（phases=2..6） |
| 3 | report.md 4×3×2 矩阵 + p99 + top-20 + 退化结论 | ✓ VERIFIED | `report.md` 含 8 段：Summary / Constraint Satisfaction / Teacher MAE / OOD Gap / Reasoning Quality / Latency p99（gguf_bf16=7.64s, gguf_q4_k_m=3.87s）/ Top-20 Failure Cases（558/1800）/ Quantization Degradation Verdict |
| 4 | decision.md GO/NO-GO（实际 GO, ratio=0.9933 ≥ 0.95） | ✓ VERIFIED | `decision.md` 含 `**GO/NO-GO:** GO`、`Threshold: ... >= 0.95`、`Computed ratio: 0.9933`、三 backend 数字表、`## Downstream Action`；ratio = 0.9867/0.9933 = 0.9933 命中 GO 分支 |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | 期望 | Status | Details |
|----------|------|--------|---------|
| `runs/.../eval/eval_prompts.jsonl` | 600 行 (300 id + 300 ood) | ✓ VERIFIED | wc -l = 600；md5 byte-stable |
| `runs/.../eval/gen_cache/{3 backends}/` | 各 600 个 *.json | ✓ VERIFIED | 三目录均 600 文件 |
| `runs/.../eval/per_sample.jsonl` | 1800 行 | ✓ VERIFIED | wc -l = 1800；compact JSONL |
| `runs/.../eval/report.md` | 4×3×2 矩阵 + p99 + top-20 + 退化 | ✓ VERIFIED | 8 sections 全部呈现 |
| `runs/.../eval/decision.md` | GO/NO-GO + verbatim 阈值 + 数字 | ✓ VERIFIED | 含全部必需 grep 锚点 |
| `tsc_cycle/eval/eval_prompts.py` | dataset selector | ✓ VERIFIED | 172 行，commit 7284b82 |
| `tsc_cycle/eval/metrics_{constraints,mae,ood_gap,reasoning}.py` | 4 指标模块 | ✓ VERIFIED | 各 38–55 行 |
| `tsc_cycle/eval/compute_metrics.py` | orchestrator | ✓ VERIFIED | 384 行 |
| `tsc_cycle/eval/decision.py` | go/no-go 裁决器 | ✓ VERIFIED | 208 行；stdout `[DECISION] GO ratio=0.9933 threshold=0.95` |

### Requirements Coverage

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| EVL-01 | 三 backend runner，共享 prompt_builder + same seed | ✓ SATISFIED | gen_cache 三目录 × 600 |
| EVL-02 | 600 prompt × 3 = 1800 generations | ✓ SATISFIED | per_sample.jsonl = 1800 行 |
| EVL-03 | 硬约束满足率 + phase_count 分桶 + trivial 排除 | ✓ SATISFIED | report.md Constraint Satisfaction 段含分桶表 |
| EVL-04 | MAE / 完全一致率 | ✓ SATISFIED | report.md Teacher MAE 段（mean MAE + exact_match） |
| EVL-05 | OOD gap | ✓ SATISFIED | report.md OOD Gap 段（id - ood gap 表） |
| EVL-06 | Reasoning 引用质量（规则式） | ✓ SATISFIED | metrics_reasoning.py + report.md Reasoning Quality 段 |
| EVL-07 | report.md 4×3×2 + p99 + top-20 + 退化结论 | ✓ SATISFIED | 8 段全呈现 |
| EVL-08 | go/no-go gate（q4_K_M OOD lint ≥ 0.95 × HF bf16） | ✓ SATISFIED | decision.md GO，ratio=0.9933 |

### Key Findings

- **GO 决议数字依据:** hf_bf16 OOD lint=0.9933, gguf_q4_k_m OOD lint=0.9867 → ratio=0.9933 ≥ 0.95 阈值
- **量化退化:** OOD MAE Δ = +0.176s（远低于 3s 阈值），未触发 imatrix 重量化
- **结构稳定性:** q4_K_M 在 600-prompt 全集 parse_error=0，思考标签闭合 100%；Phase-5 子集观察到的 dfb9ae1a 崩塌信号未泛化
- **Reasoning 质量:** q4_K_M full tier OOD = 95.7%，反而高于 bf16 后端 91.3%
- **Milestone 状态:** v1.0 CLOSED — 6/6 phases done, 20/20 plans done, 47/47 requirements completed；交付物 `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` 可投入 EvoProgTSC 部署

### Anti-Patterns Found

无 — 全部 4 个 metric 模块为单一职责纯 stdlib 实现；decision.py 阈值 verbatim 写入 markdown 便于审计；trivial 样本（min==max）在 lint rate 分母中正确排除（grep `not r["trivial"]` 命中）。

### Gaps Summary

无 gaps。Phase 6 全部 success criteria 与 EVL-01..08 在代码与运行产物中均有可验证证据。GO 决议数字（ratio=0.9933）与 SUMMARY 声明一致，decision.md / report.md / per_sample.jsonl 三个产物互相印证，无 stub / orphan / 数据漂移。

---

_验证人: Claude (gsd-verifier)_
_验证时间: 2026-05-07T16:00:00Z_
