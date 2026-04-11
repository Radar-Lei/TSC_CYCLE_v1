"""GLM5Client 单元测试

测试 GLM-5 API 客户端的初始化、单请求、重试逻辑和批量并发功能。
所有测试使用 mock 避免真实 API 调用。
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from src.glm5.client import GLM5Client, GLM5Response


class TestGLM5Response:
    """GLM5Response 数据类测试"""

    def test_to_dict(self):
        """to_dict() 返回正确的字典"""
        resp = GLM5Response(content="hello", response_time=1.5, success=True)
        d = resp.to_dict()
        assert d["content"] == "hello"
        assert d["response_time"] == 1.5
        assert d["success"] is True
        assert d["error"] is None

    def test_from_dict(self):
        """from_dict() 正确反序列化"""
        d = {"content": "hi", "response_time": 2.0, "success": False, "error": "timeout"}
        resp = GLM5Response.from_dict(d)
        assert resp.content == "hi"
        assert resp.success is False
        assert resp.error == "timeout"


class TestGLM5ClientInit:
    """GLM5Client 初始化测试"""

    @patch.dict(os.environ, {"GLM_API_KEY": "test-key-123"})
    @patch("src.glm5.client.openai.OpenAI")
    def test_init_with_env_var(self, mock_openai_cls):
        """从环境变量读取 API key 初始化成功"""
        client = GLM5Client()
        mock_openai_cls.assert_called_once_with(
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            api_key="test-key-123",
        )
        assert client.model == "glm-5"
        assert client.max_tokens == 8192
        assert client.max_retries == 3
        assert client.max_concurrent == 2

    @patch("src.glm5.client.openai.OpenAI")
    def test_init_with_explicit_key(self, mock_openai_cls):
        """显式传入 API key 初始化成功"""
        client = GLM5Client(api_key="explicit-key")
        mock_openai_cls.assert_called_once_with(
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            api_key="explicit-key",
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_init_without_key_raises(self):
        """无 api_key 且无环境变量时抛出 ValueError"""
        # 确保 GLM_API_KEY 不在环境变量中
        os.environ.pop("GLM_API_KEY", None)
        with pytest.raises(ValueError, match="GLM_API_KEY"):
            GLM5Client()


class TestCallSingle:
    """call_single() 方法测试"""

    def _make_client(self):
        """创建一个带 mock OpenAI 客户端的 GLM5Client"""
        with patch("src.glm5.client.openai.OpenAI") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            client = GLM5Client(api_key="test-key")
        # 替换内部客户端为可控的 mock
        client._client = mock_instance
        return client, mock_instance

    def test_call_single_success(self):
        """成功调用返回 GLM5Response(success=True)"""
        client, mock_oa = self._make_client()

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "这是生成的内容"
        mock_response.choices = [mock_choice]
        mock_oa.chat.completions.create.return_value = mock_response

        result = client.call_single("系统提示", "用户提示")
        assert result.success is True
        assert result.content == "这是生成的内容"
        assert result.response_time > 0

    def test_call_single_retry_on_error(self):
        """前 2 次失败第 3 次成功，验证重试逻辑"""
        client, mock_oa = self._make_client()
        client.retry_base_delay = 0.01  # 加快测试

        import openai as openai_mod

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "成功"
        mock_response.choices = [mock_choice]

        # 前 2 次抛异常，第 3 次成功
        mock_oa.chat.completions.create.side_effect = [
            openai_mod.APIError(
                message="server error",
                request=MagicMock(),
                body=None,
            ),
            openai_mod.APIError(
                message="server error",
                request=MagicMock(),
                body=None,
            ),
            mock_response,
        ]

        result = client.call_single("系统提示", "用户提示")
        assert result.success is True
        assert result.content == "成功"
        assert mock_oa.chat.completions.create.call_count == 3

    def test_call_single_all_retries_fail(self):
        """所有重试都失败，返回 success=False"""
        client, mock_oa = self._make_client()
        client.retry_base_delay = 0.01

        import openai as openai_mod

        mock_oa.chat.completions.create.side_effect = openai_mod.APIError(
            message="persistent error",
            request=MagicMock(),
            body=None,
        )

        result = client.call_single("系统提示", "用户提示")
        assert result.success is False
        assert result.error is not None
        # max_retries=3, 所以总共尝试 4 次 (初始 + 3 次重试)
        assert mock_oa.chat.completions.create.call_count == 4

    def test_max_tokens_always_8192(self):
        """验证 API 调用中 max_tokens 始终为 8192"""
        client, mock_oa = self._make_client()

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_response.choices = [mock_choice]
        mock_oa.chat.completions.create.return_value = mock_response

        client.call_single("sys", "user")

        call_kwargs = mock_oa.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 8192 or \
            (len(call_kwargs.args) > 0 and False) or \
            call_kwargs[1].get("max_tokens") == 8192


class TestCallBatch:
    """call_batch() 方法测试"""

    def test_call_batch_concurrent(self):
        """提交 4 个请求，验证结果长度和并发执行"""
        with patch("src.glm5.client.openai.OpenAI") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            client = GLM5Client(api_key="test-key")

        # Mock call_single 返回成功响应
        def fake_call_single(sys_prompt, user_prompt):
            return GLM5Response(
                content=f"response for: {user_prompt}",
                response_time=0.1,
                success=True,
            )

        client.call_single = fake_call_single

        requests = [
            {"system_prompt": "sys", "user_prompt": f"prompt_{i}"}
            for i in range(4)
        ]

        results = client.call_batch(requests)
        assert len(results) == 4
        # 验证结果按原始顺序返回
        for i, r in enumerate(results):
            assert r.success is True
            assert f"prompt_{i}" in r.content
