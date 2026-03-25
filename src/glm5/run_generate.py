"""GLM-5 批量生成 CLI 入口

使用 BatchGenerator 批量调用 GLM-5 API 生成 think 链和 solution。
支持断点续传、约束校验重试和实时进度显示。

运行方式:
    python -m src.glm5.run_generate --input outputs/glm5/sampled_5000.jsonl --output outputs/glm5/results.jsonl
"""

import argparse
import json

from src.glm5.client import GLM5Client
from src.glm5.generator import BatchGenerator

__all__ = ["main"]


def main():
    """批量生成主函数"""
    parser = argparse.ArgumentParser(
        description="GLM-5 批量生成 think 链和 solution"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="outputs/glm5/sampled_5000.jsonl",
        help="输入 jsonl 路径 (默认: outputs/glm5/sampled_5000.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/glm5/results.jsonl",
        help="输出结果路径 (默认: outputs/glm5/results.jsonl)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="约束违反重试次数 (默认: 3)",
    )
    args = parser.parse_args()

    # 加载输入数据
    samples = []
    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    print(f"[生成] 加载 {len(samples)} 条样本")

    # 创建客户端 (API key 从环境变量 GLM_API_KEY 读取)
    client = GLM5Client()

    # 创建编排器并执行
    generator = BatchGenerator(
        client=client,
        output_path=args.output,
        max_retries=args.max_retries,
    )

    try:
        stats = generator.generate(samples)
        print(f"[生成] 最终统计: {json.dumps(stats, ensure_ascii=False)}")
    finally:
        client.shutdown()


if __name__ == "__main__":
    main()
