---
phase: quick-4
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/grpo/trainer.py
  - src/grpo/format_reward.py
  - src/grpo/simulation_reward.py
  - src/scripts/train_grpo.py
autonomous: true
---

<objective>
修复 GRPO 训练中的三个关键问题:
1. Qwen3 模型的 generation_config 默认值 (max_length=262144, temperature=0.6) 覆盖了我们的训练参数
2. check_phase_validity() 函数签名与 TRL reward callback 不兼容 (缺少 phase_config 位置参数)
3. phase 不合法的 completion 仍然会触发 SUMO 仿真,浪费计算资源

Purpose: 让 GRPO 训练能正确运行,避免 TypeError 崩溃,同时优化生成参数和仿真资源利用
Output: 四个文件的修复,GRPO 训练可以端到端运行
</objective>

<context>
@src/grpo/trainer.py
@src/grpo/format_reward.py
@src/grpo/simulation_reward.py
@src/scripts/train_grpo.py
@src/grpo/data_loader.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: 修复 generation_config 默认值 + GRPOConfig.temperature</name>
  <files>src/grpo/trainer.py</files>
  <action>
  两处修改:

  1. 在 `load_base_model()` 函数中,`FastLanguageModel.from_pretrained()` 返回 model 之后、`FastLanguageModel.get_peft_model()` 之前 (即第 96 行之后),添加 generation_config 覆盖:

  ```python
  # 覆盖 Qwen3 默认 generation_config (max_length=262144, temperature=0.6)
  model.generation_config.max_length = 2048  # 匹配 max_seq_length
  model.generation_config.temperature = 0.9  # GRPO 探索需要较高温度
  model.generation_config.top_p = 0.95
  ```

  同样在 `load_sft_model()` 函数中,`FastLanguageModel.from_pretrained()` 返回 model 之后 (第 169 行之后),添加相同的三行覆盖。

  2. 将 `GRPOConfig.temperature` 默认值从 `1.0` 改为 `0.9` (第 46 行)。

  3. 更新 `__main__` 自测试部分:将 `assert config.temperature == 1.0` 改为 `assert config.temperature == 0.9`,将 `assert params["temperature"] == 1.0` 改为 `assert params["temperature"] == 0.9`。
  </action>
  <verify>
  运行自测试:
  ```bash
  cd /home/samuel/TSC_CYCLE && python -m src.grpo.trainer
  ```
  应输出 "trainer module tests passed!"
  </verify>
  <done>
  - GRPOConfig.temperature 默认值为 0.9
  - load_base_model() 和 load_sft_model() 都在模型加载后覆盖 generation_config (max_length=2048, temperature=0.9, top_p=0.95)
  - 自测试通过
  </done>
</task>

