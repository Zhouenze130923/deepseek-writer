from setuptools import setup

setup(
    name="deepseek-writer",
    version="1.0.0",
    description="AI 网文写作助手 — 多 Agent 协作，输入灵感即可自动成文",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Zhouenze",
    py_modules=["cli", "config", "orchestrator", "project", "templates"],
    packages=["agents", "prompts", "utils", "llm"],
    package_dir={
        "agents": "agents",
        "prompts": "prompts",
        "utils": "utils",
        "llm": "llm",
    },
    entry_points={
        "console_scripts": [
            "dswriter=cli:main",
        ],
    },
    python_requires=">=3.10",
    install_requires=[
        "rich>=13.0.0",
        "openai>=1.50.0",
        "anthropic>=0.40.0",
        "gradio>=5.0.0",
        "ebooklib>=0.18",
        "fpdf2>=2.7.0",
        "python-docx>=1.1.0",
        "markdown>=3.5.0",
        "edge-tts>=7.0",  # 免费 TTS，用于有声书导出
    ],
)
