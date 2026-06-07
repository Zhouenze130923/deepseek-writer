DEEPSEEK_MODELS = {
    "deepseek-v4-flash": {"max_tokens": 32768, "description": "DeepSeek V4 Flash - 快速响应"},
    "deepseek-v4-pro": {"max_tokens": 32768, "description": "DeepSeek V4 Pro - 增强推理"},
}

CLAUDE_MODELS = {
    "claude-sonnet-4-6": {"max_tokens": 8192, "description": "Claude Sonnet 4.6 - 平衡速度与质量"},
    "claude-opus-4-7": {"max_tokens": 8192, "description": "Claude Opus 4.7 - 最高质量"},
    "claude-haiku-4-5-20251001": {"max_tokens": 8192, "description": "Claude Haiku 4.5 - 最快速度"},
}

PROVIDERS = {
    "deepseek": {"models": DEEPSEEK_MODELS, "label": "DeepSeek"},
    "claude": {"models": CLAUDE_MODELS, "label": "Claude (Anthropic)"},
}
