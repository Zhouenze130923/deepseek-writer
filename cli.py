#!/usr/bin/env python3
"""DeepSeek Writer — 命令行接口，供任意 Agent 调用。

用法:
  deepseek-writer outline        --premise <文本> [--template <名称>] [--output <路径>]
  deepseek-writer characters     --outline <路径> [--constraints <文本>] [--output <路径>]
  deepseek-writer write          --project <名称> --volume <N> --chapter <N> [--output <路径>]
  deepseek-writer create         --premise <文本> --name <名称> [--template <名称>] [--output-dir <路径>]
  deepseek-writer list
  deepseek-writer status         --project <名称>
  deepseek-writer config         [--show | --set-key <key=value>]
  deepseek-writer export         --project <名称> --format <md|txt|epub|pdf|docx> [--output <路径>]

环境变量:
  DEEPSEEK_API_KEY   DeepSeek API 密钥
  ANTHROPIC_API_KEY  Claude API 密钥
  DEEPSEEK_WRITER_MODEL  模型名称（默认 deepseek-v4-flash）

返回格式: JSON (stdout)，便于机器解析。
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

# 确保能导入项目模块
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from config import Config
from orchestrator import Orchestrator
from project import Project, Volume, Chapter
from utils.file_manager import FileManager
from utils.exporter import Exporter
from agents.condenser import CondenserAgent


# ─── 工具函数 ───────────────────────────────────────────────

def _make_config() -> Config:
    """加载配置，优先取环境变量覆盖。"""
    cfg = Config.load()
    if os.environ.get("DEEPSEEK_API_KEY"):
        cfg.deepseek_api_key = os.environ["DEEPSEEK_API_KEY"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        cfg.claude_api_key = os.environ["ANTHROPIC_API_KEY"]
    if os.environ.get("DEEPSEEK_WRITER_MODEL"):
        cfg.model = os.environ["DEEPSEEK_WRITER_MODEL"]
    return cfg


def _ensure_api(cfg: Config) -> None:
    if not cfg.api_key:
        sys.stderr.write("ERROR: 未配置 API 密钥。请设置 DEEPSEEK_API_KEY 或 ANTHROPIC_API_KEY 环境变量。\n")
        sys.exit(1)


def _output(data, output_path: str | None = None) -> None:
    """输出 JSON。如果指定路径则写文件，否则打印到 stdout。"""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")


# ─── 子命令实现 ─────────────────────────────────────────────

def cmd_outline(args: argparse.Namespace) -> dict:
    """生成大纲。"""
    cfg = _make_config()
    _ensure_api(cfg)
    orch = Orchestrator(cfg)
    template_guide = ""
    if args.template:
        from templates import get_template, template_to_prompt
        t = get_template(args.template)
        if t:
            template_guide = template_to_prompt(t)
    result = orch.generate_outline(args.premise, template_guide)
    _output(result, args.output)
    return result


def cmd_characters(args: argparse.Namespace) -> dict:
    """设计角色。"""
    cfg = _make_config()
    _ensure_api(cfg)
    orch = Orchestrator(cfg)
    outline = json.loads(Path(args.outline).read_text(encoding="utf-8"))
    result = orch.design_characters(outline, constraints=args.constraints or "")
    _output(result, args.output)
    return result


def cmd_write(args: argparse.Namespace) -> dict:
    """写入指定章节。"""
    cfg = _make_config()
    _ensure_api(cfg)
    orch = Orchestrator(cfg)
    fm = FileManager()
    project = fm.load(args.project)
    if not project:
        sys.stderr.write(f"ERROR: 未找到项目「{args.project}」\n")
        sys.exit(1)

    # 找卷和章
    target_volume = None
    target_chapter = None
    for vol in project.volumes:
        if vol.volume_number == args.volume:
            target_volume = vol
            for ch in vol.chapters:
                if ch.chapter_number == args.chapter:
                    target_chapter = ch
                    break
            break

    if not target_chapter:
        sys.stderr.write(f"ERROR: 未找到第{args.volume}卷第{args.chapter}章\n")
        sys.exit(1)

    # 构建 brief
    condenser = CondenserAgent()
    brief = condenser.condense(
        outline={"volumes": [{"volume_number": v.volume_number, "volume_title": v.volume_title,
                              "synopsis": v.synopsis,
                              "chapters": [{"chapter_number": c.chapter_number, "chapter_title": c.chapter_title,
                                            "synopsis": c.synopsis, "pov_character": c.pov_character}
                                           for c in v.chapters]} for v in project.volumes],
                 "title": project.title, "genre": project.genre, "tone": project.tone},
        characters={"characters": list(project.characters.get("characters", [])),
                     "writing_style": project.writing_style,
                     "world_building": project.world_building,
                     "style_reference": project.style_reference},
        writing_style={},
    )

    prev_ctx = project.get_chapter_context(
        project.volumes.index(target_volume),
        target_volume.chapters.index(target_chapter),
    )

    bible_ctx = orch.get_bible_context(project, target_volume.volume_number, target_chapter.chapter_number)
    _, unresolved = orch.get_foreshadowing_context(project, target_volume.volume_number, target_chapter.chapter_number)

    content = orch._get_writer().write_chapter(
        brief=brief,
        volume_number=target_volume.volume_number,
        volume_title=target_volume.volume_title,
        volume_goal=target_volume.synopsis,
        chapter_number=target_chapter.chapter_number,
        chapter_title=target_chapter.chapter_title,
        must_happen=target_chapter.synopsis,
        pov=target_chapter.pov_character,
        previous_context=prev_ctx,
        plant_foreshadowing="",
        resolve_foreshadowing=unresolved,
        bible_context=bible_ctx,
    )

    target_chapter.content = content
    target_chapter.status = "done"
    fm.save(project)

    result = {
        "project": args.project,
        "volume": args.volume,
        "chapter": args.chapter,
        "title": target_chapter.chapter_title,
        "content": content,
        "word_count": len(content),
    }
    _output(result, args.output)
    return result


def cmd_create(args: argparse.Namespace) -> dict:
    """从灵感创建完整小说（大纲 + 人设 + 写简报）。"""
    cfg = _make_config()
    _ensure_api(cfg)
    orch = Orchestrator(cfg)

    template_guide = ""
    if args.template:
        from templates import get_template, template_to_prompt
        t = get_template(args.template)
        if t:
            template_guide = template_to_prompt(t)

    # 1. 大纲
    outline = orch.generate_outline(args.premise, template_guide)

    # 2. 人设
    characters = orch.design_characters(outline)

    # 3. 创建 Project
    project = Project(title=args.name, genre=outline.get("genre", ""),
                      premise=args.premise, theme=outline.get("theme", ""),
                      tone=outline.get("tone", ""),
                      characters=characters,
                      writing_style=characters.get("writing_style", {}),
                      style_reference=characters.get("style_reference", {}),
                      world_building=characters.get("world_building", {}),
                      template=args.template or "")
    for v_data in outline.get("volumes", []):
        vol = Volume(volume_number=v_data["volume_number"],
                     volume_title=v_data["volume_title"],
                     synopsis=v_data["synopsis"])
        for ch_data in v_data.get("chapters", []):
            ch = Chapter(chapter_number=ch_data["chapter_number"],
                         chapter_title=ch_data["chapter_title"],
                         synopsis=ch_data["synopsis"],
                         key_events=ch_data.get("key_events", []),
                         pov_character=ch_data.get("pov_character", ""),
                         word_count_target=ch_data.get("word_count_target", 3000))
            vol.chapters.append(ch)
        project.volumes.append(vol)

    # 保存
    fm = FileManager()
    proj_dir = fm.save(project)

    output_dir = args.output_dir or str(proj_dir)
    _output({
        "project": args.name,
        "volumes": len(project.volumes),
        "chapters": sum(len(v.chapters) for v in project.volumes),
        "path": str(proj_dir),
        "outline": outline,
        "characters": characters,
    }, os.path.join(output_dir, "create-result.json") if args.output_dir else args.output)

    return {"project": args.name, "path": str(proj_dir)}


def cmd_list(args: argparse.Namespace) -> list:
    """列出所有项目。"""
    fm = FileManager()
    projects = fm.list_projects()
    _output({"projects": projects}, args.output)
    return projects


def cmd_status(args: argparse.Namespace) -> dict:
    """查看项目状态。"""
    fm = FileManager()
    project = fm.load(args.project)
    if not project:
        sys.stderr.write(f"ERROR: 未找到项目「{args.project}」\n")
        sys.exit(1)

    total_ch = sum(len(v.chapters) for v in project.volumes)
    done_ch = sum(1 for v in project.volumes for c in v.chapters if c.status == "done")
    total_words = sum(len(c.content) for v in project.volumes for c in v.chapters)

    result = {
        "title": project.title,
        "genre": project.genre,
        "template": project.template or "auto",
        "volumes": len(project.volumes),
        "chapters": {"total": total_ch, "done": done_ch, "pending": total_ch - done_ch},
        "word_count": total_words,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "foreshadowing": project.foreshadowing.stats(),
        "bible": project.bible.stats(),
    }
    _output(result, args.output)
    return result


def cmd_config(args: argparse.Namespace) -> dict:
    """查看或设置配置。"""
    cfg = _make_config()
    if args.set_key:
        if "=" not in args.set_key:
            sys.stderr.write("ERROR: 格式应为 key=value\n")
            sys.exit(1)
        key, value = args.set_key.split("=", 1)
        key = key.strip()
        value = value.strip()
        field_map = {
            "DEEPSEEK_API_KEY": "deepseek_api_key",
            "ANTHROPIC_API_KEY": "claude_api_key",
            "DEEPSEEK_BASE_URL": "deepseek_base_url",
            "MODEL": "model",
            "CLAUDE_MODEL": "claude_model",
            "PROVIDER": "provider",
            "TEMPERATURE": "temperature",
            "MAX_TOKENS": "max_tokens",
        }
        if key in field_map:
            field = field_map[key]
            if field in ("temperature", "max_tokens"):
                setattr(cfg, field, type(getattr(cfg, field))(value))
            else:
                setattr(cfg, field, value)
        else:
            # 直接设置属性（允许任意字段）
            setattr(cfg, key.lower(), value)
        cfg.save()
        result = {"status": "saved", "key": key}
    else:
        result = {
            "provider": cfg.provider,
            "model": cfg.model if cfg.provider == "deepseek" else cfg.claude_model,
            "has_deepseek_key": bool(cfg.deepseek_api_key),
            "has_claude_key": bool(cfg.claude_api_key),
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "config_path": str(Path.home() / ".deepseek_writer" / "config.json"),
        }
    _output(result, args.output)
    return result


def cmd_web(args: argparse.Namespace) -> dict:
    """启动 Web 界面 (Gradio)。"""
    # 优先使用外部 shell 脚本启动（最可靠）
    import shutil, subprocess
    web_script = shutil.which("dswriter-web")
    if web_script:
        print("🌐 启动 Web 界面 → http://localhost:7860")
        try:
            subprocess.run([web_script], check=True)
        except KeyboardInterrupt:
            print("\nWeb 界面已关闭。")
        return {"status": "ok"}
    # 回退：直接启动 webui.py
    webui_path = str(_HERE / "webui.py")
    print("🌐 启动 Web 界面 → http://localhost:7860")
    try:
        proc = subprocess.Popen(
            [sys.executable, webui_path],
            cwd=str(_HERE),
        )
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\nWeb 界面已关闭。")
    return {"status": "ok"}


def cmd_repl(args: argparse.Namespace) -> dict:
    """启动交互式终端模式。"""
    sys.path.insert(0, str(_HERE))
    from main import DeepSeekWriter
    writer = DeepSeekWriter()
    try:
        writer.run()
    except KeyboardInterrupt:
        print("\n已退出交互模式。")
    return {"status": "ok"}


def cmd_export(args: argparse.Namespace) -> dict:
    """导出项目。"""
    # 列出语音（不导出）
    if getattr(args, 'list_voices', False):
        from utils.audio import AudioExporter
        AudioExporter.list_voices()
        return {"status": "ok"}

    fm = FileManager()
    project = fm.load(args.project)
    if not project:
        sys.stderr.write(f"ERROR: 未找到项目「{args.project}」\n")
        sys.exit(1)

    exp = Exporter(project)
    text_exporters = {
        "md": exp.export_markdown,
        "txt": exp.export_txt,
        "epub": exp.export_epub,
        "pdf": exp.export_pdf,
        "docx": exp.export_docx,
    }
    audio_formats = {"m4a", "mp3"}

    if args.format in text_exporters:
        output_path = args.output or text_exporters[args.format]()
        result = {"format": args.format, "path": str(output_path)}
    elif args.format in audio_formats:
        voice = getattr(args, 'voice', '')
        per_chapter = not getattr(args, 'merge', False)
        output_dir = exp.export_audio(fmt=args.format, per_chapter=per_chapter, voice=voice)
        result = {"format": f"audiobook/{args.format}", "path": str(output_dir)}
    else:
        sys.stderr.write(f"ERROR: 不支持的格式 {args.format}，可用: {', '.join(text_exporters.keys())} m4a mp3\n")
        sys.exit(1)

    _output(result, args.output)
    return result


# ─── CLI 入口 ───────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dswriter",
        description="DeepSeek Writer — AI 网文写作助手命令行工具",
        epilog="环境变量: DEEPSEEK_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_WRITER_MODEL",
    )
    parser.add_argument("--output", "-o", help="输出文件路径（默认 stdout）")

    sub = parser.add_subparsers(dest="command", required=True)

    # outline
    p_outline = sub.add_parser("outline", help="生成大纲")
    p_outline.add_argument("--premise", required=True, help="小说灵感/梗概")
    p_outline.add_argument("--template", help="写作模板名称")
    p_outline.set_defaults(func=cmd_outline)

    # characters
    p_chars = sub.add_parser("characters", help="设计角色")
    p_chars.add_argument("--outline", required=True, help="大纲 JSON 文件路径")
    p_chars.add_argument("--constraints", help="额外约束条件")
    p_chars.set_defaults(func=cmd_characters)

    # write
    p_write = sub.add_parser("write", help="写入章节")
    p_write.add_argument("--project", required=True, help="项目名称")
    p_write.add_argument("--volume", type=int, required=True, help="卷号")
    p_write.add_argument("--chapter", type=int, required=True, help="章节号")
    p_write.set_defaults(func=cmd_write)

    # create (full pipeline)
    p_create = sub.add_parser("create", help="从灵感创建完整小说")
    p_create.add_argument("--premise", required=True, help="小说灵感/梗概")
    p_create.add_argument("--name", required=True, help="项目名称")
    p_create.add_argument("--template", help="写作模板名称")
    p_create.add_argument("--output-dir", help="输出目录")
    p_create.set_defaults(func=cmd_create)

    # list
    sub.add_parser("list", help="列出所有项目").set_defaults(func=cmd_list)

    # status
    p_status = sub.add_parser("status", help="查看项目状态")
    p_status.add_argument("--project", required=True, help="项目名称")
    p_status.set_defaults(func=cmd_status)

    # config
    p_config = sub.add_parser("config", help="管理配置")
    p_config.add_argument("--show", action="store_true", help="显示当前配置")
    p_config.add_argument("--set-key", help="设置配置项，格式 key=value")
    p_config.set_defaults(func=cmd_config)

    # web
    sub.add_parser("web", help="启动 Web 界面 (Gradio)").set_defaults(func=cmd_web)

    # repl (interactive)
    sub.add_parser("repl", help="启动交互式终端模式").set_defaults(func=cmd_repl)

    # export
    p_export = sub.add_parser("export", help="导出项目")
    p_export.add_argument("--project", required=True, help="项目名称")
    p_export.add_argument("--format", required=True, choices=["md", "txt", "epub", "pdf", "docx", "m4a", "mp3"],
                          help="导出格式（m4a/mp3 为有声书，需要 edge-tts）")
    p_export.add_argument("--voice", default="zh-CN-XiaoxiaoNeural",
                          help="TTS 语音（仅 m4a/mp3 格式有效，默认 zh-CN-XiaoxiaoNeural）")
    p_export.add_argument("--merge", action="store_true", dest="merge",
                          help="合并为单文件（仅 m4a/mp3 格式有效，默认每章独立文件）")
    p_export.add_argument("--list-voices", action="store_true",
                          help="列出所有可用语音（不执行导出）")
    p_export.set_defaults(func=cmd_export)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
