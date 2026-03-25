"""GLM-5 prompt 构建模块单元测试"""

import pytest
from src.glm5.prompt import build_glm5_prompts, GLM5_SYSTEM_PROMPT
from src.data_generator.prompt_builder import PromptBuilder, SYSTEM_PROMPT
from src.data_generator.models import Prediction


@pytest.fixture
def sample_dict():
    """train.jsonl 行格式的样本字典"""
    return {
        "prompt": "...",
        "prediction": {
            "as_of": "2026-01-15 08:30:00",
            "phase_waits": [
                {
                    "phase_id": 0,
                    "pred_saturation": 1.2,
                    "min_green": 10,
                    "max_green": 60,
                    "capacity": 30,
                },
                {
                    "phase_id": 1,
                    "pred_saturation": 0.5,
                    "min_green": 15,
                    "max_green": 45,
                    "capacity": 25,
                },
            ],
        },
        "state_file": "outputs/states/test/state.xml",
        "metadata": {"tl_id": "test_tl"},
    }


class TestBuildGlm5Prompts:
    """build_glm5_prompts 函数测试"""

    def test_returns_tuple(self, sample_dict):
        """Test 1: 返回 (system_prompt, user_prompt) 元组"""
        result = build_glm5_prompts(sample_dict)
        assert isinstance(result, tuple)
        assert len(result) == 2
        system_prompt, user_prompt = result
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)

    def test_system_prompt_contains_think_length_guidance(self, sample_dict):
        """Test 2: system_prompt 包含原始 SYSTEM_PROMPT 内容 + think 链长度引导"""
        system_prompt, _ = build_glm5_prompts(sample_dict)
        # 包含原始 SYSTEM_PROMPT 的内容
        assert "交通信号配时优化专家" in system_prompt
        # 包含 ~500 token think 链长度引导
        assert "500" in system_prompt

    def test_user_prompt_matches_prompt_builder(self, sample_dict):
        """Test 3: user_prompt 与 PromptBuilder 输出一致"""
        _, user_prompt = build_glm5_prompts(sample_dict)
        prediction = Prediction.from_dict(sample_dict["prediction"])
        expected = PromptBuilder().build_prompt(prediction)
        assert user_prompt == expected

    def test_system_prompt_contains_tag_descriptions(self, sample_dict):
        """Test 4: system_prompt 包含标签说明"""
        system_prompt, _ = build_glm5_prompts(sample_dict)
        assert "<start_working_out>" in system_prompt
        assert "<SOLUTION>" in system_prompt


class TestGlm5SystemPrompt:
    """GLM5_SYSTEM_PROMPT 常量测试"""

    def test_contains_original_system_prompt(self):
        """GLM5_SYSTEM_PROMPT 包含原始 SYSTEM_PROMPT 的全部内容"""
        assert SYSTEM_PROMPT in GLM5_SYSTEM_PROMPT

    def test_is_longer_than_original(self):
        """GLM5_SYSTEM_PROMPT 比原始 SYSTEM_PROMPT 更长 (追加了引导文本)"""
        assert len(GLM5_SYSTEM_PROMPT) > len(SYSTEM_PROMPT)
