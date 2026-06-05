# -*- coding: utf-8 -*-
"""统一日志配置 — 所有模块通过 get_logger(__name__) 获取 logger

使用方式：
    from src.app.utils.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("...")
    logger.warning("...")
    logger.error("...")

日志级别：
    DEBUG   — 详细调试信息（开发用）
    INFO    — 关键流程节点
    WARNING — 可恢复的异常（配置缺失、回退等）
    ERROR   — 错误但不影响运行
"""
import logging
import os
import sys
from pathlib import Path


def _get_log_level() -> int:
    """根据环境确定日志级别：打包后 INFO，开发 DEBUG"""
    if getattr(sys, 'frozen', False):
        return logging.INFO
    env_level = os.environ.get("BEE_LOG_LEVEL", "DEBUG").upper()
    return getattr(logging, env_level, logging.DEBUG)


def _get_log_dir() -> str:
    """获取日志目录"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
    log_dir = os.path.join(base, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


_log_initialized = False


def setup_root_logger() -> str:
    """初始化根日志器（仅在 main.py 入口调用一次），返回日志文件路径"""
    global _log_initialized
    if _log_initialized:
        return ""

    level = _get_log_level()
    log_dir = _get_log_dir()
    log_path = os.path.join(log_dir, "bee.log")

    root = logging.getLogger()
    root.setLevel(level)

    # 清除已有 handler（避免重复）
    for h in root.handlers[:]:
        root.removeHandler(h)

    # ── 文件 handler（完整日志） ──
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)

    # ── 控制台 handler（仅 WARNING+，开发模式显示 INFO+） ──
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO if level == logging.DEBUG else logging.WARNING)
    sh.setFormatter(logging.Formatter(
        "[%(levelname)-7s] %(name)s: %(message)s",
    ))
    root.addHandler(sh)

    _log_initialized = True
    root.info("日志系统已初始化: level=%s path=%s", logging.getLevelName(level), log_path)
    return log_path


def get_logger(name: str) -> logging.Logger:
    """获取模块级 logger"""
    return logging.getLogger(name)
