import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict

CONFIG_DIR = Path.home() / ".deepseek_writer"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    provider: str = "deepseek"  # "deepseek" or "claude"
    model: str = "deepseek-v4-flash"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    temperature: float = 0.8
    max_tokens: int = 8192
    top_p: float = 0.95

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()

    @property
    def api_key(self) -> str:
        if self.provider == "deepseek":
            return self.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        return self.claude_api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def active_model(self) -> str:
        if self.provider == "deepseek":
            return self.model
        return self.claude_model

    def validate(self) -> list[str]:
        """校验配置，返回所有问题列表。空列表表示配置正常。"""
        issues = []
        if self.provider not in ("deepseek", "claude"):
            issues.append(f"不支持的 provider: {self.provider}（应为 deepseek 或 claude）")
        if not self.api_key:
            issues.append("未配置 API Key（设置环境变量或通过 /config 配置）")
        if self.provider == "deepseek":
            if not self.model:
                issues.append("DeepSeek 模型名为空")
            if not self.deepseek_base_url:
                issues.append("DeepSeek API 地址为空")
        else:
            if not self.claude_model:
                issues.append("Claude 模型名为空")
        if not (0 < self.temperature <= 2):
            issues.append(f"temperature 值异常: {self.temperature}（应为 0-2）")
        if self.max_tokens < 256:
            issues.append(f"max_tokens 过小: {self.max_tokens}（建议 ≥256）")
        return issues
