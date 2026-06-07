#!/bin/bash
# dswriter-web — 启动 DeepSeek Writer Web 界面
# 直接使用 Homebrew Python，完全避免 macOS/Xcode Python 冲突

PROJECT_DIR="$HOME/Desktop/deepseek_writer_new"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: 找不到项目目录 $PROJECT_DIR" >&2
    exit 1
fi

# 确定 Python
if [ -x /opt/homebrew/bin/python3.10 ]; then
    PYTHON=/opt/homebrew/bin/python3.10
elif [ -x /opt/homebrew/bin/python3.11 ]; then
    PYTHON=/opt/homebrew/bin/python3.11
elif [ -x /opt/homebrew/bin/python3 ]; then
    PYTHON=/opt/homebrew/bin/python3
else
    echo "ERROR: 找不到 Homebrew Python，请安装 python@3.10" >&2
    exit 1
fi

export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
echo "🌐 启动 Web 界面 → http://localhost:7860"
cd "$PROJECT_DIR"
exec "$PYTHON" "$PROJECT_DIR/webui.py"
