"""GLM-5 API 客户端，支持并发请求和指数退避重试

提供 GLM5Client 类用于调用智谱 AI GLM-5 模型 API，
支持单请求、批量并发请求和自动指数退避重试。

主要功能:
- GLM5Client: GLM-5 API 客户端
- GLM5Response: API 响应数据类
- 指数退避重试策略 (2s, 4s, 8s)
- ThreadPoolExecutor 并发请求 (默认 4 并发)
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Optional

import openai


@dataclass
class GLM5Response:
    """GLM-5 API 响应数据

    Attributes:
        content: LLM 生成的文本内容
        response_time: API 调用耗时 (秒)
        success: 是否成功
        error: 错误信息 (如果失败)
    """

    content: str
    response_time: float
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """序列化为字典

        Returns:
            包含所有字段的字典
        """
        return {
            "content": self.content,
            "response_time": self.response_time,
            "success": self.success,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GLM5Response":
        """从字典反序列化

        Args:
            data: 包含响应字段的字典

        Returns:
            GLM5Response 实例
        """
        return cls(
            content=data["content"],
            response_time=data["response_time"],
            success=data["success"],
            error=data.get("error"),
        )


class GLM5Client:
    """GLM-5 API 客户端

    通过 OpenAI-compatible API 调用智谱 AI GLM-5 模型，
    支持并发请求和指数退避重试。

    Attributes:
        model: 模型名称 (固定为 glm-5)
        max_tokens: 最大生成 token 数 (固定为 8192)
        max_retries: 最大重试次数
        retry_base_delay: 重试基础延迟 (秒)
        timeout: API 调用超时时间 (秒)
        max_concurrent: 最大并发请求数

    Example:
        >>> client = GLM5Client(api_key="your-key")
        >>> response = client.call_single("系统提示", "用户提示")
        >>> if response.success:
        ...     print(response.content)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
        timeout: float = 120.0,
        max_concurrent: int = 4,
    ):
        """初始化 GLM-5 客户端

        Args:
            api_key: API key，未提供则从 GLM_API_KEY 环境变量读取
            max_retries: 最大重试次数 (默认 3)
            retry_base_delay: 重试基础延迟秒数 (默认 2.0，指数退避: 2s, 4s, 8s)
            timeout: API 调用超时秒数 (默认 120.0)
            max_concurrent: 最大并发请求数 (默认 4)

        Raises:
            ValueError: 未提供 api_key 且 GLM_API_KEY 环境变量未设置
        """
        # API key: 优先参数，否则环境变量
        if api_key is None:
            api_key = os.environ.get("GLM_API_KEY")
        if not api_key:
            raise ValueError(
                "GLM_API_KEY not set: 请通过参数传入 api_key 或设置 GLM_API_KEY 环境变量"
            )

        self._client = openai.OpenAI(
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            api_key=api_key,
        )
        self.model = "glm-5"
        self.max_tokens = 8192
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)

    def call_single(self, system_prompt: str, user_prompt: str) -> GLM5Response:
        """发送单条请求到 GLM-5 API

        带指数退避重试策略，失败时自动重试最多 max_retries 次。

        Args:
            system_prompt: 系统提示 (角色定义)
            user_prompt: 用户提示 (任务内容)

        Returns:
            GLM5Response 包含生成内容或错误信息
        """
        last_error: Optional[str] = None
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            attempt_start = time.time()

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                )

                response_time = time.time() - attempt_start

                content = ""
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    if choice.message and choice.message.content:
                        content = choice.message.content

                return GLM5Response(
                    content=content,
                    response_time=response_time,
                    success=True,
                )

            except (
                openai.APITimeoutError,
                openai.APIConnectionError,
                openai.RateLimitError,
                openai.APIError,
            ) as e:
                last_error = str(e)
                print(
                    f"[GLM5] 重试 {attempt + 1}/{self.max_retries}: {last_error}"
                )

            except Exception as e:
                last_error = str(e)
                print(
                    f"[GLM5] 未预期错误 {attempt + 1}/{self.max_retries}: {last_error}"
                )

            # 指数退避: delay = base * 2^attempt (2s, 4s, 8s)
            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** attempt)
                time.sleep(delay)

        # 所有重试都失败
        total_time = time.time() - start_time
        return GLM5Response(
            content="",
            response_time=total_time,
            success=False,
            error=last_error,
        )

    def call_batch(self, requests: List[dict]) -> List[GLM5Response]:
        """批量并发请求 GLM-5 API

        使用 ThreadPoolExecutor 并发发送多个请求，结果按原始顺序返回。

        Args:
            requests: 请求列表，每个元素为
                      {"system_prompt": str, "user_prompt": str}

        Returns:
            GLM5Response 列表，与输入顺序一致
        """
        results: List[Optional[GLM5Response]] = [None] * len(requests)

        futures = {
            self._executor.submit(
                self.call_single, r["system_prompt"], r["user_prompt"]
            ): i
            for i, r in enumerate(requests)
        }

        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = GLM5Response(
                    content="",
                    response_time=0.0,
                    success=False,
                    error=str(e),
                )

        return results

    def shutdown(self):
        """关闭线程池"""
        self._executor.shutdown(wait=False)
