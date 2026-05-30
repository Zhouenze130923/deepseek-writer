from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

def print_banner():
    console.print("""
[bold cyan]╔════════════════════════════════════════════════╗
║          DeepSeek Writer - AI 写作助手         ║
║  专为写作而生 · 多模型 · 多代理协作           ║
╚════════════════════════════════════════════════╝[/bold cyan]""")

def print_help():
    console.print("")

def print_styles():
    from utils.style_guide import STYLE_GUIDES
    table = Table(title="写作风格", box=box.ROUNDED)
    table.add_column("风格", style="cyan")
    table.add_column("叙事方式")
    table.add_column("节奏")
    table.add_column("适合场景")
    for name, guide in STYLE_GUIDES.items():
        table.add_row(name, guide["narrative_mode"], guide["pace"], guide["tone"])
    console.print(table)

def print_project_status(project):
    table = Table(title=f"《{project.title}》", box=box.ROUNDED)
    table.add_column("卷", style="cyan")
    table.add_column("章")
    table.add_column("标题")
    table.add_column("状态")
    table.add_column("字数")
    for vol in project.volumes:
        for ch in vol.chapters:
            status_icon = {"pending": "待写", "writing": "写作中", "done": "完成", "reviewing": "审阅中"}.get(ch.status, ch.status)
            table.add_row(f"第{vol.volume_number}卷", f"第{ch.chapter_number}章", ch.chapter_title, status_icon, str(len(ch.content) if ch.content else 0))
    console.print(table)

def print_outline(outline: dict):
    console.print(f"\n[bold cyan]{outline.get('title','未命名')}[/bold cyan]")
    console.print(f"[dim]类型: {outline.get('genre','')} | 主题: {outline.get('theme','')} | 基调: {outline.get('tone','')}[/dim]")
    console.print(f"[yellow]{outline.get('premise','')}[/yellow]\n")
    for vol in outline.get("volumes", []):
        text = f"[bold]第{vol['volume_number']}卷「{vol['volume_title']}」[/bold]\n[dim]{vol['synopsis']}[/dim]\n"
        for ch in vol.get("chapters", []):
            text += f"  ├ 第{ch['chapter_number']}章「{ch['chapter_title']}」- {ch['synopsis'][:60]}...\n"
        console.print(Panel(text.strip(), box=box.ROUNDED))

def print_characters(characters: dict):
    console.print("\n[bold cyan]人物档案[/bold cyan]\n")
    for c in characters.get("characters", []):
        text = f"[bold]{c['name']}[/bold] - {c.get('role','')}\n年龄: {c.get('age','')} | {c.get('personality','')[:80]}...\n动机: {c.get('motivation','')}"
        console.print(Panel(text, box=box.ROUNDED))
    ws = characters.get("writing_style", {})
    if ws:
        style_text = "\n".join(f"- {k}: {v}" for k, v in ws.items() if not isinstance(v, list))
        console.print(Panel(style_text, title="写作风格", box=box.ROUNDED))

def print_streaming(text: str, end: str = ""):
    console.print(text, end=end, highlight=False)

def print_success(msg: str):
    console.print(f"[green]{msg}[/green]")

def print_error(msg: str):
    console.print(f"[red]{msg}[/red]")

def print_info(msg: str):
    console.print(f"[blue]{msg}[/blue]")

def print_warning(msg: str):
    console.print(f"[yellow]{msg}[/yellow]")
