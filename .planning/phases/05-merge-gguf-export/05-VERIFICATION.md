---
phase: 05-merge-gguf-export
verified: 2026-05-07T10:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
requirements_covered: 5/5
re_verification: false
---

# Phase 5: Merge + GGUF Export 验证报告

**Phase Goal:** LoRA → bf16 merge → GGUF bf16 → Q4_K_M 量化 → 三精度 parity（HF / GGUF bf16 / GGUF q4_K_M）；量化漂移在阈值内或触发 imatrix backlog 预案
**Verified:** 2026-05-07T10:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

Phase 5 目标"LoRA→bf16/GGUF/Q4_K_M 三精度 parity（量化漂移可控）"已达成。
4 个 EXP 直接通过；EXP-05 q4_K_M MAE=4.51s 超 3s 阈值，但这是 ROADMAP/PLAN 显式预案设计的
路由分支（mae_exceeded → imatrix backlog），非 fail。所有 must_haves 实际满足或被路由到记账位。

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | LoRA 已 merge 为 bf16 全精度 HF 权重 | ✓ VERIFIED | `runs/20260507T032419Z/merged_bf16/` 存在；vocab=151936（无 resize）；非 4-bit base merge |
| 2 | bf16 GGUF 与 Q4_K_M GGUF 已导出且体积合理 | ✓ VERIFIED | `model.bf16.gguf`=7678MB；`model.q4_K_M.gguf`=2381MB（PHASE05_REPORT §1） |
| 3 | GGUF tokenize sanity：4 个自定义标签 HF↔GGUF 完全一致 | ✓ VERIFIED | `tokenize_sanity.json` `all_custom_match=true`、`all_custom_multi_token=true`；4 标签 token id 序列逐一匹配（PHASE05_REPORT §2） |
| 4 | 三精度 parity 测试完成（HF / GGUF bf16 / GGUF q4_K_M）on 同一固化 20-prompt 集 | ✓ VERIFIED | `parity_report.json` n_prompts=20、n_parse_failures=0；20 条同源 frozen md5=09fa4e6326722c37bad720dbfddc29db |
| 5 | GGUF 格式无损 + q4 漂移在 ROADMAP 预案内（>3s → imatrix backlog） | ✓ VERIFIED | bf16 vs HF MAE=0.58s（GGUF 无损）；q4 vs HF MAE=4.51s 触发 mae_exceeded=true → STATE ⚠ done-with-flag + PHASE05_REPORT §5 backlog 已记录 |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `runs/20260507T032419Z/merged_bf16/` | bf16 HF merged dir, vocab=151936 | ✓ VERIFIED | pre-phase artifact，PHASE05_REPORT §1 确认 |
| `runs/20260507T032419Z/gguf/model.bf16.gguf` | bf16 GGUF, ~7.7GB | ✓ VERIFIED | 7678MB |
| `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` | Q4_K_M (preset 15), ~2.4GB | ✓ VERIFIED | 2381MB |
| `tsc_cycle/student/tokenize_sanity.py` | GGUF tokenize parity checker (gguf-py + tokenizers BPE 重建) | ✓ VERIFIED | 234 行；含 GGUFReader / models.BPE / 复刻 Qwen3 pre_tokenizer Sequence |
| `runs/20260507T032419Z/gguf/tokenize_sanity.json` | per-tag hf_ids/gguf_ids/match | ✓ VERIFIED | all_custom_match=true |
| `tsc_cycle/student/parity_prompts.py` | deterministic 20-sample selector | ✓ VERIFIED | 136 行；md5 byte-stable |
| `runs/20260507T032419Z/gguf/parity_prompts.jsonl` | 10 id + 10 ood frozen prompts | ✓ VERIFIED | md5=09fa4e6326722c37bad720dbfddc29db |
| `tsc_cycle/student/parity_{hf,gguf,merge,parity}.py` | 4-stage subprocess-isolated runner | ✓ VERIFIED | parity.py(143) + parity_hf.py(125) + parity_gguf.py(216, llama-server flavor) + parity_merge.py(144) |
| `runs/20260507T032419Z/gguf/parity_report.json` | overall_mae_*_vs_hf + timing + mae_exceeded | ✓ VERIFIED | overall_mae_q4_vs_hf=4.515; mae_exceeded=true |
| `runs/20260507T032419Z/PHASE05_REPORT.md` | 单文件 phase closure | ✓ VERIFIED | 83 行 / 5 H2 sections / 含 EXP-01..05 + MAE 字段 |
| STATE.md Phase 5 row | ⚠ done-with-flag + 链接 PHASE05_REPORT.md | ✓ VERIFIED | grep `done-with-flag` == 1 |
| REQUIREMENTS.md EXP-01..05 | Done（EXP-05 带 FLAG 注释） | ✓ VERIFIED | 5/5 行 lines 159-163 标 Done |

