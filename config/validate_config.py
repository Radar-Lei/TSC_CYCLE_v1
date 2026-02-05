#!/usr/bin/env python3
"""配置验证脚本

提供配置文件的加载、验证和查询功能。
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def validate_config(config_path: str) -> bool:
    """验证配置文件是否符合 schema 规范

    Args:
        config_path: 配置文件路径

    Returns:
        bool: 验证是否通过
    """
    try:
        # 尝试导入 jsonschema
        try:
            import jsonschema
            has_jsonschema = True
        except ImportError:
            has_jsonschema = False
            print("[WARNING] jsonschema 未安装,仅检查 JSON 格式", file=sys.stderr)

        # 加载配置文件
        config_file = Path(config_path)
        if not config_file.exists():
            print(f"[ERROR] 配置文件不存在: {config_path}", file=sys.stderr)
            return False

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 如果有 jsonschema,使用 schema 验证
        if has_jsonschema:
            schema_file = Path(__file__).parent / 'schema.json'
            if not schema_file.exists():
                print(f"[ERROR] Schema 文件不存在: {schema_file}", file=sys.stderr)
                return False

            with open(schema_file, 'r', encoding='utf-8') as f:
                schema = json.load(f)

            try:
                jsonschema.validate(instance=config, schema=schema)
                print(f"[SUCCESS] 配置文件验证通过: {config_path}")
                return True
            except jsonschema.ValidationError as e:
                print(f"[ERROR] 配置验证失败: {e.message}", file=sys.stderr)
                print(f"  路径: {'.'.join(str(p) for p in e.path)}", file=sys.stderr)
                print(f"  Schema 路径: {'.'.join(str(p) for p in e.schema_path)}", file=sys.stderr)
                return False
        else:
            # Fallback: 仅检查必需字段存在
            required_sections = ['training', 'simulation', 'rewards', 'paths']
            for section in required_sections:
                if section not in config:
                    print(f"[ERROR] 缺少必需配置节: {section}", file=sys.stderr)
                    return False

            # 检查 training 子节
            if 'sft' not in config['training'] or 'grpo' not in config['training']:
                print("[ERROR] training 配置缺少 sft 或 grpo", file=sys.stderr)
                return False

            print(f"[SUCCESS] 配置文件格式检查通过 (未使用 schema): {config_path}")
            return True

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] 验证失败: {e}", file=sys.stderr)
        return False


def load_config(config_path: str) -> Dict[str, Any]:
    """加载并验证配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        dict: 配置字典

    Raises:
        ValueError: 如果配置验证失败
        FileNotFoundError: 如果配置文件不存在
    """
    if not validate_config(config_path):
        raise ValueError(f"配置文件验证失败: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """获取嵌套配置值

    使用点号分隔的键路径访问嵌套字典。

    Args:
        config: 配置字典
        key: 键路径,如 "training.sft.max_steps"
        default: 默认值,键不存在时返回

    Returns:
        配置值或默认值

    Examples:
        >>> config = {"training": {"sft": {"max_steps": 300}}}
        >>> get_config_value(config, "training.sft.max_steps")
        300
        >>> get_config_value(config, "training.nonexistent", default=100)
        100
    """
    keys = key.split('.')
    value = config

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default

    return value


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='验证配置文件')
    parser.add_argument('config_path', nargs='?', default='config/config.json',
                        help='配置文件路径 (默认: config/config.json)')
    parser.add_argument('--verbose', action='store_true',
                        help='显示详细信息')

    args = parser.parse_args()

    success = validate_config(args.config_path)

    if args.verbose and success:
        config = load_config(args.config_path)
        print("\n配置内容:")
        print(json.dumps(config, indent=2, ensure_ascii=False))

    sys.exit(0 if success else 1)
