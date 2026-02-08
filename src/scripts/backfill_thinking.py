#!/usr/bin/env python3
"""
GLM-4.7 API Thinking Backfill Script

为 SFT 训练数据生成真实的 thinking 推理内容，替换空占位符。
使用 GLM-4.7 API 为每个样本生成交通信号配时分析思考过程。

使用 urllib（标准库）而非 requests。

用法:
    python -m src.scripts.backfill_thinking --dry-run           # 测试 3 条
    python -m src.scripts.backfill_thinking --max-samples 100   # 处理 100 条
    python -m src.scripts.backfill_thinking                     # 全量处理
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

# GLM-4.7 API 配置
API_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_API_KEY = "d8318666ab424416b427231b9d503f75.NYYiQKROscMtungx"
MODEL_NAME = "glm-4.7"

# 默认路径
DEFAULT_INPUT = "outputs/sft/train.jsonl"
DEFAULT_OUTPUT = "outputs/sft/train_with_thinking.jsonl"
PROGRESS_FILE = "outputs/sft/.backfill_progress.json"

# 速率控制 (秒)
REQUEST_INTERVAL = 1.5  # 每次请求后等待


def call_glm_api(
    user_content: str,
    json_answer: str,
    api_key: str,
    max_retries: int = 5
) -> Optional[str]:
    """
    调用 GLM-4.7 API 生成 thinking 内容。

    Returns:
        生成的 thinking 文本，失败返回 None
    """
    prompt = f"""以下是一个交通信号配时任务的输入和已知正确答案。
请生成简短的分析思考过程（3-5句话），说明如何根据各相位的饱和度(pred_saturation)、min_green、max_green 得出该答案。
只输出思考过程文本，不要输出 <think> 标签，不要输出 JSON。

【输入数据】
{user_content}