### Key Link Verification

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| parity_prompts.py | data/labeled.jsonl | 流式 jsonl 扫 + split_hint 分桶 | ✓ WIRED |
| parity_prompts.jsonl | parity_hf / parity_gguf | 统一读固化 frozen 集 | ✓ WIRED |
| parity_hf.py | merged_bf16 (HF) | transformers AutoModel + bf16 + sdpa | ✓ WIRED |
| parity_gguf.py | model.bf16.gguf / q4_K_M.gguf | llama-server CUDA build + HTTP /completion | ✓ WIRED |
| parity_merge.py | parity_report.json | MAE 计算 + mae_exceeded flag + STATE FLAG line（worktree 还原，主分支留 hook） | ✓ WIRED |
| parity_report.json | PHASE05_REPORT.md / STATE.md / REQUIREMENTS.md | Plan 04 closure 收尾 | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Result | Status |
| -------- | ------ | ------ |
| n_prompts == 20 (parity_report.json) | 20 | ✓ PASS |
| n_parse_failures ≤ 5 | 0 | ✓ PASS |
| GGUF bf16 wall < 1500s | 104.3s | ✓ PASS |
| GGUF q4 wall < 1500s | 48.9s | ✓ PASS |
| 4 自定义标签 HF↔GGUF token id 完全相等 | 全 match | ✓ PASS |
| GGUF 格式无损（bf16 vs HF MAE 接近 0） | 0.58s | ✓ PASS |
| mae_exceeded → backlog 路由 | true → STATE ⚠ + REPORT §5 | ✓ PASS |

## Requirements Traceability

| REQ | Description | Implementation | Status |
| --- | ----------- | -------------- | ------ |
| EXP-01 | merge 前 reload bf16 base（非 4-bit），保存到 `runs/{ts}/merged_bf16/` | pre-phase artifact，vocab=151936 无 resize | ✓ Done |
| EXP-02 | `convert_hf_to_gguf.py` 转 bf16 GGUF | `model.bf16.gguf` 7678MB；Qwen3ForCausalLM 已注册 | ✓ Done |
| EXP-03 | `llama-quantize` Q4_K_M (preset 15) | `model.q4_K_M.gguf` 2381MB | ✓ Done |
| EXP-04 | GGUF tokenize sanity：自定义标签 sub-token 与 HF 一致 | tokenize_sanity.json all_custom_match=true | ✓ Done |
| EXP-05 | 20 prompt greedy parity（HF / GGUF bf16 / q4_K_M）；MAE>3s 触发 imatrix 预案 | parity_report.json overall_mae_q4_vs_hf=4.51s → mae_exceeded → imatrix backlog 入档 | ✓ Done (FLAG: imatrix backlog) |

**Coverage:** 5/5 requirements satisfied (无 orphaned)

## must_haves Verification（PLAN frontmatter）

跨 4 个 plan 的 must_haves（artifacts + key_links）已在上面"Required Artifacts"与
"Key Link Verification"两表中逐项核对。无 stub / 无 missing / 无 orphaned。
worktree-rule 约束下 STATE.md FLAG 由 Plan 04 在主分支显式重写（`⚠ done-with-flag` 已在 STATE.md），
等价语义达成。Plan 04 把 ROADMAP traceability 表对齐到项目实际位置（REQUIREMENTS.md），
Rule 3 blocking adjustment 合规。

## Notable Items

### 1. q4_K_M MAE=4.51s 超 3s 阈值 — ROADMAP 设计内的 routing path（非 fail）

ROADMAP/PLAN 03 显式设计："MAE>3s 时 mae_exceeded=true → STATE FLAG + imatrix backlog 入档"。
该路径已正确触发并归档：

- `parity_report.json` 含 `mae_exceeded: true`
- `STATE.md` Phase 5 行 = `⚠ done-with-flag`
- `PHASE05_REPORT.md §5 Backlog` 含完整 imatrix 重量化 runbook（imatrix.dat 生成 + 重量化 + 重跑 parity）
- `REQUIREMENTS.md` EXP-05 = `Done (FLAG: imatrix backlog)`

最严重退化点：OOD 样本 `dfb9ae1a` q4 输出 `phase_3=158`（HF=32），违反 max_green 硬约束 —
属典型 q4 数值崩塌信号，已在 backlog 中作为 imatrix 重量化优先 trigger。

### 2. Phase 6 入口已就绪

PHASE05_REPORT.md 是 Phase 6 评测 entry context；三 GGUF/HF 产物路径明确；
Phase 6 EVL 套件可同时跑三 variant，对 q4 退化做 OOD 硬约束满足率定量对比。

### 3. Worktree FLAG 写入路径

Plan 03 的 parity_merge.py STATE.md FLAG append 在 worktree 模式被还原；
Plan 04 在主分支显式 Edit 重新写入 ⚠ done-with-flag — 语义等价、记账一致。

### 4. Deferred (跨 phase, 非本 phase 阻塞)

- Phase 1-4 历史 ENV/FND/DGEN/TCH/DSET/TRN traceability 仍 Pending（Plan 04 故意不越界处理）
- imatrix 重量化 / OOD 硬约束修复 → Phase 6 EVL-08 go/no-go gate 时自然触发

## Gaps Summary

无 gap。Phase 5 全部 5 个 EXP 通过；q4_K_M MAE 超阈值是 ROADMAP 显式设计的
backlog 路由分支，所有路由 artifact（FLAG / REPORT §5 / mae_exceeded 字段）已正确生成。
Phase 6 可直接消费 `runs/20260507T032419Z/PHASE05_REPORT.md` 入场。

---

_Verified: 2026-05-07T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
