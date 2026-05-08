---
phase: 07-标签协议全链路迁移
verified: 2026-05-08T00:00:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 07: 标签协议全链路迁移 Verification Report

**Phase Goal:** 全链路 prompt、数据、训练、推理与评测统一新思考结束标签 `<end_working_out>`。
**Verified:** 2026-05-08
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 新协议字面值 `<end_working_out>` 出现在 prompt、assistant 拼装、parser 与 tokenize_sanity CUSTOM_TAGS 中 | ✓ VERIFIED | `tsc_cycle/prompt_builder.py:24` 常量；`USER_TEMPLATE` 行 55/59 出现；`build_full_assistant` 行 86 拼装；`tokenize_sanity.py:37-49` 通过 import 共享常量 |
| 2 | parser 对仅含旧标签 `</end_working_out>` 的输入返回 `('', None)` | ✓ VERIFIED | `prompt_builder.py:101-102` 拒绝分支；smoke test 直接验证：`reject old: ('', None)` |
| 3 | parser 对新标签 prefill-only 输入仍能正确返回 reasoning 与 solution | ✓ VERIFIED | smoke test：`new prefill: ('step-by-step', {'1': 60})`；测试 `test_parse_with_prefill_only` PASS |
| 4 | USER_TEMPLATE 与所有源代码路径不再把 `</end_working_out>` 当作正例 | ✓ VERIFIED | `grep -rn '</end_working_out>' tsc_cycle scripts` 仅命中 `prompt_builder.py:30` 的 `LEGACY_THINK_CLOSE` 拒绝常量；data/labeled.jsonl 是历史训练数据，不在守门 scope（PLAN 明确不改） |
| 5 | tokenizer_check 对新标签确认 multi sub-token，不注册 added token | ✓ VERIFIED | 离线 tokenizer 验证：`<end_working_out>` → ids=[27,408,81101,6068,29] (5 sub-tokens, multi=True)；原生 `<think>`=[151667]、`</think>`=[151668] 单 token 未变 |
| 6 | tests 同时覆盖：新标签正例、旧标签反例、prefill-only 新闭标签反向用例、常量字面值锁定 | ✓ VERIFIED | `tests/test_prompt_builder.py` 含 `test_constants_match_protocol`、`test_parse_rejects_old_close_tag`、`test_parse_old_close_in_prefill_form`、`test_parse_rejects_when_both_close_tags_present`、`test_user_prompt_no_old_close_tag`、`test_full_assistant_uses_new_close_tag`，全部 PASS |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tsc_cycle/prompt_builder.py` | TAG_THINK_CLOSE='<end_working_out>' + 旧标签拒绝分支 + USER_TEMPLATE 文案 | ✓ VERIFIED | 行 24 新常量；行 30 `LEGACY_THINK_CLOSE` 模块级常量（响应 REVIEW WR-03）；行 101-102 无条件拒绝旧标签（响应 REVIEW WR-01）；docstring/USER_TEMPLATE 全部更新 |
| `tsc_cycle/eval/metrics_reasoning.py` | docstring 引用新闭标签 | ✓ VERIFIED | 行 3 `<start_working_out>...<end_working_out>` |
| `tsc_cycle/student/tokenize_sanity.py` | CUSTOM_TAGS 通过 import prompt_builder 常量 | ✓ VERIFIED | 行 37-49：从 prompt_builder import 4 个常量构造 CUSTOM_TAGS 列表 |
| `tests/test_prompt_builder.py` | 新增反例与常量锁定测试 + prefill 用例更新 | ✓ VERIFIED | 包含 `test_parse_rejects_old_close_tag` 等 6 个新测试；prefill 用例已切换到新字面值 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `prompt_builder::TAG_THINK_CLOSE` | tokenize_sanity / 下游 | Python import | ✓ WIRED | `tokenize_sanity.py` `from tsc_cycle.prompt_builder import TAG_*`；`metrics_reasoning.py:18` import `parse_assistant_output` |
| `prompt_builder::parse_assistant_output` | metrics_constraints (solution=None → lint_ok=False) | 返回 `("", None)` | ✓ WIRED | smoke test 验证旧标签 / 同时含新旧标签 / prefill-only 旧标签三个反例全部返回 `('', None)` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| pytest 全套件通过 | `.venv/bin/python -m pytest tests/ -q` | `30 passed in 0.01s` | ✓ PASS |
| grep 守门：tsc_cycle/scripts 内只允许 LEGACY_THINK_CLOSE 命中 | `grep -rn '</end_working_out>' tsc_cycle scripts` | 唯一命中 `prompt_builder.py:30 LEGACY_THINK_CLOSE = "</end_working_out>"` | ✓ PASS |
| parser 旧标签拒绝（完整形式） | parse `<start_working_out>x</end_working_out><SOLUTION>{...}</SOLUTION>` | `('', None)` | ✓ PASS |
| parser 旧标签拒绝（prefill 形式） | parse `step-by-step</end_working_out><SOLUTION>{...}</SOLUTION>` | `('', None)` | ✓ PASS |
| parser 新闭标签 prefill 接受 | parse `step-by-step<end_working_out><SOLUTION>{"1":60}</SOLUTION>` | `('step-by-step', {'1': 60})` | ✓ PASS |
| parser 新旧标签同存拒绝（WR-01 加固） | parse mixed sample | `('', None)` | ✓ PASS |
| Tokenizer multi-token 验证 | `tok.encode('<end_working_out>', add_special_tokens=False)` | `[27, 408, 81101, 6068, 29]`, len=5, multi=True | ✓ PASS |
| 原生 `<think>`/`</think>` id 未变 | `tok.encode('<think>')` / `tok.encode('</think>')` | `[151667]` / `[151668]` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TAG-01 | 07-01-PLAN.md | 全链路 prompt/数据/训练/推理/eval 输出协议统一为新结束标签 | ✓ SATISFIED | USER_TEMPLATE、build_full_assistant、tokenize_sanity 均使用新标签；grep 守门通过 |
| TAG-02 | 07-01-PLAN.md | 解析器和 lint 拒绝旧 `</end_working_out>` 输出 | ✓ SATISFIED | `parse_assistant_output` LEGACY_THINK_CLOSE 分支无条件返回 `('', None)`；4 个反例测试覆盖（含 both-present 与 prefill-only） |

REQUIREMENTS.md Phase 7 仅映射 TAG-01 / TAG-02；无 orphaned。

### Anti-Patterns Found

无 blocker。已通过 REVIEW 的 3 条 WARNING 全部在最终提交中修复：
- WR-01（新旧同存被静默接受）→ 已收紧为 `if LEGACY_THINK_CLOSE in text: return "", None`，并新增 `test_parse_rejects_when_both_close_tags_present`。
- WR-02（反例 prefill 断言强度）→ `test_parse_old_close_in_prefill_form` 含 `assert r == ""`。
- WR-03（局部字面值 vs SSOT）→ `LEGACY_THINK_CLOSE` 提升为模块级常量并加注释。

### Human Verification Required

无。所有 success criteria 均可程序化验证且全部通过。

### Gaps Summary

无。Phase 07 目标（思考结束标签全链路统一为 `<end_working_out>` + 旧标签拒绝 + tokenizer 安全 + 测试覆盖）在代码中实际达成。所有 4 条 ROADMAP success criteria、6 条 PLAN must-have truths、4 个 artifacts、2 条 key links、8 项 behavioral spot-checks 全部 VERIFIED；REVIEW 提出的 3 条 warning 已全部修复。

---

_Verified: 2026-05-08_
_Verifier: Claude (gsd-verifier)_