<task type="auto">
  <name>Task 2: 重构 check_phase_validity 签名兼容 TRL + 从 prompt 提取 phase_config</name>
  <files>src/grpo/format_reward.py, src/scripts/train_grpo.py</files>
  <action>
  **核心问题:** TRL 调用奖励函数时签名为 `reward_func(completions, **kwargs)`,其中 kwargs 包含 dataset 的各列 (prompts, state_file, tl_id, metadata 等)。当前 `check_phase_validity(completions, phase_config, **kwargs)` 要求 phase_config 作为位置参数,但 TRL 不会传递它。

  **修改 `src/grpo/format_reward.py`:**

  1. 新增辅助函数 `extract_phase_config_from_prompt(prompt)`:
     - 参数 prompt 是单个 prompt,类型可能是:
       - `List[Dict]` (conversational 模式,即 messages 列表,如 `[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]`)
       - `str` (纯文本模式)
     - 如果是 List[Dict],找到 role=="user" 的消息,提取其 content
     - 如果是 str,直接使用
     - 在 user content 中用 `json.loads()` 解析整个 content(因为 prompt 内容就是 JSON 格式,包含 `phase_waits` 字段)
     - 从解析出的 dict 中提取 `phase_waits` 数组
     - 构建并返回 `Dict[int, Dict]` 格式: `{pw["phase_id"]: {"min_green": pw["min_green"], "max_green": pw["max_green"]} for pw in phase_waits}`
     - 解析失败返回 None

  2. 修改 `check_phase_validity` 签名为 `check_phase_validity(completions, **kwargs)`:
     - 从 `kwargs.get("prompts", [])` 获取 prompts 列表
     - 对每个 completion,取对应索引的 prompt,调用 `extract_phase_config_from_prompt(prompt)` 获取 phase_config
     - 如果提取失败 (prompt 中无法解析出 phase_config),对该 completion 返回 0.0 (无法判断有效性,不奖不罚)
     - 如果提取成功,使用提取到的 phase_config 执行现有的相位有效性检查逻辑 (phase_id 是否存在、final 是否在 min_green~max_green 范围内)
     - 保持原有的返回值: 全部有效 +1.0, 任一无效 -2.0, 无法解析 completion 0.0

  3. 更新 `__main__` 自测试:
     - 修改 check_phase_validity 的测试,不再传 phase_config 位置参数
     - 改为在 kwargs 中传 prompts 参数,prompts 为包含 phase_waits JSON 的 user 消息列表
     - 构造测试用 prompt: `[{"role": "system", "content": "..."}, {"role": "user", "content": json.dumps({"as_of": "2025-01-01", "phase_waits": [{"phase_id": 0, "min_green": 10, "max_green": 60, "pred_saturation": 0.5, "capacity": 30}, {"phase_id": 1, "min_green": 10, "max_green": 60, "pred_saturation": 0.3, "capacity": 30}]})}]`
     - 调用: `check_phase_validity(completions, prompts=[prompt])`

  **修改 `src/scripts/train_grpo.py`:**
  无需修改,因为 `check_phase_validity` 已经在 reward_funcs 列表中直接传递 (第 305 行),签名修改后自动兼容。
  但需要确认不需要额外修改。
  </action>
  <verify>
  运行自测试:
  ```bash
  cd /home/samuel/TSC_CYCLE && python -m src.grpo.format_reward
  ```
  应输出 "All format_reward tests passed!"
  </verify>
  <done>
  - check_phase_validity 签名为 `(completions, **kwargs)`,与 TRL GRPOTrainer 兼容
  - phase_config 自动从 prompts 中的 JSON 解析提取
  - 不再需要外部传入 phase_config
  - 自测试通过,覆盖有效/无效/无法解析三种情况
  </done>
</task>

