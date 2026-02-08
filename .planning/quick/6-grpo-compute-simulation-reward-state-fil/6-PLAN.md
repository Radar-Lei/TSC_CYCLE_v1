---
phase: quick-6
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/grpo/simulation_reward.py
autonomous: true

must_haves:
  truths:
    - "compute_simulation_reward() 可以通过 kwargs 接收数据集列参数"
    - "TRL GRPOTrainer 调用时不会抛出 missing positional arguments 错误"
    - "state_file 和 tl_id (单数) 参数名与数据集列名匹配"
  artifacts:
    - path: "src/grpo/simulation_reward.py"
      provides: "修复后的 compute_simulation_reward() 函数签名"
      contains: "state_file: List[str]"
  key_links:
    - from: "src/scripts/train_grpo.py:372"
      to: "src.grpo.simulation_reward.compute_simulation_reward"
      via: "lambda wrapper with **kwargs"
      pattern: "compute_simulation_reward\\(.*\\*\\*kwargs"
---

<objective>
修复 GRPO `compute_simulation_reward()` 函数参数不匹配问题

**目的:** 解决 TRL GRPOTrainer 调用奖励函数时参数传递错误，使训练能够正常进行

**输出:** 修复后的 simulation_reward.py，函数签名与 TRL 和数据集列名兼容
</objective>

<execution_context>
@/home/samuel/.claude/get-shit-done/workflows/execute-plan.md
@/home/samuel/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

**错误信息:**
```
TypeError: compute_simulation_reward() missing 2 required positional arguments: 'state_files' and 'tl_ids'
```

**根本原因:**
1. 函数签名参数名为 `state_files` 和 `tl_ids` (复数)
2. 数据集列名为 `state_file` 和 `tl_id` (单数)
3. TRL GRPOTrainer 通过 `**kwargs` 传递数据集列，直接使用列名
4. 参数定义为位置参数，但 TRL 以关键字形式传递

**修复策略:**
将参数名改为单数形式 (`state_file`, `tl_id`) 并改为仅关键字参数，与数据集列名匹配
</context>

<tasks>

<task type="auto">
  <name>修复 compute_simulation_reward() 函数签名</name>
  <files>src/grpo/simulation_reward.py</files>
  <action>
修改 `compute_simulation_reward()` 函数签名 (line 176-183):

**当前签名:**
```python
def compute_simulation_reward(
    completions: List[Any],
    prompts: List[str],
    state_files: List[str],  # 复数，位置参数
    tl_ids: List[str],       # 复数，位置参数
    phase_config: Dict[str, Any],
    **kwargs
) -> List[float]:
```

**修改为:**
```python
def compute_simulation_reward(
    completions: List[Any],
    *,  # 强制后续参数为仅关键字参数
    prompts: List[str] = None,
    state_file: List[str] = None,   # 单数，默认值，匹配数据集列名
    tl_id: List[str] = None,        # 单数，默认值，匹配数据集列名
    phase_config: Dict[str, Any],
    **kwargs
) -> List[float]:
```

**同步更新函数内部变量引用 (line 222):**
```python
# 当前: for i, (completion, state_file, tl_id) in enumerate(zip(completions, state_files, tl_ids)):
# 修改为: (参数名已经是 state_file 和 tl_id，无需变更)
```

**理由:**
- 参数名改为单数 (`state_file`, `tl_id`) 与数据集列名完全匹配
- 使用 `*` 强制关键字传参，符合 TRL 调用方式
- 添加默认值 `None` 允许函数优雅处理缺失参数
- `prompts` 也改为可选，因为当前代码未强依赖它 (仅用于 phase 验证)
  </action>
  <verify>
运行以下命令验证语法正确:
```bash
python -c "from src.grpo.simulation_reward import compute_simulation_reward; print('Import OK')"
```

检查函数签名是否正确更新:
```bash
grep -A 5 "def compute_simulation_reward" src/grpo/simulation_reward.py
```
  </verify>
  <done>
- `compute_simulation_reward()` 函数签名已更新为仅关键字参数
- 参数名 `state_file` 和 `tl_id` (单数) 与数据集列名匹配
- 函数可以成功导入，无语法错误
  </done>
</task>

<task type="auto">
  <name>验证修复与数据集列名匹配</name>
  <files>src/grpo/data_loader.py</files>
  <action>
验证数据集列名与修复后的参数名一致:

1. 读取 `src/grpo/data_loader.py` 中 `prepare_grpo_dataset()` 返回的数据集字段 (line 149-154)
2. 确认字段名为: `state_file` (单数), `tl_id` (单数)
3. 如果字段名与修复后的参数名完全匹配，修复有效

**预期匹配:**
```python
# data_loader.py
grpo_item = {
    "state_file": sample["state_file"],  # 单数
    "tl_id": tl_id,                       # 单数
    ...
}

# simulation_reward.py (修复后)
def compute_simulation_reward(
    ...,
    state_file: List[str] = None,  # 单数
    tl_id: List[str] = None,       # 单数
    ...
)
```
  </action>
  <verify>
运行以下命令检查字段名:
```bash
grep -E "(state_file|tl_id)" src/grpo/data_loader.py | head -10
```
  </verify>
  <done>
- 数据集字段名 (`state_file`, `tl_id`) 与修复后的函数参数名完全匹配
- TRL 将能够正确传递参数到奖励函数
  </done>
</task>

</tasks>

<verification>
运行以下命令验证修复:

1. **语法检查:**
   ```bash
   python -c "from src.grpo.simulation_reward import compute_simulation_reward; print('✓ Import successful')"
   ```

2. **签名检查:**
   ```bash
   python -c "import inspect; from src.grpo.simulation_reward import compute_simulation_reward; print(inspect.signature(compute_simulation_reward))"
   ```

   预期输出应包含 `state_file=None, tl_id=None` (单数，带默认值)

3. **列名匹配检查:**
   ```bash
   grep -E "\"(state_file|tl_id)\"" src/grpo/data_loader.py
   ```

   应显示数据集使用单数列名
</verification>

<success_criteria>
- [ ] `compute_simulation_reward()` 函数签名已更新
- [ ] 参数 `state_files` → `state_file`, `tl_ids` → `tl_id` (改为单数)
- [ ] 参数改为仅关键字参数 (使用 `*` 分隔符)
- [ ] 参数添加默认值 `None`
- [ ] 函数可以成功导入，无语法错误
- [ ] 参数名与数据集列名 (`state_file`, `tl_id`) 完全匹配
- [ ] TRL GRPOTrainer 可以通过 `**kwargs` 正确传递参数
</success_criteria>

<output>
完成后创建 `.planning/quick/6-grpo-compute-simulation-reward-state-fil/6-SUMMARY.md`
</output>
