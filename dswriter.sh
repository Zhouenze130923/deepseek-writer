#!/bin/bash
# dswriter — DeepSeek Writer CLI 快捷命令
# 安装: chmod +x /usr/local/bin/dswriter

PROJECT_DIR="$HOME/Desktop/deepseek_writer_new"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: 找不到 DeepSeek Writer 项目目录" >&2
    echo "请将项目放在 ~/Desktop/deepseek_writer_new/" >&2
    exit 1
fi

export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# 优先使用 Homebrew Python 3.10+
if [ -x /opt/homebrew/bin/python3.10 ]; then
    PYTHON=/opt/homebrew/bin/python3.10
elif [ -x /opt/homebrew/bin/python3.11 ]; then
    PYTHON=/opt/homebrew/bin/python3.11
else
    PYTHON=python3
fi

exec "$PYTHON" "$PROJECT_DIR/cli.py" "$@"