<task type="auto">
  <name>Task 3: compute_simulation_reward 中 phase 不合法时跳过仿真</name>
  <files>src/grpo/simulation_reward.py</files>
  <action>
  **核心目标:** 在 compute_simulation_reward 中,解析出 plan 后、送入 SUMO 之前,先检查 phase 有效性。如果不合法,直接返回 -1.0 惩罚,跳过耗时的 SUMO 仿真。

  **修改 `src/grpo/simulation_reward.py`:**

  1. 在文件顶部导入 `extract_phase_config_from_prompt`:
     ```python
     from .format_reward import extract_phase_config_from_prompt
     ```

  2. 新增辅助函数 `is_plan_phase_valid(plan, phase_config_dict)`:
     - plan: List[Dict] (解析出的 [{phase_id, final}, ...])
     - phase_config_dict: Dict[int, Dict] (从 prompt 提取的 {phase_id: {min_green, max_green}})
     - 检查每个 item: phase_id 是否在 phase_config_dict 中,final 是否在 min_green~max_green 范围内
     - 全部合法返回 True,任一不合法返回 False

  3. 修改 `compute_simulation_reward` 函数,在解析出 plan 之后 (约第 200 行 `if plan is None` 判断之后),添加 phase 有效性检查:
     - 获取对应的 prompt: 从 prompts 参数获取 (prompts 通过 kwargs 传入,但 compute_simulation_reward 当前已通过 lambda 传入,注意 prompts 在 train_grpo.py 的 lambda 中是通过 **kwargs 透传的)
     - 实际上 prompts 已经是 `compute_simulation_reward` 签名中的参数了 (第 141 行),所以可以直接使用
     - 调用 `extract_phase_config_from_prompt(prompts[i])` 提取 phase_config
     - 如果提取成功,调用 `is_plan_phase_valid(plan, phase_config_dict)`
     - 如果 plan 不合法,将该 evaluation 标记为 "invalid" (不加入 evaluations,最终返回 -1.0)

  具体实现: 在循环中,plan 解析成功后,添加:
  ```python
  # 检查 phase 有效性,不合法跳过仿真
  if i < len(prompts):
      pc = extract_phase_config_from_prompt(prompts[i])
      if pc is not None and not is_plan_phase_valid(plan, pc):
          evaluations.append("invalid")  # 标记为不合法
          continue
  ```

  在最终计算奖励时,处理 "invalid" 标记:
  ```python
  for result in results:
      if result == "invalid":
          rewards.append(-1.0)  # phase 不合法惩罚
      elif result is None:
          ...
  ```

  注意: `parallel_evaluate` 接收的 evaluations 列表中不能混入字符串。所以改用两个列表:
  - 保持 evaluations 仍然只有 None 和 tuple
  - 额外维护一个 `skip_indices: Dict[int, float]` 记录需要跳过的索引和对应惩罚分数
  - 在最终组装 rewards 时,先检查 skip_indices

  实现方式:
  ```python
  skip_indices = {}  # index -> penalty score

  for i, (completion, state_file, tl_id) in enumerate(zip(...)):
      # ... 提取 content, 解析 plan ...
      if plan is None:
          evaluations.append(None)
          continue

      # 检查 phase 有效性
      if i < len(prompts):
          pc = extract_phase_config_from_prompt(prompts[i])
          if pc is not None and not is_plan_phase_valid(plan, pc):
              evaluations.append(None)  # 占位
              skip_indices[i] = -1.0
              continue

      # ... 正常构建评估任务 ...
  ```

  在计算奖励时:
  ```python
  rewards = []
  for i, result in enumerate(results):
      if i in skip_indices:
          rewards.append(skip_indices[i])
      elif result is None:
          rewards.append(float('nan'))
      elif not result.success:
          rewards.append(float('nan'))
      else:
          reward = compute_metric_reward(result)
          rewards.append(reward)
  ```

  4. 在 evaluation stats 打印中增加 skip 数量:
  ```python
  skipped_invalid = len(skip_indices)
  print(f"Evaluation stats: {success} success, {failed} failed, {skipped} skipped, {skipped_invalid} invalid-phase-skipped (total: {len(results)})")
  ```
  注意这行统计在 parallel_evaluate 中,但 skip_indices 在外层函数。所以将统计移到 compute_simulation_reward 中,或者在 parallel_evaluate 返回后再打印额外信息。

  最简方案: 在 compute_simulation_reward 的奖励计算循环后,打印:
  ```python
  if skip_indices:
      print(f"  Phase validity: {len(skip_indices)} completions skipped simulation (invalid phases)")
  ```
  </action>
  <verify>
  运行模块导入检查:
  ```bash
  cd /home/samuel/TSC_CYCLE && python -c "from src.grpo.simulation_reward import compute_simulation_reward, is_plan_phase_valid; print('OK')"
  ```
  应输出 "OK"

  运行 format_reward 自测试确保没有循环导入:
  ```bash
  cd /home/samuel/TSC_CYCLE && python -m src.grpo.format_reward
  ```
  </verify>
  <done>
  - compute_simulation_reward 在 SUMO 仿真前先检查 phase 有效性
  - phase 不合法的 completion 直接返回 -1.0,不触发 SUMO 仿真
  - 打印跳过统计信息
  - 无循环导入问题
  </done>
</task>

</tasks>

<verification>
1. 各模块自测试通过:
   ```bash
   python -m src.grpo.trainer
   python -m src.grpo.format_reward
   python -c "from src.grpo.simulation_reward import compute_simulation_reward, is_plan_phase_valid; print('OK')"
   ```

2. train_grpo.py 导入无报错:
   ```bash
   python -c "from src.scripts.train_grpo import main; print('imports OK')"
   ```

3. 关键行为验证:
   - GRPOConfig().temperature == 0.9
   - check_phase_validity 接受 (completions, **kwargs) 签名,从 prompts 中自动提取 phase_config
   - compute_simulation_reward 对 phase 不合法的 completion 返回 -1.0 而非运行 SUMO
</verification>

<success_criteria>
- generation_config 在模型加载后被覆盖为 max_length=2048, temperature=0.9, top_p=0.95
- GRPOConfig.temperature 默认值为 0.9
- check_phase_validity 签名兼容 TRL,不再报 TypeError
- phase 不合法的 completion 跳过 SUMO 仿真,返回 -1.0
- 所有自测试和导入检查通过
</success_criteria>