【正确答案】
{json_answer}"""

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
        "max_tokens": 500
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for attempt in range(max_retries):
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                API_ENDPOINT,
                data=data,
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))

                if 'choices' in result and len(result['choices']) > 0:
                    message = result['choices'][0]['message']
                    # GLM-4.7 是推理模型，thinking 在 reasoning_content 字段
                    # content 字段可能为空，优先读取 reasoning_content
                    thinking = (
                        message.get('reasoning_content', '') or
                        message.get('content', '')
                    ).strip()
                    return thinking if thinking else None
                else:
                    print(f"  Warning: Unexpected API response: {result}")
                    return None

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else "No error body"
            if e.code == 429:
                # 速率限制：用更长的退避
                backoff = 10 * (2 ** attempt)  # 10s, 20s, 40s, 80s, 160s
                print(f"  Rate limited (attempt {attempt + 1}/{max_retries}), waiting {backoff}s...")
                time.sleep(backoff)
            else:
                print(f"  HTTP {e.code} (attempt {attempt + 1}/{max_retries}): {error_body[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        except (urllib.error.URLError, TimeoutError) as e:
            reason = str(e.reason) if hasattr(e, 'reason') else str(e)
            print(f"  Network error (attempt {attempt + 1}/{max_retries}): {reason}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))

        except Exception as e:
            print(f"  Error (attempt {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


def extract_thinking_and_answer(assistant_content: str) -> tuple[str, str]:
    """从 assistant content 中分离 thinking 和 JSON 答案。"""
    think_end = assistant_content.find("</think>")
    if think_end == -1:
        return "", assistant_content.strip()

    think_start = assistant_content.find("<think>")
    if think_start != -1:
        current_thinking = assistant_content[think_start + 7:think_end].strip()
    else:
        current_thinking = ""

    json_answer = assistant_content[think_end + 8:].strip()
    return current_thinking, json_answer


def load_progress(progress_file: str) -> dict:
    """加载进度：{index: thinking_text}"""
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {}


def save_progress(progress_file: str, results: dict):
    """保存进度"""
    os.makedirs(os.path.dirname(progress_file), exist_ok=True)
    with open(progress_file, 'w') as f:
        json.dump(results, f, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill thinking content for SFT training data using GLM-4.7 API"
    )
    parser.add_argument('--input', default=DEFAULT_INPUT)
    parser.add_argument('--output', default=DEFAULT_OUTPUT)
    parser.add_argument('--max-samples', type=int)
    parser.add_argument('--dry-run', action='store_true',
                        help="Process first 3 samples and print results")
    parser.add_argument('--api-key',
                        default=os.environ.get('GLM_API_KEY', DEFAULT_API_KEY))

    args = parser.parse_args()

    # 读取输入
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    print(f"Loading data from {input_path}...")
    with open(input_path, 'r') as f:
        records = [json.loads(line) for line in f if line.strip()]

    total_samples = len(records)
    print(f"Total samples: {total_samples}")

    # Dry-run
    if args.dry_run:
        print("\n=== DRY RUN MODE ===")
        for idx in range(min(3, total_samples)):
            messages = records[idx]['messages']
            user_content = messages[1]['content']
            assistant_content = messages[2]['content']
            _, json_answer = extract_thinking_and_answer(assistant_content)

            print(f"\n--- Sample {idx} ---")
            print(f"Input (first 200 chars): {user_content[:200]}...")
            print(f"JSON answer: {json_answer}")

            thinking = call_glm_api(user_content, json_answer, args.api_key)
            if thinking:
                print(f"Generated thinking:\n{thinking}")
            else:
                print("FAILED to generate thinking")
            time.sleep(REQUEST_INTERVAL)

        print("\n=== DRY RUN COMPLETE ===")
        return 0

    # 加载已有进度 (key: str(index), value: thinking_text)
    progress = load_progress(PROGRESS_FILE)
    print(f"Found {len(progress)} already completed samples")

    # 确定处理范围
    samples_to_process = min(args.max_samples, total_samples) if args.max_samples else total_samples

    # 顺序处理
    print(f"\nProcessing {samples_to_process} samples (single-threaded, {REQUEST_INTERVAL}s interval)...")
    start_time = time.time()
    success_count = 0
    skip_count = 0
    error_count = 0

    for idx in range(samples_to_process):
        str_idx = str(idx)

        # 跳过已完成的
        if str_idx in progress:
            skip_count += 1
            continue

        messages = records[idx]['messages']
        user_content = messages[1]['content']
        assistant_content = messages[2]['content']
        current_thinking, json_answer = extract_thinking_and_answer(assistant_content)

        # 已有非空 thinking
        if current_thinking:
            progress[str_idx] = current_thinking
            skip_count += 1
            continue

        # 调用 API
        thinking = call_glm_api(user_content, json_answer, args.api_key)

        if thinking:
            progress[str_idx] = thinking
            success_count += 1
        else:
            error_count += 1
            # 记录为空，后续重跑可以重试
            print(f"  [FAIL] Sample {idx}")

        # 进度汇报
        done = success_count + skip_count
        if success_count > 0 and success_count % 50 == 0:
            elapsed = time.time() - start_time
            rate = success_count / elapsed if elapsed > 0 else 0
            remaining = samples_to_process - done - error_count
            eta = remaining / rate / 60 if rate > 0 else 0
            print(f"  [{done}/{samples_to_process}] {done/samples_to_process*100:.1f}% | "
                  f"{rate:.2f} samples/s | ETA: {eta:.0f} min | errors: {error_count}")

        # 定期保存进度
        if success_count % 100 == 0 and success_count > 0:
            save_progress(PROGRESS_FILE, progress)

        # 速率控制
        time.sleep(REQUEST_INTERVAL)

    # 保存最终进度
    save_progress(PROGRESS_FILE, progress)

    # 写入最终输出文件（按原始顺序）
    print(f"\nWriting output file...")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with open(output_path, 'w') as outfile:
        for idx in range(samples_to_process):
            record = records[idx]
            str_idx = str(idx)

            if str_idx in progress and progress[str_idx]:
                # 有 thinking，替换
                messages = record['messages']
                _, json_answer = extract_thinking_and_answer(messages[2]['content'])
                new_content = f"<think>\n{progress[str_idx]}\n</think>\n{json_answer}"
                record = {
                    "messages": [
                        messages[0],
                        messages[1],
                        {"role": "assistant", "content": new_content}
                    ]
                }

            outfile.write(json.dumps(record, ensure_ascii=False) + '\n')
            written += 1

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"BACKFILL COMPLETE")
    print(f"{'='*60}")
    print(f"Total: {samples_to_process}")
    print(f"New thinking generated: {success_count}")
    print(f"Previously completed: {skip_count}")
    print(f"Errors: {error_count}")
    print(f"Written to: {output_path} ({written} lines)")
    print(f"Time: {elapsed/60:.1f} minutes")

    if error_count > 0:
        print(f"\n Re-run to retry {error_count} failed samples.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
