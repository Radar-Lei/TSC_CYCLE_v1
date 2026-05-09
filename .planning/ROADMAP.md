# Milestone v4.0 Roadmap — 4B 回退 + 扩展数据重训 + 标签协议修复

**Milestone:** v4.0
**Granularity:** standard
**Total Phases:** 5
**Coverage:** 24/24 requirements mapped
**Created:** 2026-05-10

## Phases

- [x] **Phase 7: 4B baseline/label protocol gate** — 回退到 v1 已验证 4B 基座，先把基座、环境、只读 baseline 与正确标签协议全部设为硬门禁
- [x] **Phase 8: v3 扩展数据 → 4B dataset rebuild** — 复用 v1/v3 lint-pass 数据，用 Qwen3-4B tokenizer 重建 v4 split/tokenized artifacts
- [ ] **Phase 9: 4B QLoRA retrain** — 沿用 v1 已验证 4B QLoRA 路线，在 v4 数据与正确标签协议上完成重训
- [ ] **Phase 10: merge + GGUF export** — 将 v4 adapter merge 并导出 GGUF fp16 与 q4_K_M，验证三精度协议与 tokenizer parity
- [ ] **Phase 11: eval matrix + decision** — 对比 v4 HF/q4 与 v1 q4 baseline，给出 GO/NO-GO/用户决策

## Phase Details

### Phase 7: 4B baseline/label protocol gate
**Goal**: 在任何重建或训练前，确认 v4.0 已回到可训练可部署的 Qwen3-4B 路线，并且全链路只接受 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` 协议。
**Depends on**: Nothing (first v4.0 phase)
**Requirements**: BASE-01, BASE-02, BASE-03, TAG-01, TAG-02, TAG-03, TAG-04
**Success Criteria** (what must be TRUE):
  1. 操作者可以运行 baseline gate，并看到学生模型固定为 `Qwen/Qwen3-4B-Thinking-2507`，训练环境来自 `/dgx-spark-training` 与 `/home/samuel/dgx-spark-setup/.venv`，且没有 Qwen3.5-9B 训练路径被选中。
  2. v1.0 baseline artifact 与 gen_cache 以只读方式挂载或引用，v4.0 gate 能证明 `runs/20260507T032419Z/` 未被写入。
  3. Qwen3-4B tokenizer audit 显示 4 个自定义标签均拆成多个 sub-token，并动态记录 native `<think>`/`</think>` token id 供后续泄漏检查使用。
  4. 标签协议 fixture 能接受完整 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`，并拒绝错误结束标签 `<end_working_out>` 与任意 native `<think>`/`</think>` 注入。
**Plans**: 4 plans
Plans:
- [x] 07-01-PLAN.md — 修正共享协议常量、parser、prompt 与协议 fixture gate，接受 `</end_working_out>` 并拒绝 `<end_working_out>`/native think。
- [x] 07-02-PLAN.md — 实现 4B model lock、环境只读证据与 v1 baseline read-only snapshot gate。
- [x] 07-03-PLAN.md — 实现 Qwen3-4B tokenizer audit，证明四个自定义标签多 sub-token 并动态记录 native think IDs。
- [x] 07-04-PLAN.md — 聚合 Phase 7 子门禁并提供固定 argv wrapper，生成 `phase7_gate_report.json`。

### Phase 8: v3 扩展数据 → 4B dataset rebuild
**Goal**: 将 v1.0 valid labeled data 与 v3 新增 lint-pass labeled data 合并去重，并用 Qwen3-4B tokenizer 产出隔离的 v4 split/tokenized dataset。
**Depends on**: Phase 7
**Requirements**: DATA4B-01, DATA4B-02, DATA4B-03, DATA4B-04, DATA4B-05
**Success Criteria** (what must be TRUE):
  1. 操作者可以检查 v4 数据 manifest，确认数据源只包含 v1.0 valid labeled data 与 v3 新增 lint-pass labeled data，且样本哈希去重后可复现。
  2. 数据清洗报告列出 `<end_working_out>` → `</end_working_out>` 的替换数量，并证明所有训练样本均使用正确结束标签且不含 native `<think>`/`</think>`。
  3. v4 隔离路径中存在 seed=42 的 80/10/10 split 与 Qwen3-4B tokenized artifacts，OOD val 同时保留 v1.0 可比子集与 v3 扩展 OOD 子集。
  4. rebuild 报告显示截断率 ≤5%，任一样本均未编码出 native `<think>`/`</think>` token id。
  5. dataset card 清楚记录数据来源、标签规范化、split 哈希，以及 v1/v3/v4 artifact 边界。
**Plans**: 4 plans
Plans:
- [x] 08-01-PLAN.md — 建立 Phase 8 RED 测试合约，覆盖 v1/v3 source merge、标签规范化、split/tokenize、aggregate gate 与 dataset card。
- [x] 08-02-PLAN.md — 实现 v4 source merge、清洗报告、deterministic 80/10/10 split、Qwen3-4B raw-text tokenization 与 rebuild report。
- [x] 08-03-PLAN.md — 实现 Phase 8 aggregate gate 与固定 argv wrapper，阻止不完整数据进入 Phase 9。
- [x] 08-04-PLAN.md — 更新 dataset card 的 v4 Phase 8 数据来源、标签规范化、split hash 与 v1/v3/v4 artifact 边界。

