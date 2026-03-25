"""
GLM-5 结果到 SFT 训练数据组装逻辑的单元测试

测试 assemble_sft_record 的正常和异常 case，
验证 messages 格式、标签格式、JSON 序列化。
支持 BatchGenerator 格式和简化格式两种输入。
"""

import json
import pytest


def _make_record(think="这是推理过程", solution=None, prompt="用户输入的 prompt"):
    """构造测试用的简化格式 results.jsonl 单行记录"""
    if solution is None:
        solution = [
            {"phase_id": 0, "final": 20},
            {"phase_id": 1, "final": 15},
        ]
    return {
        "prompt": prompt,
        "prediction": {"phase_waits": []},
        "think": think,
        "solution": solution,
        "metadata": {"scenario": "test", "tl_id": "tl_0"},
        "think_length": len(think),
        "attempt": 1,
    }


def _make_generator_record(
    think_text="这是推理过程",
    solution=None,
    prompt="用户输入的 prompt",
    status="success",
):
    """构造 BatchGenerator 格式的 results.jsonl 单行记录"""
    if solution is None:
        solution = [
            {"phase_id": 0, "final": 20},
            {"phase_id": 1, "final": 15},
        ]
    return {
        "id": "test_tl_0",
        "status": status,
        "think_text": think_text,
        "solution": solution,
        "think_length": len(think_text),
        "response_time": 1.5,
        "retries": 0,
        "sample": {
            "prompt": prompt,
            "prediction": {"phase_waits": []},
            "state_file": "test.xml",
            "metadata": {"scenario": "test", "tl_id": "tl_0"},
        },
    }


class TestAssembleSftRecord:
    """assemble_sft_record 单元测试"""

    def test_normal_record_has_three_roles(self):
        """Test 1: 简化格式转换为 messages 格式，包含 system/user/assistant 三个角色"""
        from src.glm5.assembler import assemble_sft_record

        record = _make_record()
        result = assemble_sft_record(record)

        assert result is not None
        messages = result["messages"]
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_generator_format_has_three_roles(self):
        """Test 1b: BatchGenerator 格式转换为 messages 格式"""
        from src.glm5.assembler import assemble_sft_record

        record = _make_generator_record()
        result = assemble_sft_record(record)

        assert result is not None
        messages = result["messages"]
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_assistant_content_has_correct_tags(self):
        """Test 2: assistant content 使用正确的标签格式"""
        from src.glm5.assembler import assemble_sft_record

        record = _make_record(think="分析交通流量")
        result = assemble_sft_record(record)

        content = result["messages"][2]["content"]
        assert content.startswith("<start_working_out>")
        assert "<end_working_out>" in content
        assert "<SOLUTION>" in content
        assert "</SOLUTION>" in content
        # 验证结构: think 在 working_out 标签内, solution 在 SOLUTION 标签内
        assert content.index("<start_working_out>") < content.index("<end_working_out>")
        assert content.index("<end_working_out>") < content.index("<SOLUTION>")
        assert content.index("<SOLUTION>") < content.index("</SOLUTION>")

    def test_solution_serialized_as_compact_json(self):
        """Test 3: solution 列表正确序列化为紧凑 JSON 数组"""
        from src.glm5.assembler import assemble_sft_record

        solution = [{"phase_id": 0, "final": 20}, {"phase_id": 1, "final": 15}]
        record = _make_record(solution=solution)
        result = assemble_sft_record(record)

        content = result["messages"][2]["content"]
        # 提取 SOLUTION 标签内的内容
        start = content.index("<SOLUTION>") + len("<SOLUTION>")
        end = content.index("</SOLUTION>")
        solution_str = content[start:end]

        # 验证是紧凑 JSON (无空格)
        parsed = json.loads(solution_str)
        assert parsed == solution
        # 紧凑格式: separators=(',', ':')
        expected = json.dumps(solution, ensure_ascii=False, separators=(",", ":"))
        assert solution_str == expected

    def test_empty_solution_returns_none(self):
        """Test 4: 跳过 solution 为空列表的无效记录"""
        from src.glm5.assembler import assemble_sft_record

        record = _make_record(solution=[])
        result = assemble_sft_record(record)
        assert result is None

    def test_missing_solution_returns_none(self):
        """Test 4b: 跳过缺少 solution 字段的记录"""
        from src.glm5.assembler import assemble_sft_record

        record = _make_record()
        del record["solution"]
        result = assemble_sft_record(record)
        assert result is None

    def test_non_success_status_returns_none(self):
        """Test 4c: 跳过 status 非 success 的 BatchGenerator 记录"""
        from src.glm5.assembler import assemble_sft_record

        for status in ["api_error", "constraint_failed"]:
            record = _make_generator_record(status=status)
            result = assemble_sft_record(record)
            assert result is None, f"Expected None for status={status}"

    def test_system_prompt_matches_prompt_builder(self):
        """验证 system message 使用 prompt_builder 中的 SYSTEM_PROMPT"""
        from src.glm5.assembler import assemble_sft_record
        from src.data_generator.prompt_builder import SYSTEM_PROMPT

        record = _make_record()
        result = assemble_sft_record(record)

        assert result["messages"][0]["content"] == SYSTEM_PROMPT

    def test_user_content_is_prompt_field(self):
        """验证 user message 内容为 record 的 prompt 字段 (简化格式)"""
        from src.glm5.assembler import assemble_sft_record

        prompt_text = "这是一个特定的用户 prompt"
        record = _make_record(prompt=prompt_text)
        result = assemble_sft_record(record)

        assert result["messages"][1]["content"] == prompt_text

    def test_generator_format_extracts_prompt_from_sample(self):
        """验证 BatchGenerator 格式从 sample.prompt 提取用户 prompt"""
        from src.glm5.assembler import assemble_sft_record

        prompt_text = "BatchGenerator 的用户 prompt"
        record = _make_generator_record(prompt=prompt_text)
        result = assemble_sft_record(record)

        assert result["messages"][1]["content"] == prompt_text

    def test_generator_format_uses_think_text_field(self):
        """验证 BatchGenerator 格式使用 think_text 字段而非 think"""
        from src.glm5.assembler import assemble_sft_record

        think = "BatchGenerator 的推理过程"
        record = _make_generator_record(think_text=think)
        result = assemble_sft_record(record)

        content = result["messages"][2]["content"]
        assert f"<start_working_out>{think}<end_working_out>" in content
