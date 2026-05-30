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
