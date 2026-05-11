---
phase: 12-home-samuel-tsc-cycle-reality-log-reality-test-log
plan: "03"
subsystem: phase12-reality-replay
tags: [reality-log, gguf, llama-server, q4-k-m, protocol-gate, human-verify]
requires:
  - phase: 12-home-samuel-tsc-cycle-reality-log-reality-test-log
    plan: "02"
    provides: Phase 12 reality.log 输入解析、GGUF replay CLI、fail-closed report gate 与 wrapper
provides:
  - 由最新 Phase 11 GO q4_K_M GGUF 模型生成的 /home/samuel/TSC_CYCLE/reality_test.log
  - 426 条 reality.log 输入的 Phase 12 manifest/per-sample/report 证据
  - 426/426 parse、lint、protocol 全绿的非 dry-run gate 报告
affects: [phase12-reality-test, reality_test.log, deployment-handoff]
tech-stack:
  added: []
  patterns: [llama-server resume cache, fail-closed report verification, prose-safe protocol grep, human spot-check checkpoint]
key-files:
  created:
    - reality_test.log
  modified:
    - artifacts/v4/phase12/manifest.json
    - artifacts/v4/phase12/per_sample.jsonl
    - artifacts/v4/phase12/phase12_report.json
    - tsc_cycle/v4_gates/phase12_report.py
key-decisions:
  - "Phase 12 full replay 使用 Phase 11 GO 推荐的 /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf，不回退 frozen v1。"
  - "保留 report.reports.final_log，并新增 report.reports.reality_test_log 兼容键以满足最终完整性检查。"
  - "最终人工验证只要求用户抽查已有文件，不要求用户运行任何生成命令。"
patterns-established:
  - "Phase 12 最终报告同时暴露 final_log 与 reality_test_log 两个路径键，便于下游检查脚本稳定引用。"
  - "对自定义思考协议的最终检查应只扫描 result RAW 段，避免 prompt 说明文本中的标签计数造成自我误报。"
requirements-completed: [PHASE12-GOAL]
duration: 16min02s
completed: 2026-05-11
---

# Phase 12 Plan 03: Full Reality Log Replay Summary

**最新 Phase 11 GO q4_K_M GGUF 模型已完整重放 426 条 reality.log 输入，生成带自定义思考协议的最终 reality_test.log，并通过 426/426 parse、lint、protocol gate。**

## Performance

- **Duration:** 16min02s（wrapper manifest 记录 live generation elapsed_sec=962.21）
- **Started:** 2026-05-11T12:17:15Z
- **Completed:** 2026-05-11T12:33:17Z
- **Tasks:** 3 completed (including approved blocking human-verify checkpoint)
- **Files modified:** 5 generated/implementation artifacts + 3 planning/tracking files updated at completion

## Accomplishments

- 先运行 dry-run smoke：`/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase12_reality_test --dry-run --limit 3`，成功退出。
- 运行 `/home/samuel/TSC_CYCLE/scripts/run_phase12_reality_test.sh`，使用 Phase 11 GO q4_K_M 模型生成 `/home/samuel/TSC_CYCLE/reality_test.log`。
- 产出非 dry-run Phase 12 证据：`manifest.json`、`per_sample.jsonl`、`phase12_report.json`。
- 最终报告为 green：`ok=true`、`next_phase_allowed=true`、`input_count=426`、`parse_ok_count=426`、`lint_ok_count=426`、`protocol_ok_count=426`、`timeout_count=0`。
- `reality_test.log` 共 32176 行，包含 426 个 `type=result|engine=tsc-cycle-v4-q4_K_M` result block；所有 RAW 段均可由 `parse_assistant_output` 解析为 reasoning + SOLUTION。
- Task 3 human spot-check 已收到用户 `approved` 回复，确认最终 `reality_test.log` 可接受。

## Task Commits

Each task was committed atomically:

1. **Task 1: Execute full Phase 12 GGUF reality replay** - `5fc5f61` (feat)
2. **Task 2: Verify final artifact integrity and no-contamination invariants** - `c7f5f35` (fix)
3. **Summary checkpoint record before human verification** - `3b9d659` (docs)
4. **Task 3: Human spot-check final reality_test.log** - pending completion commit (docs)

**Plan metadata:** this summary/tracking update records the approved checkpoint and completes Plan 12-03.

## Files Created/Modified

- `reality_test.log` - 由 v4 q4_K_M GGUF 模型对 426 条 `reality.log` prompt 输入生成的最终 replay log。
- `artifacts/v4/phase12/manifest.json` - 记录 input/model/output hashes、426 条 input records、model artifact 与运行元数据。
- `artifacts/v4/phase12/per_sample.jsonl` - 426 行 per-sample raw output、parsed solution、lint/protocol/cache evidence。
- `artifacts/v4/phase12/phase12_report.json` - 非 dry-run aggregate gate report，所有 gate 通过。
- `tsc_cycle/v4_gates/phase12_report.py` - 增加 `reports.reality_test_log` 兼容键，满足最终完整性检查。

## Decisions Made