### Phase 9: 4B QLoRA retrain
**Goal**: 使用 v4 rebuilt dataset 和正确 raw-text protocol，按 v1 已验证 4B QLoRA 路线重新训练 Qwen3-4B adapter。
**Depends on**: Phase 8
**Requirements**: SFT4B-01, SFT4B-02, SFT4B-03, SFT4B-04
**Success Criteria** (what must be TRUE):
  1. 训练前 smoke gate 可证明 tokenizer leakage、样本结构、最小训练步、SOLUTION parse 与硬约束 lint 全部通过。
  2. 全量训练在 v1 已验证的 4B QLoRA 配置下运行，`packing=False`，raw-text protocol 不走 chat_template，且产物写入 `runs/v4.0-4B-{utc_timestamp}/`。
  3. 训练完成后，操作者可以查看报告中的 loss 曲线、训练时长、显存峰值、adapter hash 与数据 manifest hash。
  4. 训练产物的验证生成样本包含完整 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` 结构，且 SOLUTION 可解析并通过基本硬约束 lint。
**Plans**: 4 plans
Plans:
- [x] 09-01-PLAN.md — 建立 Phase 9 RED 合约，覆盖 4B QLoRA 配置、pre-train smoke、DGX-safe wrapper 与最终 report/handoff。
- [ ] 09-02-PLAN.md — 实现 4B/v4 SFT helper、pre-train smoke evaluator 与 Phase 9-aware trainer mode。
- [ ] 09-03-PLAN.md — 实现 Phase 9 smoke/full-training wrappers 与 fail-closed aggregate report evaluator。
- [ ] 09-04-PLAN.md — 自动执行 smoke gate、run_safe full training 与最终 Phase 9 aggregate handoff report。

### Phase 10: merge + GGUF export
**Goal**: 将 v4 4B adapter 合并为 HF 权重并导出 GGUF fp16 与 q4_K_M，确认量化后协议、约束与 tokenizer parity 不崩塌。
**Depends on**: Phase 9
**Requirements**: GGUF4B-01, GGUF4B-02, GGUF4B-03, GGUF4B-04
**Success Criteria** (what must be TRUE):
  1. 操作者可以看到完整 artifact 链路：LoRA merge → HF bf16/fp16 safetensors → GGUF fp16 → q4_K_M GGUF 全部产出并带 hash。
  2. HF / GGUF fp16 / GGUF q4_K_M 三精度 smoke 均输出完整 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` 结构。
  3. 固定 prompt fixture 上 HF tokenizer ↔ llama-tokenize parity 通过，说明 GGUF metadata 与训练 tokenizer 一致。
  4. q4_K_M 相对 HF/fp16 的协议与硬约束 smoke 未崩塌；若失败，报告中明确记录 q5_K_M fallback 决策点。
**Plans**: TBD

### Phase 11: eval matrix + decision
**Goal**: 用统一评测矩阵比较 v4 HF、v4 q4_K_M 与 v1 q4_K_M baseline，判断扩展数据与 `</end_working_out>` 标签修复是否带来收益或至少不回退。
**Depends on**: Phase 10
**Requirements**: EVAL4B-01, EVAL4B-02, EVAL4B-03, EVAL4B-04
**Success Criteria** (what must be TRUE):
  1. 评测矩阵至少包含 v4 HF、v4 q4_K_M、v1 q4_K_M baseline，且 v1 baseline gen_cache 只读引用、不重生成。
  2. 评测报告同时展示 OOD hard-constraint pass、teacher MAE、format pass、q4-vs-HF ratio、bootstrap CI、p99/max-abs tail metrics。
  3. 决策门明确判断 v4 q4_K_M 是否满足 hard-constraint pass ≥98%、q4-vs-HF ratio ≥0.95、且相对 v1 baseline 不显著回退。
  4. `decision.md` 给出 GO / NO-GO / 用户决策，并解释扩展数据与 `</end_working_out>` 标签修复对结果的贡献。
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 7. 4B baseline/label protocol gate | 4/4 | Complete | 2026-05-10 |
| 8. v3 扩展数据 → 4B dataset rebuild | 4/4 | Complete | 2026-05-10 |
| 9. 4B QLoRA retrain | 0/4 | Planned | - |
| 10. merge + GGUF export | 0/0 | Not started | - |
| 11. eval matrix + decision | 0/0 | Not started | - |

## Coverage Map

All 24 v4.0 requirements mapped to exactly one phase:

| Category | Requirements | Phase |
|----------|--------------|-------|
| BASE (3) | BASE-01, BASE-02, BASE-03 | Phase 7 |
| TAG (4) | TAG-01, TAG-02, TAG-03, TAG-04 | Phase 7 |
| DATA4B (5) | DATA4B-01..05 | Phase 8 |
| SFT4B (4) | SFT4B-01..04 | Phase 9 |
| GGUF4B (4) | GGUF4B-01..04 | Phase 10 |
| EVAL4B (4) | EVAL4B-01..04 | Phase 11 |

**Coverage:** 24/24 ✓ — no orphans, no duplicates.

## Dependency DAG

```text
Phase 7 (4B baseline + label protocol gate)
  └─► Phase 8 (4B dataset rebuild)
        └─► Phase 9 (4B QLoRA retrain)
              └─► Phase 10 (merge + GGUF export)
                    └─► Phase 11 (eval matrix + decision)
```

**Critical path:** Phase 9 training is the main long-running step; all earlier gates exist to prevent wasting training time on the wrong base model, wrong tokenizer, writable baseline, or wrong `</end_working_out>` protocol.
