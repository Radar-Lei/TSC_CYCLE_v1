#!/usr/bin/env python3
"""
GLM-4.7 API Thinking Backfill Script

为 SFT 训练数据生成真实的 thinking 推理内容，替换空占位符。
使用 GLM-4.7 API 为每个样本生成交通信号配时分析思考过程。

注意：使用 urllib（标准库）而非 requests，因为系统 Python 3.14 未安装 requests。
"""

import json
import os
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional
import urllib.request
import urllib.error
import urllib.parse

# GLM-4.7 API 配置
API_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_API_KEY = "d8318666ab424416b427231b9d503f75.NYYiQKROscMtungx"
MODEL_NAME = "glm-4.7"

# 默认路径
DEFAULT_INPUT = "outputs/sft/train.jsonl"
DEFAULT_OUTPUT = "outputs/sft/train_with_thinking.jsonl"
PROGRESS_FILE = "outputs/sft/.backfill_progress.json"


def call_glm_api(
    user_content: str,
    json_answer: str,
    api_key: str,
    max_retries: int = 3
) -> Optional[str]:
    """
    调用 GLM-4.7 API 生成 thinking 内容。

    Args:
        user_content: 原始用户输入（交通信号数据）
        json_answer: 已知的正确答案（JSON 数组）
        api_key: GLM API key
        max_retries: 最大重试次数

    Returns:
        生成的 thinking 文本，失败返回 None
    """
    # 构造 prompt
    prompt = f"""以下是一个交通信号配时任务的输入和已知正确答案。
请生成简短的分析思考过程（3-5句话），说明如何根据各相位的饱和度(pred_saturation)、min_green、max_green 得出该答案。
只输出思考过程文本，不要输出 <think> 标签，不要输出 JSON。

【输入数据】
{user_content}

【正确答案】
{json_answer}"""

    # 构造请求体
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "你是交通信号配时优化专家。请根据输入数据和已知的最终配时结果，生成简短的分析思考过程。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 300
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 重试机制
    for attempt in range(max_retries):
        try:
            # 构造请求
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                API_ENDPOINT,
                data=data,
                headers=headers,
                method='POST'
            )

            # 发送请求
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

                # DEBUG: 在第一次调用时打印完整响应
                if attempt == 0 and os.environ.get('DEBUG_API'):
                    print(f"[DEBUG] API Response: {json.dumps(result, ensure_ascii=False, indent=2)}")

                # 提取 thinking 内容
                if 'choices' in result and len(result['choices']) > 0:
                    message = result['choices'][0]['message']
                    # GLM-4.7 使用 reasoning_content 字段存储推理内容
                    thinking = message.get('reasoning_content', message.get('content', '')).strip()
                    return thinking if thinking else None
                else:
                    print(f"Warning: Unexpected API response format: {result}")
                    return None

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else "No error body"
            print(f"Attempt {attempt + 1}/{max_retries} failed: HTTP {e.code} - {error_body}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避

        except urllib.error.URLError as e:
            print(f"Attempt {attempt + 1}/{max_retries} failed: Network error - {e.reason}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        except Exception as e:
            print(f"Attempt {attempt + 1}/{max_retries} failed: {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


def extract_thinking_and_answer(assistant_content: str) -> Tuple[str, str]:
    """
    从 assistant content 中分离 thinking 和 JSON 答案。

    Returns:
        (current_thinking, json_answer)
    """
    # 查找 </think> 标签
    think_end = assistant_content.find("</think>")
    if think_end == -1:
        # 如果没有 thinking 标签，整个内容视为答案
        return "", assistant_content.strip()

    # 提取 thinking（在 <think> 和 </think> 之间）
    think_start = assistant_content.find("<think>")
    if think_start != -1:
        current_thinking = assistant_content[think_start + 7:think_end].strip()
    else:
        current_thinking = ""

    # 提取 JSON 答案（</think> 之后）
    json_answer = assistant_content[think_end + 8:].strip()

    return current_thinking, json_answer


def process_single_sample(
    idx: int,
    record: Dict,
    api_key: str,
    dry_run: bool = False
) -> Tuple[int, Optional[Dict], Optional[str]]:
    """
    处理单个样本，生成 thinking 并更新记录。

    Args:
        idx: 样本索引
        record: SFT JSONL 记录
        api_key: GLM API key
        dry_run: 是否为 dry-run 模式

    Returns:
        (idx, updated_record, error_message)
    """
    try:
        # 提取消息
        messages = record['messages']
        user_content = messages[1]['content']  # index 1 是 user message
        assistant_content = messages[2]['content']  # index 2 是 assistant message

        # 分离 thinking 和 JSON 答案
        current_thinking, json_answer = extract_thinking_and_answer(assistant_content)

        # 如果已有非空 thinking，跳过
        if current_thinking and current_thinking.strip():
            if dry_run:
                print(f"Sample {idx} already has thinking, skipping.")
            return idx, record, None

        # 调用 GLM API 生成 thinking
        new_thinking = call_glm_api(user_content, json_answer, api_key)

        if new_thinking is None:
            error_msg = f"Failed to generate thinking for sample {idx}"
            return idx, None, error_msg

        # 重新组装 assistant content
        new_assistant_content = f"<think>\n{new_thinking}\n</think>\n{json_answer}"

        # 更新记录
        updated_record = record.copy()
        updated_record['messages'] = [
            messages[0],  # system
            messages[1],  # user
            {
                "role": "assistant",
                "content": new_assistant_content
            }
        ]

        if dry_run:
            print(f"\n=== Sample {idx} ===")
            print(f"User input (first 200 chars): {user_content[:200]}...")
            print(f"JSON answer: {json_answer}")
            print(f"Generated thinking:\n{new_thinking}\n")

        return idx, updated_record, None

    except Exception as e:
        error_msg = f"Error processing sample {idx}: {type(e).__name__} - {e}"
        return idx, None, error_msg


def load_progress(progress_file: str) -> set:
    """加载已完成的样本索引集合"""
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            data = json.load(f)
            return set(data.get('completed_indices', []))
    return set()


def save_progress(progress_file: str, completed_indices: set):
    """保存进度"""
    with open(progress_file, 'w') as f:
        json.dump({'completed_indices': sorted(list(completed_indices))}, f)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill thinking content for SFT training data using GLM-4.7 API"
    )
    parser.add_argument(
        '--input',
        default=DEFAULT_INPUT,
        help=f"Input SFT JSONL file (default: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        '--output',
        default=DEFAULT_OUTPUT,
        help=f"Output JSONL file (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=5,
        help="Number of concurrent threads (default: 5)"
    )
    parser.add_argument(
        '--max-samples',
        type=int,
        help="Maximum number of samples to process (for testing)"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Process only first 3 samples and print results without writing file"
    )
    parser.add_argument(
        '--api-key',
        default=os.environ.get('GLM_API_KEY', DEFAULT_API_KEY),
        help="GLM API key (default: env GLM_API_KEY or hardcoded key)"
    )

    args = parser.parse_args()

    # 读取输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    print(f"Loading data from {input_path}...")
    with open(input_path, 'r') as f:
        records = [json.loads(line) for line in f]

    total_samples = len(records)
    print(f"Total samples: {total_samples}")

    # Dry-run 模式
    if args.dry_run:
        print("\n=== DRY RUN MODE ===")
        print("Processing first 3 samples...\n")
        for idx in range(min(3, total_samples)):
            _, updated_record, error = process_single_sample(
                idx, records[idx], args.api_key, dry_run=True
            )
            if error:
                print(f"Error: {error}")
            time.sleep(0.1)  # 速率控制
        print("\n=== DRY RUN COMPLETE ===")
        return 0

    # 加载进度
    completed_indices = load_progress(PROGRESS_FILE)
    print(f"Found {len(completed_indices)} already completed samples")

    # 确定要处理的样本
    if args.max_samples:
        samples_to_process = min(args.max_samples, total_samples)
    else:
        samples_to_process = total_samples

    # 准备输出文件（追加模式支持断点续跑）
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 如果是新开始，清空输出文件
    if not completed_indices:
        if output_path.exists():
            output_path.unlink()

    # 并发处理
    print(f"\nProcessing {samples_to_process} samples with {args.concurrency} threads...")
    start_time = time.time()

    success_count = 0
    error_count = 0
    skipped_count = len(completed_indices)
    errors = []

    # 打开输出文件（追加模式）
    with open(output_path, 'a') as outfile:
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            # 提交任务（跳过已完成的）
            futures = {}
            for idx in range(samples_to_process):
                if idx in completed_indices:
                    continue
                future = executor.submit(
                    process_single_sample,
                    idx,
                    records[idx],
                    args.api_key,
                    dry_run=False
                )
                futures[future] = idx
                time.sleep(0.02)  # 速率控制：每个线程启动间隔

            # 处理结果
            for future in as_completed(futures):
                idx, updated_record, error = future.result()

                if error:
                    error_count += 1
                    errors.append(error)
                    print(f"[ERROR] {error}")
                elif updated_record:
                    # 写入结果
                    outfile.write(json.dumps(updated_record, ensure_ascii=False) + '\n')
                    outfile.flush()

                    # 更新进度
                    completed_indices.add(idx)
                    success_count += 1

                    # 每 100 条保存一次进度
                    if success_count % 100 == 0:
                        save_progress(PROGRESS_FILE, completed_indices)
                        elapsed = time.time() - start_time
                        rate = success_count / elapsed
                        remaining = samples_to_process - success_count - skipped_count
                        eta = remaining / rate if rate > 0 else 0
                        progress_pct = (success_count + skipped_count) / samples_to_process * 100
                        print(f"Progress: {success_count + skipped_count}/{samples_to_process} "
                              f"({progress_pct:.1f}%) | "
                              f"Rate: {rate:.1f} samples/sec | "
                              f"ETA: {eta/60:.1f} min")

                time.sleep(0.1)  # 速率控制

    # 最终保存进度
    save_progress(PROGRESS_FILE, completed_indices)

    elapsed = time.time() - start_time
    print(f"\n=== COMPLETE ===")
    print(f"Total processed: {success_count}")
    print(f"Skipped (already done): {skipped_count}")
    print(f"Errors: {error_count}")
    print(f"Time elapsed: {elapsed/60:.1f} minutes")

    if errors:
        print(f"\nErrors encountered:")
        for error in errors[:10]:  # 只显示前 10 个错误
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    if success_count + skipped_count == samples_to_process and error_count == 0:
        print(f"\n✓ All samples processed successfully!")
        print(f"Output written to: {output_path}")
    else:
        print(f"\n⚠ Some samples failed. You can re-run to retry failed samples.")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