- 使用 wrapper 的 `--resume` 行为完成 full replay；第一次后台 wrapper 被手动停止后，保留已有有效 cache 并继续生成，未删除 `gen_cache`。
- 最终协议检查改为逐个 result RAW 段解析，而不是对整份 log 直接计数 `<start_working_out>`；整份 log 的 prompt instructions 本身也包含协议标签，直接计数会产生误报。
- 人工验证 checkpoint 保持 blocking；自动检查全部通过后，按用户 `approved` 回复将 Task 3 标记完成。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补齐 report 中的 `reports.reality_test_log` 路径键**
- **Found during:** Task 2 (Verify final artifact integrity and no-contamination invariants)
- **Issue:** 计划中的最终 JSON 检查要求 `report['reports']['reality_test_log'] == '/home/samuel/TSC_CYCLE/reality_test.log'`，但 Plan 12-02 的 report payload 只有 `reports.final_log`，导致验收脚本无法引用该键。
- **Fix:** 在 `evaluate_phase12_report` 的 `reports` payload 中保留 `final_log`，并新增同值的 `reality_test_log` alias。
- **Files modified:** `tsc_cycle/v4_gates/phase12_report.py`
- **Verification:** `pytest tests/test_phase12_reality_log_generation.py -q` 通过；最终 JSON/protocol 检查通过。
- **Committed in:** `c7f5f35`

---

**Total deviations:** 1 auto-fixed (Rule 2 missing critical functionality)
**Impact on plan:** 仅补齐计划要求的审计字段；未改变 generation、lint、protocol 或 artifact selection 语义。

## Issues Encountered

- 计划中的 report CLI verify 示例使用了未实现的 `--input` / `--expect-count` 参数；实际使用当前 CLI 支持的 `--reality-test-log` 与 `--artifact-root` 完成同等 report gate 验证。
- 第一次 full wrapper 后台进程与第二次 retry 发生并行；为避免重复生成和端口/显存占用，停止了旧的第一组 wrapper/server 进程，仅保留第二组 wrapper 继续通过 resume cache 完成 426/426 输出。
- 计划中直接断言整份 `reality_test.log` 的 `<start_working_out>` 计数为 426 会误计 prompt instructions 中的标签；最终改用 result RAW 段解析验证 426 个模型输出。

## User Setup Required

None. runtime/model/server 路径均存在，full generation 已由 Claude 自动完成。

## Known Stubs

None. `gen_cache/` 是 wrapper resume cache，当前被 `.gitignore` 忽略；最终可审计证据已汇总进 `per_sample.jsonl`、`manifest.json` 与 `phase12_report.json`。

## Threat Flags

None beyond the planned Phase 12 trust boundaries. 本计划只生成最终 replay artifact，并未引入新的网络端点、认证路径、文件访问 trust boundary 或 schema 变更。

## Verification

Passed:

```bash
cd /home/samuel/TSC_CYCLE && /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase12_reality_test --dry-run --limit 3
cd /home/samuel/TSC_CYCLE && /home/samuel/TSC_CYCLE/scripts/run_phase12_reality_test.sh
cd /home/samuel/TSC_CYCLE && /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase12_report --reality-test-log /home/samuel/TSC_CYCLE/reality_test.log --artifact-root /home/samuel/TSC_CYCLE/artifacts/v4/phase12
cd /home/samuel/TSC_CYCLE && /home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_phase12_reality_log_generation.py -q
```

Final prose-safe JSON/protocol check passed:

- `ok is True`
- `next_phase_allowed is True`
- `dry_run is False`
- `input_count == parse_ok_count == lint_ok_count == 426`
- `model_artifact == /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`
- `reports.reality_test_log == /home/samuel/TSC_CYCLE/reality_test.log`
- zero native `<think>` / `</think>` tags
- 426 result RAW blocks parse as custom reasoning + SOLUTION
- no malformed `<end_working_out>` close tags inside result RAW blocks

## Human Verification

Approved. 用户在 checkpoint continuation 中回复 `approved`，确认最终 `reality_test.log` 的抽查结果可接受；Task 3 完成。

## Auth Gates

None.

## Deferred Issues

None.

## Self-Check: PASSED

- Found `/home/samuel/TSC_CYCLE/reality_test.log`.
- Found `/home/samuel/TSC_CYCLE/artifacts/v4/phase12/manifest.json`.
- Found `/home/samuel/TSC_CYCLE/artifacts/v4/phase12/per_sample.jsonl`.
- Found `/home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json`.
- Found `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase12_report.py`.
- Commits found: `5fc5f61`, `c7f5f35`, `3b9d659`.
- Contract tests passed: `11 passed`.
- Final artifact checks passed: `phase12 final artifact checks passed`.
- Checkpoint continuation verification passed: `phase12 checkpoint approval verification passed`.
- Task 3 human approval recorded from user response: `approved`.

## Checkpoint Status

Plan 12-03 completed after **Task 3: Human spot-check final reality_test.log** (`checkpoint:human-verify`, blocking) received user approval. Automated generation and validation remained green at continuation.

---
*Phase: 12-home-samuel-tsc-cycle-reality-log-reality-test-log*
*Completed: 2026-05-11*
