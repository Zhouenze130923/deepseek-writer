# DeepSeek Writer — AI 网文写作助手

DeepSeek Writer 是一款基于 LLM 多 Agent 协作的网文写作工具，支持 DeepSeek 和 Claude 双模型驱动。输入灵感，自动完成从大纲、人设到章节写作的全流程。

## 功能特性

- **多 Agent 写作流水线**：大纲 Agent → 人设 Agent → 压缩 Agent → 写作 Agent → 编辑 Agent
- **双模型支持**：DeepSeek / Claude，可随时切换
- **流式输出**：章节内容实时流式生成，所见即所得
- **三编辑并行审阅**：逻辑编辑 + 风格编辑 + 伏笔编辑同时审查
- **伏笔追踪**：自动记录每章埋下的伏笔，待回收提醒
- **世界圣经**：连续性子系统，追踪角色、世界观、关键物品等设定一致性
- **多格式导出**：Markdown / TXT / EPUB / PDF / DOCX
- **Web UI 界面**：基于 Gradio 的图形化操作界面（`/web` 启动）
- **写作模板库**：内置网文升级流、史诗奇幻、悬疑解谜、三幕剧等 6 种模板
- **续写 / 回溯 / 重写**：支持 `/continue` 续写未完成章节，`/backtrack` 回溯，`/retry` 重写

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥（DeepSeek 或 Claude）
python main.py
# 启动后输入 /config 配置密钥

# 或者命令行直接运行
python main.py
```

## 使用方法

### 终端模式

启动后在提示符输入小说灵感即可开始创作：

```
> 一个天才建筑师穿越到古代，用现代建筑技术改变世界
```

### 命令列表

| 命令 | 说明 |
|------|------|
| `/config` | 配置 API 密钥和模型 |
| `/fast` | 极速模式（跳过审阅） |
| `/strict` | 严格模式（2 轮审阅） |
| `/triple` | 三编辑并行审阅 |
| `/templates` | 查看写作模板 |
| `/status` | 查看项目进度 |
| `/stats` | 查看统计（字数、伏笔、圣经） |
| `/list` | 列出已保存项目 |
| `/load <名称>` | 加载已有项目 |
| `/continue` | 继续未完成章节 |
| `/retry N` | 重写第 N 章 |
| `/backtrack N` | 回溯到第 N 章 |
| `/export` | 多格式导出 |
| `/import <文件>` | 导入人设/世界观 |
| `/memory` | 查看记忆状态 |
| `/web` | 启动 Web 界面 |
| `/help` | 帮助 |
| `/quit` | 退出 |

### Web 界面

输入 `/web` 启动 Gradio Web UI，浏览器访问 `http://localhost:7860`。

## 项目结构

```
deepseek-writer/
├── main.py                # 主入口（CLI）
├── webui.py               # Web UI (Gradio)
├── config.py              # 配置管理
├── orchestrator.py        # Agent 编排器
├── project.py             # 项目数据模型
├── templates.py           # 写作模板库
├── agents/
│   ├── base.py            # Agent 基类
│   ├── outline.py         # 大纲 Agent
│   ├── character.py       # 人设 Agent
│   ├── condenser.py       # 压缩 Agent（生成写作简报）
│   ├── writer.py          # 写作 Agent
│   └── editor.py          # 编辑 Agent
├── prompts/
│   ├── writer.py          # 写作提示词
│   ├── editor.py          # 编辑提示词
│   ├── outline.py         # 大纲提示词
│   └── character.py       # 人设提示词
├── utils/
│   ├── continuity.py      # 连续性子系统（世界圣经）
│   ├── foreshadowing.py   # 伏笔追踪
│   ├── file_manager.py    # 文件管理
│   ├── exporter.py        # 多格式导出
│   ├── memory.py          # 记忆系统
│   ├── style_guide.py     # 风格指南
│   └── display.py         # 终端显示
└── llm/
    ├── client.py          # LLM 客户端
    └── models.py          # 模型列表
```

## 写作工作流

```
输入灵感
    │
    ▼
[大纲 Agent] → 生成结构大纲（卷/章/事件） → 用户确认
    │
    ▼
[人设 Agent] → 设计角色 + 写作风格 + 世界观 → 用户确认
    │
    ▼
[压缩 Agent] → 生成写作简报（角色速查/风格规则/伏笔任务）
    │
    ▼
[写作 Agent] → 逐章写作（流式输出）
    │
    ▼
[编辑 Agent] → 审阅（逻辑/风格/伏笔并行）→ 自动修改
    │
    ▼
保存项目 / 导出
```

## 依赖

- Python 3.10+
- `rich` — 终端美化
- `openai` / `anthropic` — LLM 调用
- `gradio` — Web UI
- `ebooklib`, `fpdf2`, `python-docx` — 多格式导出

## 配置

配置文件自动保存至 `~/.deepseek_writer/config.json`。

支持两种 API 提供商：

- **DeepSeek**: API Key 从 [platform.deepseek.com](https://platform.deepseek.com) 获取
- **Claude**: API Key 从 [console.anthropic.com](https://console.anthropic.com) 获取

## 相关

- [华棠班级管理系统](https://huatang-class.top) — 另一个由同一位作者开发的教育管理项目
