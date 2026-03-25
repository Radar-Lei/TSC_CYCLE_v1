"""GLM-5 输出解析和约束校验模块单元测试"""

import pytest
from src.glm5.validator import parse_glm5_output, validate_constraints, ParsedOutput


class TestParseGlm5Output:
    """parse_glm5_output 函数测试"""

    def test_parse_without_start_tag(self):
        """Test 1: 解析不含 <start_working_out> 前缀的内容"""
        content = (
            '分析各相位饱和度情况<end_working_out>'
            '<SOLUTION>[{"phase_id":0,"final":30}]</SOLUTION>'
        )
        result = parse_glm5_output(content)
        assert result.success is True
        assert result.think_text == "分析各相位饱和度情况"
        assert result.solution == [{"phase_id": 0, "final": 30}]
        assert result.raw_content == content

    def test_parse_with_start_tag(self):
        """Test 2: 解析含 <start_working_out> 前缀的完整标签内容"""
        content = (
            '<start_working_out>详细推理过程<end_working_out>'
            '<SOLUTION>[{"phase_id":0,"final":25},{"phase_id":1,"final":35}]</SOLUTION>'
        )
        result = parse_glm5_output(content)
        assert result.success is True
        assert result.think_text == "详细推理过程"
        assert len(result.solution) == 2

    def test_parse_missing_solution_end_tag(self):
        """Test 3: 缺少 </SOLUTION> 标签"""
        content = '推理<end_working_out><SOLUTION>[{"phase_id":0,"final":30}]'
        result = parse_glm5_output(content)
        assert result.success is False
        assert result.error != ""

    def test_parse_invalid_json(self):
        """Test 4: SOLUTION 内非法 JSON"""
        content = '推理<end_working_out><SOLUTION>{not valid json}</SOLUTION>'
        result = parse_glm5_output(content)
        assert result.success is False
        assert result.error != ""

    def test_think_length_calculated(self):
        """think_length 为 think_text 的字符数"""
        content = (
            '<start_working_out>ABC<end_working_out>'
            '<SOLUTION>[{"phase_id":0,"final":30}]</SOLUTION>'
        )
        result = parse_glm5_output(content)
        assert result.think_length == 3

    def test_to_dict(self):
        """ParsedOutput.to_dict() 返回字典"""
        content = (
            '推理<end_working_out>'
            '<SOLUTION>[{"phase_id":0,"final":30}]</SOLUTION>'
        )
        result = parse_glm5_output(content)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "success" in d
        assert "think_text" in d
        assert "solution" in d


class TestValidateConstraints:
    """validate_constraints 函数测试"""

    @pytest.fixture
    def phase_waits(self):
        """标准两相位配置"""
        return [
            {"phase_id": 0, "min_green": 10, "max_green": 60},
            {"phase_id": 1, "min_green": 15, "max_green": 45},
        ]

    def test_valid_solution(self, phase_waits):
        """Test 5: 合法 solution"""
        solution = [
            {"phase_id": 0, "final": 30},
            {"phase_id": 1, "final": 25},
        ]
        valid, msg = validate_constraints(solution, phase_waits)
        assert valid is True
        assert msg == ""

    def test_wrong_phase_order(self, phase_waits):
        """Test 6: 相位顺序错误"""
        solution = [
            {"phase_id": 1, "final": 25},
            {"phase_id": 0, "final": 30},
        ]
        valid, msg = validate_constraints(solution, phase_waits)
        assert valid is False
        assert "顺序" in msg

    def test_green_time_out_of_range(self, phase_waits):
        """Test 7: 绿灯时间越界"""
        solution = [
            {"phase_id": 0, "final": 5},  # < min_green(10)
            {"phase_id": 1, "final": 25},
        ]
        valid, msg = validate_constraints(solution, phase_waits)
        assert valid is False
        assert "绿灯" in msg

    def test_non_integer_final(self, phase_waits):
        """Test 8: final 非整数"""
        solution = [
            {"phase_id": 0, "final": 30.5},
            {"phase_id": 1, "final": 25},
        ]
        valid, msg = validate_constraints(solution, phase_waits)
        assert valid is False
        assert "整数" in msg

    def test_length_mismatch(self, phase_waits):
        """Test 9: solution 长度与 phase_waits 不匹配"""
        solution = [
            {"phase_id": 0, "final": 30},
        ]
        valid, msg = validate_constraints(solution, phase_waits)
        assert valid is False
        assert "数量" in msg or "不匹配" in msg
