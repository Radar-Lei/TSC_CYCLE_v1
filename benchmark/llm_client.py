"""
LLM API 客户端

通过 OpenAI-compatible API 调用 LM Studio，支持超时和指数退避重试。

主要功能:
- LLMClient: LM Studio API 客户端
- LLMResponse: API 响应数据类
- 指数退避重试策略
- 结构化输出支持 (JSON Schema)
"""

import time
from dataclasses import dataclass
from typing import Any, Optional

import openai
from loguru import logger


@dataclass
class LLMResponse:
    """LLM API 响应数据

    Attributes:
        content: LLM 生成的文本内容
        response_time: API 调用耗时 (秒)
        success: 是否成功
        error: 错误信息 (如果失败)
        used_structured_output: 是否使用了结构化输出 (用于调试)
        structured_output_failed: 结构化输出是否失败并回退
    """
    content: str
    response_time: float
    success: bool
    error: Optional[str] = None
    used_structured_output: bool = False
    structured_output_failed: bool = False


class LLMClient:
    """LM Studio API 客户端

    通过 OpenAI-compatible API 调用 LM Studio，支持超时和指数退避重试。

    Attributes:
        api_base_url: API 基础 URL (默认: http://localhost:1234/v1)
        timeout_seconds: API 调用超时时间 (秒)
        max_retries: 最大重试次数
        retry_base_delay: 重试基础延迟 (秒)，指数退避

    Example:
        >>> client = LLMClient(
        ...     api_base_url="http://localhost:1234/v1",
        ...     timeout_seconds=120,
        ...     max_retries=2,
        ...     retry_base_delay=1.0
        ... )
        >>> response = client.call("你的 prompt")
        >>> if response.success:
        ...     print(response.content)
        ... else:
        ...     print(f"Error: {response.error}")
    """

    def __init__(
        self,
        api_base_url: str = "http://localhost:1234/v1",
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        retry_base_delay: float = 1.0,
        model: str = "local-model"
    ):
        """初始化 LLM 客户端

        Args:
            api_base_url: API 基础 URL
            timeout_seconds: API 调用超时时间 (秒)
            max_retries: 最大重试次数
            retry_base_delay: 重试基础延迟 (秒)
            model: 模型名称 (LM Studio 通常不需要)
        """
        self.api_base_url = api_base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.model = model

        # 初始化 OpenAI 客户端
        self._client = openai.OpenAI(
            base_url=api_base_url,
            api_key="not-needed"  # LM Studio 不需要 API key
        )

    def call(
        self,
        prompt: str,
        response_format: Optional[dict[str, Any]] = None
    ) -> LLMResponse:
        """调用 LLM API

        发送 prompt 到 LLM API 并返回响应。
        如果调用失败，会进行指数退避重试。

        Args:
            prompt: 输入 prompt
            response_format: Optional JSON Schema for structured output.
                            If provided and fails, will retry without structured output.

        Returns:
            LLMResponse 包含:
            - content: 生成的文本 (成功时)
            - response_time: 调用耗时
            - success: 是否成功
            - error: 错误信息 (失败时)
            - used_structured_output: 是否使用了结构化输出
            - structured_output_failed: 结构化输出是否失败并回退

        Structured Output Fallback Strategy:
        1. If response_format provided, try API call with it first
        2. If API returns error (model doesn't support structured output):
           - Log warning and retry WITHOUT response_format
           - Set structured_output_failed=True in response
        3. If response doesn't match schema:
           - Return content anyway (parsing will handle fallback to SOLUTION tag)
           - Set structured_output_failed=True in response
        """
        # If structured output requested, try it first
        if response_format is not None:
            structured_response = self._call_with_structured_output(prompt, response_format)
            if structured_response.success:
                structured_response.used_structured_output = True
                return structured_response

            # Structured output failed, log and fall back to regular call
            logger.warning(
                "Structured output failed for model {}, falling back to regular call. Error: {}",
                self.model,
                structured_response.error
            )

            # Retry without structured output
            regular_response = self._call_regular(prompt)
            regular_response.structured_output_failed = True
            return regular_response

        # No structured output requested, regular call
        return self._call_regular(prompt)

    def _call_with_structured_output(
        self,
        prompt: str,
        response_format: dict[str, Any]
    ) -> LLMResponse:
        """Try API call with structured output."""
        last_error: Optional[str] = None
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            attempt_start = time.time()

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=self.timeout_seconds,
                    response_format=response_format,
                )

                response_time = time.time() - attempt_start

                content = ""
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    if choice.message and choice.message.content:
                        content = choice.message.content

                logger.debug(
                    "LLM structured output call succeeded in {:.2f}s",
                    response_time
                )

                return LLMResponse(
                    content=content,
                    response_time=response_time,
                    success=True,
                    used_structured_output=True
                )

            except openai.BadRequestError as e:
                # Model doesn't support structured output
                last_error = f"Structured output not supported: {str(e)}"
                logger.warning(
                    "Structured output not supported (attempt {}/{}): {}",
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )
                # Don't retry for BadRequestError - model doesn't support it
                break

            except (openai.APIError, openai.APITimeoutError, openai.APIConnectionError) as e:
                last_error = f"Structured output API error: {str(e)}"
                logger.warning(
                    "Structured output API error (attempt {}/{}): {}",
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            except Exception as e:
                last_error = f"Unexpected error with structured output: {str(e)}"
                logger.warning(
                    "Unexpected structured output error (attempt {}/{}): {}",
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** attempt)
                logger.info("Retrying structured output in {:.1f}s...", delay)
                time.sleep(delay)

        # All retries failed
        total_time = time.time() - start_time
        return LLMResponse(
            content="",
            response_time=total_time,
            success=False,
            error=last_error,
            used_structured_output=True
        )

    def _call_regular(self, prompt: str) -> LLMResponse:
        """Regular API call without structured output."""
        last_error: Optional[str] = None
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            attempt_start = time.time()

            try:
                # 调用 API
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    timeout=self.timeout_seconds,
                )

                response_time = time.time() - attempt_start

                # 提取内容
                content = ""
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    if choice.message and choice.message.content:
                        content = choice.message.content

                logger.debug(
                    "LLM API call succeeded in {:.2f}s (attempt {}/{})",
                    response_time,
                    attempt + 1,
                    self.max_retries + 1
                )

                return LLMResponse(
                    content=content,
                    response_time=response_time,
                    success=True
                )

            except openai.APITimeoutError as e:
                last_error = f"API timeout after {self.timeout_seconds}s: {str(e)}"
                response_time = time.time() - attempt_start
                logger.warning(
                    "LLM API timeout after {:.2f}s (attempt {}/{}): {}",
                    response_time,
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            except openai.APIConnectionError as e:
                last_error = f"API connection error: {str(e)}"
                response_time = time.time() - attempt_start
                logger.warning(
                    "LLM API connection error after {:.2f}s (attempt {}/{}): {}",
                    response_time,
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            except openai.APIError as e:
                last_error = f"API error: {str(e)}"
                response_time = time.time() - attempt_start
                logger.warning(
                    "LLM API error after {:.2f}s (attempt {}/{}): {}",
                    response_time,
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                response_time = time.time() - attempt_start
                logger.warning(
                    "LLM API unexpected error after {:.2f}s (attempt {}/{}): {}",
                    response_time,
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            # 如果还有重试机会，等待后重试
            if attempt < self.max_retries:
                # 指数退避: 1s -> 2s -> 4s
                delay = self.retry_base_delay * (2 ** attempt)
                logger.info(
                    "Retrying in {:.1f}s (attempt {}/{} remaining)...",
                    delay,
                    self.max_retries - attempt,
                    self.max_retries
                )
                time.sleep(delay)

        # 所有重试都失败
        total_time = time.time() - start_time
        logger.error(
            "LLM API call failed after {} attempts: {}",
            self.max_retries + 1,
            last_error
        )

        return LLMResponse(
            content="",
            response_time=total_time,
            success=False,
            error=last_error
        )

    def call_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[dict[str, Any]] = None
    ) -> LLMResponse:
        """调用 LLM API (带系统 prompt)

        发送系统 prompt 和用户 prompt 到 LLM API。

        Args:
            system_prompt: 系统 prompt (角色定义)
            user_prompt: 用户 prompt (任务内容)
            response_format: Optional JSON Schema for structured output

        Returns:
            LLMResponse 包含生成内容或错误信息

        Example:
            >>> response = client.call_with_system(
            ...     system_prompt="你是交通信号配时专家",
            ...     user_prompt="分析这个路口的配时方案"
            ... )
        """
        # If structured output requested, try it first
        if response_format is not None:
            structured_response = self._call_with_system_structured(
                system_prompt, user_prompt, response_format
            )
            if structured_response.success:
                structured_response.used_structured_output = True
                return structured_response

            # Structured output failed, log and fall back
            logger.warning(
                "Structured output failed for model {} (with system prompt), falling back. Error: {}",
                self.model,
                structured_response.error
            )

            regular_response = self._call_with_system_regular(system_prompt, user_prompt)
            regular_response.structured_output_failed = True
            return regular_response

        return self._call_with_system_regular(system_prompt, user_prompt)

    def _call_with_system_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any]
    ) -> LLMResponse:
        """Try API call with system prompt and structured output."""
        last_error: Optional[str] = None
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            attempt_start = time.time()

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    timeout=self.timeout_seconds,
                    response_format=response_format,
                )

                response_time = time.time() - attempt_start

                content = ""
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    if choice.message and choice.message.content:
                        content = choice.message.content

                logger.debug(
                    "LLM structured output with system succeeded in {:.2f}s",
                    response_time
                )

                return LLMResponse(
                    content=content,
                    response_time=response_time,
                    success=True,
                    used_structured_output=True
                )

            except openai.BadRequestError as e:
                last_error = f"Structured output not supported: {str(e)}"
                logger.warning(
                    "Structured output not supported (attempt {}/{}): {}",
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )
                break

            except (openai.APIError, openai.APITimeoutError, openai.APIConnectionError) as e:
                last_error = f"Structured output API error: {str(e)}"
                logger.warning(
                    "Structured output API error (attempt {}/{}): {}",
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.warning(
                    "Unexpected structured output error (attempt {}/{}): {}",
                    attempt + 1,
                    self.max_retries + 1,
                    str(e)
                )

            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** attempt)
                logger.info("Retrying in {:.1f}s...", delay)
                time.sleep(delay)

        total_time = time.time() - start_time
        return LLMResponse(
            content="",
            response_time=total_time,
            success=False,
            error=last_error,
            used_structured_output=True
        )

    def _call_with_system_regular(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> LLMResponse:
        """Regular API call with system prompt (no structured output)."""
        last_error: Optional[str] = None
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            attempt_start = time.time()

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    timeout=self.timeout_seconds,
                )

                response_time = time.time() - attempt_start

                content = ""
                if response.choices and len(response.choices) > 0:
                    choice = response.choices[0]
                    if choice.message and choice.message.content:
                        content = choice.message.content

                logger.debug(
                    "LLM API call with system succeeded in {:.2f}s",
                    response_time
                )

                return LLMResponse(
                    content=content,
                    response_time=response_time,
                    success=True
                )

            except openai.APITimeoutError as e:
                last_error = f"API timeout: {str(e)}"

            except openai.APIConnectionError as e:
                last_error = f"API connection error: {str(e)}"

            except openai.APIError as e:
                last_error = f"API error: {str(e)}"

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"

            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** attempt)
                logger.info("Retrying in {:.1f}s...", delay)
                time.sleep(delay)

        total_time = time.time() - start_time
        return LLMResponse(
            content="",
            response_time=total_time,
            success=False,
            error=last_error
        )
