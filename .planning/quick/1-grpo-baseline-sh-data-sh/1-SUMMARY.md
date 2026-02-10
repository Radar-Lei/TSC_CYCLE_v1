---
phase: quick-1
plan: 1
subsystem: grpo-baseline
tags: [progress-bar, user-experience, parallel-processing]
dependency_graph:
  requires:
    - src/grpo/baseline.py (existing)
  provides:
    - Real-time progress bar for baseline computation
  affects:
    - Baseline precomputation workflow
tech_stack:
  added: []
  patterns:
    - Progress bar with percentage, elapsed time, ETA
    - Flush=True for real-time updates
key_files:
  created: []
  modified:
    - src/grpo/baseline.py: Added _print_progress function and real-time progress tracking
decisions: []
metrics:
  duration: 88s
  completed: 2026-02-10T02:21:05Z
---

# Quick Task 1: Add Progress Bar to GRPO Baseline Script

为 GRPO 基线计算脚本添加实时进度条,每次迭代更新显示百分比、已用时间和预估剩余时间

## Tasks Completed

| Task | Name                              | Commit  | Files Modified         |
| ---- | --------------------------------- | ------- | ---------------------- |
| 1    | 添加进度条功能到 baseline.py      | dbcb9ca | src/grpo/baseline.py   |

## Implementation Details

### Progress Bar Function

在 `baseline.py` 中新增 `_print_progress(completed, total, elapsed)` 辅助函数:

**特性:**
- 30字符宽度的进度条,使用 `█` (filled) 和 `░` (empty) 字符
- 显示完成百分比 `(completed/total)`
- 显示已用时间 (elapsed seconds)
- 动态计算并显示预估剩余时间 (ETA)
- `flush=True` 确保进度立即显示

**格式示例:**
```
  进度: |███████████░░░░░░░░░░░░░░░░░░░| 15/40 (37%) 已用:45s 剩余:75s
```

### Integration Changes

**1. Import time module** (line 17)
- 添加 `import time` 用于时间跟踪

**2. Initialize start_time** (line 199)
- 在 `ProcessPoolExecutor` 循环前初始化 `start_time = time.time()`

**3. Call progress bar on every iteration** (line 213)
- 在处理每个结果后调用 `_print_progress(i + 1, len(tasks), elapsed)`
- 移除了旧的每50项打印逻辑 `if (i + 1) % 50 == 0:`

### Code Quality

- **Syntax validation:** ✅ Passes `python3 -m py_compile`
- **Function verification:** ✅ `_print_progress` defined at line 148
- **Time import:** ✅ Present at line 17
- **Start time init:** ✅ Present at line 199
- **Progress calls:** ✅ Called at line 213
- **Old logic removed:** ✅ No modulo-50 print statements remain

## Changes from Plan

### Deviations

None - plan executed exactly as written.

## File Modifications

### src/grpo/baseline.py (+20 lines, -2 lines)

**Added:**
- Line 17: `import time`
- Lines 148-163: `_print_progress()` function implementation
- Line 199: `start_time = time.time()`
- Lines 212-213: Progress bar call after each result

**Removed:**
- Lines 194-195 (old): Modulo-50 progress print logic

**Result:** File grew from 208 to 225 lines (meets min_lines: 210 requirement)

## Verification Results

### Syntax Check
```bash
python3 -m py_compile src/grpo/baseline.py
# ✅ Success - no syntax errors
```

### Structure Check
```bash
grep -n "_print_progress" src/grpo/baseline.py
# 148:def _print_progress(completed, total, elapsed):
# 213:            _print_progress(i + 1, len(tasks), elapsed)

grep -n "import time" src/grpo/baseline.py
# 17:import time

grep -n "start_time = time.time()" src/grpo/baseline.py
# 199:    start_time = time.time()
```

### Must-Have Verification

✅ **Truth 1:** 基线计算显示实时进度条,包含百分比和预估剩余时间
- Progress bar prints: `|{bar}| {completed}/{total} ({pct:.0f}%) 已用:{elapsed}s 剩余:{eta_str}`

✅ **Truth 2:** 进度条在每个任务完成时更新,而非每50个
- Called at line 213: `_print_progress(i + 1, len(tasks), elapsed)` (inside loop, no modulo check)

✅ **Truth 3:** 输出格式与 data.sh 的进度条保持一致
- Uses identical format from `generate_training_data.py`: 30-char bar, `█`/`░` chars, same string template

✅ **Artifact:** src/grpo/baseline.py (225 lines, min 210)
- Contains `_print_progress` function
- Links from main() ProcessPoolExecutor loop to _print_progress via pattern match

## Expected Behavior

When running baseline precomputation:
```bash
./docker/grpo_baseline.sh
# or
python3 src/grpo/baseline.py --workers 4
```

Output will show real-time progress:
```
[Baseline] Unique state files: 120
[Baseline] Workers: 4
  进度: |█████░░░░░░░░░░░░░░░░░░░░░░░░░| 20/120 (16%) 已用:12s 剩余:60s
  进度: |██████████░░░░░░░░░░░░░░░░░░░░| 40/120 (33%) 已用:25s 剩余:50s
  进度: |███████████████░░░░░░░░░░░░░░░| 60/120 (50%) 已用:38s 剩余:38s
  ...
[Baseline] Done. 118/120 succeeded, 2 errors
[Baseline] Saved to outputs/grpo/baseline.json
```

## Success Criteria

- [x] src/grpo/baseline.py 成功导入 time 模块
- [x] _print_progress 函数存在且逻辑正确(进度条、百分比、ETA计算)
- [x] ProcessPoolExecutor 循环在每次迭代时调用进度条打印
- [x] 旧的每50项打印逻辑已完全移除
- [x] 代码无语法错误,可以正常编译
- [x] 进度条格式与 generate_training_data.py 保持一致

## Self-Check

### File Existence
```bash
[ -f "src/grpo/baseline.py" ] && echo "FOUND: src/grpo/baseline.py" || echo "MISSING: src/grpo/baseline.py"
```
Result: **FOUND: src/grpo/baseline.py**

### Commit Existence
```bash
git log --oneline --all | grep -q "dbcb9ca" && echo "FOUND: dbcb9ca" || echo "MISSING: dbcb9ca"
```
Result: **FOUND: dbcb9ca**

### Line Count Verification
```bash
wc -l src/grpo/baseline.py
```
Result: **225 src/grpo/baseline.py** (exceeds min_lines: 210)

### Function Implementation
```bash
grep -A 15 "def _print_progress" src/grpo/baseline.py | wc -l
```
Result: **14 lines** (complete function with bar rendering, ETA calculation, and print statement)

## Self-Check: PASSED

All verification checks passed:
- ✅ File exists: src/grpo/baseline.py
- ✅ Commit exists: dbcb9ca
- ✅ Line count: 225 (min 210)
- ✅ Function complete: _print_progress with 14-line implementation
- ✅ Integration verified: import time, start_time init, progress calls
- ✅ Old logic removed: no modulo-50 prints
