#!/usr/bin/env python3
"""
相位处理 CLI 脚本

处理 SUMO 网络文件,输出相位配置 JSON 文件
"""

import argparse
import os
import sys
from pathlib import Path

# 确保可以导入 src 模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.phase_processor.processor import process_traffic_lights, save_result_to_json
from src.utils.logging_config import setup_logging


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        description="处理 SUMO 网络文件,生成相位配置 JSON",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="输入的 SUMO 网络文件路径 (.net.xml)"
    )

    parser.add_argument(
        "-o", "--output",
        default="phase_config.json",
        help="输出的 JSON 文件路径"
    )

    parser.add_argument(
        "--log-file",
        default="phase_processing.log",
        help="日志文件路径"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="启用详细日志 (DEBUG 级别)"
    )

    args = parser.parse_args()

    # 验证输入文件存在
    if not os.path.exists(args.input):
        print(f"错误: 输入文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    # 创建输出目录 (如果不存在)
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 设置日志
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = setup_logging(log_file=args.log_file, level=log_level)

    # 执行处理流程
    logger.info(f"输入文件: {args.input}")
    logger.info(f"输出文件: {args.output}")

    try:
        result = process_traffic_lights(args.input, logger)

        # 保存结果
        source_file = os.path.basename(args.input)
        save_result_to_json(result, args.output, source_file)

        # 输出处理摘要到 console
        print("\n" + "=" * 60)
        print("相位处理完成")
        print("=" * 60)
        print(f"输入文件: {args.input}")
        print(f"输出文件: {args.output}")
        print(f"\n统计:")
        print(f"  总信号灯数: {result.total_tl}")
        print(f"  有效信号灯数: {result.valid_tl}")
        print(f"  跳过信号灯数: {result.skipped_tl}")
        print(f"  总相位数: {result.total_phases}")
        print(f"  过滤的无效相位数: {result.filtered_phases}")
        print(f"  冲突解决次数: {result.conflict_resolutions}")
        print("=" * 60)
        print(f"\n详细日志: {args.log_file}")

        return 0

    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        print(f"\n错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
