# Milestones

## v4.0 4B 回退 + 扩展数据重训 + 标签协议修复 (Shipped: 2026-05-11)

**Phases completed:** 6 phases, 23 plans, 26 tasks

**Key accomplishments:**

- CPU-fast RED pytest contracts for v4 4B dataset rebuild source hygiene, deterministic split/tokenize safety, and Phase 8 handoff gating
- v4 Qwen3-4B dataset rebuild engine with source normalization, deterministic split indexes, native-think token gates, and dry-run rebuild evidence
- Fail-closed Phase 8 DATA4B aggregate handoff gate plus fixed-argv v4 rebuild wrapper for Qwen3-4B dataset artifacts
- Real Phase 8 DATA4B provenance in the dataset card plus a regenerated green aggregate handoff gate for Phase 9
- CPU-fast RED pytest contracts locking Qwen3-4B raw-text QLoRA, smoke gates, DGX-safe wrappers, and Phase 10 handoff evidence before implementation
- CPU-fast RED contracts for Phase 10 merge/export, tokenizer parity, three-backend protocol smoke, and q4_K_M collapse decision evidence
- Qwen3-4B v4 adapter exported to merged HF safetensors plus llama.cpp fp16 and q4_K_M GGUF with hash-addressed GGUF4B-01 evidence
- Phase 11 RED contracts now lock read-only v1 baseline safety, normalized backend IDs, bootstrap/tail metrics, decision thresholds, and decision markdown expectations before implementation.
- Phase 12 的 reality.log 输入重放、v4 q4_K_M 产物选择、协议解析、fail-closed 报告与原子写入行为已用 RED pytest 合同锁定。
- Phase 12 已实现可复用的 reality.log 输入重放 CLI、fail-closed 报告 gate、固定 wrapper 与 dry-run 审计证据，使后续 full generation 可以通过 v4 q4_K_M GGUF 产物安全生成 `reality_test.log`。
- 最新 Phase 11 GO q4_K_M GGUF 模型已完整重放 426 条 reality.log 输入，生成带自定义思考协议的最终 reality_test.log，并通过 426/426 parse、lint、protocol gate。

---
