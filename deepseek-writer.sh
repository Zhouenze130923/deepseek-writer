#!/bin/bash
# DeepSeek Writer CLI — 供任意 Agent 调用的命令行接口
# 安装: chmod +x /usr/local/bin/deepseek-writer

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../Desktop/deepseek_writer_new" 2>/dev/null && pwd)"
FALLBACK_DIR="$HOME/Desktop/deepseek_writer_new"
TARGET="${PROJECT_DIR:-$FALLBACK_DIR}"

if [ ! -d "$TARGET" ]; then
    echo "ERROR: 找不到 DeepSeek Writer 项目目录" >&2
    echo "请将项目放在 ~/Desktop/deepseek_writer_new/" >&2
    exit 1
fi

export PYTHONPATH="$TARGET:$PYTHONPATH"
exec python3 "$TARGET/cli.py" "$@"
