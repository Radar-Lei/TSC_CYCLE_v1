"""批量生成编排器

使用 GLM-5 API 批量生成 think 链和 solution，
支持约束校验重试、断点续传和实时进度显示。

主要功能:
- BatchGenerator: 批量生成编排器
- 断点续传: 启动时自动跳过已完成条目
- 约束校验重试: 违反约束时丢弃重试 (最多 3 次)
- 逐条追加写入: 每条结果立即写入 results.jsonl
- 实时进度: 终端显示完成数/总数、成功率、平均 think 长度
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.glm5.client import GLM5Client
from src.glm5.prompt import build_glm5_prompts
from src.glm5.validator import parse_glm5_output, validate_constraints

__all__ = ["BatchGenerator"]


def _sample_id(sample: dict) -> str:
    """从 sample 生成唯一 ID，用于断点续传

    Args:
        sample: train.jsonl 中的一行数据

    Returns:
        格式为 "tl_id:as_of" 的唯一标识
    """
    tl_id = sample["metadata"]["tl_id"]
    as_of = sample["prediction"]["as_of"]
    return f"{tl_id}:{as_of}"


class BatchGenerator:
    """批量生成编排器

    调用 GLM-5 API 为每条样本生成 think 链和 solution，
    包含约束校验重试、断点续传和实时进度显示。

    Attributes:
        client: GLM5Client 实例
        output_path: 输出文件路径 (逐条追加写入)
        max_retries: 约束违反时最大重试次数

    Example:
        >>> client = GLM5Client()
        >>> gen = BatchGenerator(client=client, output_path="outputs/glm5/results.jsonl")
        >>> stats = gen.generate(samples)
    """

    def __init__(
        self,
        client: GLM5Client,
        output_path: str = "outputs/glm5/results.jsonl",
        max_retries: int = 3,
    ):
        """初始化批量生成编排器

        Args:
            client: GLM5Client 实例 (外部创建，依赖注入)
            output_path: 输出 jsonl 文件路径
            max_retries: 约束违反时的重试次数 (默认 3)
        """
        self.client = client
        self.output_path = output_path
        self.max_retries = max_retries
        self._completed_ids: set = set()
        self._stats = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "total_think_len": 0,
        }
        self._write_lock = threading.Lock()

    def _load_completed(self):
        """启动时读取已有结果，收集已完成 ID 用于断点续传"""
        if not os.path.exists(self.output_path):
            return
        with open(self.output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        self._completed_ids.add(record["id"])
                        # 恢复统计
                        if record["status"] == "success":
                            self._stats["success"] += 1
                            self._stats["total_think_len"] += record.get(
                                "think_length", 0
                            )
                        else:
                            self._stats["failed"] += 1
                    except (json.JSONDecodeError, KeyError):
                        continue
        if self._completed_ids:
            print(
                f"[生成] 断点续传: 已完成 {len(self._completed_ids)} 条，跳过"
            )

    def _process_one(self, sample: dict) -> dict:
        """处理单条样本: 调用 GLM-5 -> 解析 -> 校验 -> 重试

        Args:
            sample: train.jsonl 中的一行数据

        Returns:
            结果字典，包含 id, status, think_text, solution 等字段
        """
        sample_id = _sample_id(sample)
        system_prompt, user_prompt = build_glm5_prompts(sample)
        phase_waits = sample["prediction"]["phase_waits"]

        last_error = ""
        for attempt in range(self.max_retries):
            response = self.client.call_single(system_prompt, user_prompt)
            if not response.success:
                # API 错误 (client 已重试过)，直接标记失败
                return {
                    "id": sample_id,
                    "status": "api_error",
                    "error": response.error,
                    "retries": attempt,
                    "response_time": response.response_time,
                    "sample": sample,
                }

            parsed = parse_glm5_output(response.content)
            if not parsed.success:
                last_error = parsed.error
                continue  # 解析失败，重试

            valid, reason = validate_constraints(parsed.solution, phase_waits)
            if valid:
                return {
                    "id": sample_id,
                    "status": "success",
                    "think_text": parsed.think_text,
                    "solution": parsed.solution,
                    "think_length": parsed.think_length,
                    "response_time": response.response_time,
                    "retries": attempt,
                    "sample": sample,
                }

            # 约束违反，记录原因并重试
            last_error = reason

        # max_retries 次均失败
        print(
            f"[生成] 跳过 {sample_id}: {self.max_retries} 次均失败 - {last_error}"
        )
        return {
            "id": sample_id,
            "status": "constraint_failed",
            "error": last_error,
            "retries": self.max_retries,
            "sample": sample,
        }

    def _print_progress(self, current: int, total: int):
        """终端单行刷新进度

        Args:
            current: 当前已处理条数
            total: 总条数
        """
        pct = current / total * 100 if total > 0 else 0
        success = self._stats["success"]
        failed = self._stats["failed"]
        total_done = success + failed
        success_rate = (success / total_done * 100) if total_done > 0 else 0
        avg_think = (
            (self._stats["total_think_len"] / success) if success > 0 else 0
        )
        print(
            f"\r[生成] {current}/{total} ({pct:.1f}%) | "
            f"成功率: {success_rate:.1f}% | "
            f"平均think: {avg_think:.0f} chars",
            end="",
            flush=True,
        )

    def _append_result(self, result: dict):
        """线程安全地追加写入一条结果到 output_path

        Args:
            result: 结果字典
        """
        with self._write_lock:
            with open(self.output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()

    def generate(self, samples: list) -> dict:
        """执行批量生成

        Args:
            samples: train.jsonl 样本列表

        Returns:
            统计字典: {"success": N, "failed": N, "skipped": N, "total": N}
        """
        # 断点续传: 加载已完成 ID
        self._load_completed()

        # 创建输出目录
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        # 过滤已完成样本
        pending = []
        for sample in samples:
            sid = _sample_id(sample)
            if sid in self._completed_ids:
                self._stats["skipped"] += 1
            else:
                pending.append(sample)

        total = len(pending) + len(self._completed_ids)
        if self._stats["skipped"] > 0:
            print(
                f"[生成] 跳过 {self._stats['skipped']} 条已完成，"
                f"剩余 {len(pending)} 条待处理"
            )

        print(f"[生成] 开始批量生成: {len(pending)} 条待处理，共 {total} 条")

        # 并发处理
        processed = len(self._completed_ids)
        with ThreadPoolExecutor(
            max_workers=self.client.max_concurrent
        ) as executor:
            futures = {
                executor.submit(self._process_one, sample): sample
                for sample in pending
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as e:
                    sample = futures[future]
                    result = {
                        "id": _sample_id(sample),
                        "status": "exception",
                        "error": str(e),
                        "retries": 0,
                        "sample": sample,
                    }

                # 逐条追加写入
                self._append_result(result)

                # 更新统计
                if result["status"] == "success":
                    self._stats["success"] += 1
                    self._stats["total_think_len"] += result.get(
                        "think_length", 0
                    )
                else:
                    self._stats["failed"] += 1

                processed += 1
                self._print_progress(processed, total)

        # 最终统计
        print()  # 换行
        print(
            f"[生成] 完成! "
            f"成功: {self._stats['success']}, "
            f"失败: {self._stats['failed']}, "
            f"跳过: {self._stats['skipped']}, "
            f"总计: {total}"
        )

        return {
            "success": self._stats["success"],
            "failed": self._stats["failed"],
            "skipped": self._stats["skipped"],
            "total": total,
        }
