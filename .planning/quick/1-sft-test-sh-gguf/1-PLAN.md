---
phase: quick-1-sft-test-sh-gguf
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - docker/sft_test.sh
autonomous: true
requirements: [QUICK-1]
user_setup: []

must_haves:
  truths:
    - "用户可以使用 --gguf 参数选择 GGUF 模式"
    - "默认情况下仍使用 PyTorch 模型测试"
    - "GGUF 模式调用 src/test_gguf.py，PyTorch 模式调用 src/sft/test_inference.py"
  artifacts:
    - path: "docker/sft_test.sh"
      provides: "带 GGUF 选项的 SFT 测试入口脚本"
      min_lines: 50
  key_links:
    - from: "docker/sft_test.sh"
      to: "src/sft/test_inference.py"
      via: "--gguf 参数未指定时"
      pattern: "test_inference.py"
    - from: "docker/sft_test.sh"
      to: "src/test_gguf.py"
      via: "--gguf 参数指定时"
      pattern: "test_gguf.py"
---

<objective>
修改 docker/sft_test.sh 脚本，增加 --gguf 选项让用户可以选择使用 GGUF 模型进行测试。

Purpose: 为用户提供快速测试 GGUF 量化模型的能力，无需 GPU 显存即可验证量化后模型的推理效果。
Output: 更新后的 docker/sft_test.sh 脚本，支持 --gguf 参数切换。
</objective>

<execution_context>
@/home/samuel/.claude/get-shit-done/workflows/execute-plan.md
@/home/samuel/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md

# 当前脚本
@docker/sft_test.sh

# GGUF 测试脚本
@src/test_gguf.py

# PyTorch 测试脚本
@src/sft/test_inference.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: 添加 --gguf 选项到 sft_test.sh</name>
  <files>docker/sft_test.sh</files>
  <action>
修改 docker/sft_test.sh，添加 --gguf 选项支持。

**实现要求:**

1. 解析命令行参数:
   - 支持 `--gguf` 标志（无值，仅作为开关）
   - 支持 `[NUM_SAMPLES]` 位置参数（默认 5）
   - 用法示例:
     - `./docker/sft_test.sh 3` → PyTorch 模式，3 条样本
     - `./docker/sft_test.sh --gguf 3` → GGUF 模式，3 条样本
     - `./docker/sft_test.sh --gguf` → GGUF 模式，5 条样本（默认）

2. 参数解析逻辑（使用 bash while/case）:
   ```bash
   USE_GGUF=false
   NUM_SAMPLES=5

   while [[ $# -gt 0 ]]; do
       case $1 in
           --gguf)
               USE_GGUF=true
               shift
               ;;
           *)
               NUM_SAMPLES="$1"
               shift
               ;;
       esac
   done
   ```

3. 更新 echo 输出，显示当前模式:
   - `[测试模式] PyTorch` 或 `[测试模式] GGUF`

4. 根据 USE_GGUF 变量选择执行脚本:
   - GGUF 模式: `src/test_gguf.py`
   - PyTorch 模式: `src/sft/test_inference.py`（原有行为）

5. 更新脚本头部注释，说明新用法。

**不要改变:**
- Docker 容器配置（IMAGE_NAME, CONTAINER_NAME 等）
- 原有的 PyTorch 模式作为默认行为
  </action>
  <verify>
    ```bash
    # 检查脚本语法
    bash -n docker/sft_test.sh && echo "语法检查通过"

    # 检查 --gguf 相关代码存在
    grep -q "USE_GGUF" docker/sft_test.sh && echo "USE_GGUF 变量存在"
    grep -q "test_gguf.py" docker/sft_test.sh && echo "test_gguf.py 引用存在"
    grep -q "\-\-gguf" docker/sft_test.sh && echo "--gguf 选项说明存在"
    ```
  </verify>
  <done>
- 脚本支持 `--gguf` 参数
- 默认行为不变（PyTorch 模式）
- GGUF 模式调用 `src/test_gguf.py`
- 脚本头部注释更新
  </done>
</task>

</tasks>

<verification>
运行更新后的脚本验证两种模式:
1. `./docker/sft_test.sh --help` 或检查参数解析逻辑
2. 确认 `--gguf` 标志正确切换到 GGUF 模式
3. 确认默认行为仍为 PyTorch 模式
</verification>

<success_criteria>
- [ ] `docker/sft_test.sh` 支持 `--gguf` 参数
- [ ] `./docker/sft_test.sh 3` 使用 PyTorch 模式（默认）
- [ ] `./docker/sft_test.sh --gguf 3` 使用 GGUF 模式
- [ ] 脚本语法正确（bash -n 通过）
- [ ] 输出显示当前测试模式
</success_criteria>

<output>
After completion, create `.planning/quick/1-sft-test-sh-gguf/1-SUMMARY.md`
</output>
