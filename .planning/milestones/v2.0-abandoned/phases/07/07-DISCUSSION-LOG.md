# Phase 7: 标签协议全链路迁移 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 7-标签协议全链路迁移
**Areas discussed:** 协议源头, 解析与失败语义, Tokenizer 安全, 测试覆盖

---

## 协议源头

| Option | Description | Selected |
|--------|-------------|----------|
| prompt_builder single source of truth | Keep constants and parser in `tsc_cycle/prompt_builder.py`, downstream imports from there. | ✓ |
| Distributed literals | Update literals in each file independently. | |

**User's choice:** auto-selected recommended default.
**Notes:** Phase is a protocol migration; centralizing avoids inconsistent old/new tags.

---

## 解析与失败语义

| Option | Description | Selected |
|--------|-------------|----------|
| Strict rejection | Old `</end_working_out>` never parses as a valid output. | ✓ |
| Compatibility shim | Accept both old and new close tags during transition. | |

**User's choice:** auto-selected recommended default.
**Notes:** Requirement TAG-02 and roadmap success criteria explicitly require old-tag failure.

---

## Tokenizer 安全

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-token text tags only | Validate custom tags are ordinary multi-token BPE pieces; do not add tokens. | ✓ |
| Register special tokens | Add tags to tokenizer vocab for cleaner boundaries. | |

**User's choice:** auto-selected recommended default.
**Notes:** Project memory and requirements forbid native/special-token reasoning tag collisions.

---

## 测试覆盖

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing tests | Add positive/negative parser and tokenizer checks around current tests. | ✓ |
| New separate protocol test suite | Create a new parallel suite just for protocol migration. | |

**User's choice:** auto-selected recommended default.
**Notes:** Existing `tests/test_prompt_builder.py` already covers the relevant path.

---

## Claude's Discretion

- Exact implementation mechanics are left to planner/executor, with minimal-change preference.

## Deferred Ideas

None.
