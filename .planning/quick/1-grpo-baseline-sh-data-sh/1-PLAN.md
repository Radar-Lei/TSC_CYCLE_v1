---
phase: quick-1
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/grpo/baseline.py
autonomous: true

must_haves:
  truths:
    - "基线计算显示实时进度条，包含百分比和预估剩余时间"
    - "进度条在每个任务完成时更新，而非每50个"
    - "输出格式与 data.sh 的进度条保持一致"
  artifacts:
    - path: "src/grpo/baseline.py"
      provides: "进度条打印功能"
      contains: "_print_progress"
      min_lines: 210
  key_links:
    - from: "src/grpo/baseline.py main()"
      to: "_print_progress"
      via: "在 ProcessPoolExecutor 循环中每次调用"
      pattern: "_print_progress.*completed.*total"
---

<objective>
为 GRPO 基线计算脚本添加实时进度条，显示完成百分比、已用时间和预估剩余时间。

Purpose: 提供更好的用户体验，让长时间运行的基线计算任务有清晰的进度反馈
Output: 更新的 baseline.py，带有类似 generate_training_data.py 的进度条功能
</objective>

<execution_context>
@/home/samuel/.claude/get-shit-done/workflows/execute-plan.md
@/home/samuel/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/home/samuel/TSC_CYCLE/src/grpo/baseline.py
@/home/samuel/TSC_CYCLE/src/scripts/generate_training_data.py
</context>

<tasks>

<task type="auto">
  <name>添加进度条功能到 baseline.py</name>
  <files>src/grpo/baseline.py</files>
  <action>
修改 src/grpo/baseline.py 以添加进度条打印：

1. 在文件顶部导入语句中添加 `import time`（第11-18行附近，与其他导入一起）

2. 在 main() 函数内的 ProcessPoolExecutor 循环之前添加：
   - `start_time = time.time()`（第182行附近，就在 `with ProcessPoolExecutor` 之前）

3. 在 compute_single_baseline() 之后、main() 之前添加 _print_progress 辅助函数（第146-147行之间）：
```python
def _print_progress(completed, total, elapsed):
    """打印进度条"""
    pct = completed / total * 100
    bar_len = 30
    filled = int(bar_len * completed / total)
    bar = '█' * filled + '░' * (bar_len - filled)
    if completed > 0:
        avg = elapsed / completed
        eta = avg * (total - completed)
        eta_str = f"{int(eta)}s"
    else:
        eta_str = "--"
    print(f"  进度: |{bar}| {completed}/{total} ({pct:.0f}%) "
          f"已用:{int(elapsed)}s 剩余:{eta_str}", flush=True)
```

4. 在 ProcessPoolExecutor 的 for 循环内（第183-195行），将现有的每50项打印逻辑替换为每次调用进度条：
   - 删除第194-195行的 `if (i + 1) % 50 == 0:` 检查和打印
   - 在处理完每个结果后（第192行 print ERROR 之后），添加：
     ```python
     elapsed = time.time() - start_time
     _print_progress(i + 1, len(tasks), elapsed)
     ```

5. 保持错误处理逻辑不变，只是移除旧的进度打印

注意：
- 进度条字符使用 `█` (filled) 和 `░` (empty)，与 generate_training_data.py 一致
- flush=True 确保进度立即显示
- 进度条应在循环内每次迭代都调用，而非仅每50次
  </action>
  <verify>
运行以下命令检查语法和基本结构：
```bash
python3 -m py_compile src/grpo/baseline.py
grep -n "_print_progress" src/grpo/baseline.py
grep -n "import time" src/grpo/baseline.py
grep -n "start_time = time.time()" src/grpo/baseline.py
```

验证：
- 编译成功无语法错误
- _print_progress 函数定义存在
- time 模块已导入
- start_time 在 ProcessPoolExecutor 前初始化
  </verify>
  <done>
- baseline.py 包含 `import time` 导入
- 新增 `_print_progress(completed, total, elapsed)` 函数，实现30字符宽的进度条
- main() 函数在 ProcessPoolExecutor 前初始化 `start_time = time.time()`
- ProcessPoolExecutor 循环中每次迭代调用 `_print_progress(i + 1, len(tasks), elapsed)`
- 移除了旧的每50项打印逻辑 `if (i + 1) % 50 == 0:`
- 代码通过 py_compile 检查无语法错误
  </done>
</task>

</tasks>

<verification>
执行以下验证步骤：

1. 语法检查：
   ```bash
   python3 -m py_compile src/grpo/baseline.py
   ```

2. 结构检查：
   ```bash
   grep -A 15 "def _print_progress" src/grpo/baseline.py
   grep -B 2 -A 2 "start_time = time.time()" src/grpo/baseline.py
   ```

3. 功能测试（可选，如果有测试数据）：
   ```bash
   python3 src/grpo/baseline.py --workers 2
   ```
   应显示实时进度条，格式类似：
   ```
   进度: |███████████░░░░░░░░░░░░░░░░░░░| 15/40 (37%) 已用:45s 剩余:75s
   ```
</verification>

<success_criteria>
- src/grpo/baseline.py 成功导入 time 模块
- _print_progress 函数存在且逻辑正确（进度条、百分比、ETA计算）
- ProcessPoolExecutor 循环在每次迭代时调用进度条打印
- 旧的每50项打印逻辑已完全移除
- 代码无语法错误，可以正常编译
- 进度条格式与 generate_training_data.py 保持一致
</success_criteria>

<output>
完成后创建 `.planning/quick/1-grpo-baseline-sh-data-sh/1-SUMMARY.md`
</output>
