"""轻量日志工具。供 CLI 和非交互式场景使用，不依赖 Rich。"""

from __future__ import annotations
import sys
import os
from datetime import datetime


_LOG_LEVEL = os.environ.get("DEEPSEEK_WRITER_LOG", "INFO").upper()
_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


def _should_log(level: str) -> bool:
    return _LEVELS.get(level, 20) >= _LEVELS.get(_LOG_LEVEL, 20)


def debug(msg: str):
    if _should_log("DEBUG"):
        _write("DEBUG", msg)


def info(msg: str):
    if _should_log("INFO"):
        _write("INFO", msg)


def warn(msg: str):
    if _should_log("WARN"):
        _write("WARN", msg)


def error(msg: str):
    if _should_log("ERROR"):
        _write("ERROR", msg)


def _write(level: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{level}] {msg}", file=sys.stderr, flush=True)
