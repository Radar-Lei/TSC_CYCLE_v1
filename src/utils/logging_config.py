"""日志配置模块"""
import logging
import sys


def setup_logging(log_file: str = "phase_processing.log", level: int = logging.INFO) -> logging.Logger:
    """配置日志系统

    Args:
        log_file: 日志文件路径
        level: 日志级别

    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger("phase_processor")
    logger.setLevel(level)

    # 移除已有的处理器,避免重复添加
    logger.handlers.clear()

    # 格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console 处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
