"""多格式导出器——支持 TXT, EPUB, PDF, DOCX。"""

from __future__ import annotations
from pathlib import Path
from project import Project


class Exporter:
    """将项目导出为多种格式。"""

    def __init__(self, project: Project, output_dir: str = ""):
        self.project = project
        self.output_dir = Path(output_dir) if output_dir else Path.home() / "Desktop" / "DeepSeekWriter" / project.title

    def export_all(self) -> dict[str, str]:
        results = {}
        results["md"] = self.export_markdown()
        results["txt"] = self.export_txt()
        results["epub"] = self.export_epub()
        results["pdf"] = self.export_pdf()
        results["docx"] = self.export_docx()
        return results

    def export_markdown(self) -> str:
        path = self.output_dir / "完整版.md"
        lines = [f"# 《{self.project.title}》", "", f"> {self.project.premise}", ""]
        for vol in self.project.volumes:
            lines.append(f"# 第{vol.volume_number}卷「{vol.volume_title}」")
            lines.append("")
            for ch in vol.chapters:
                if ch.content:
                    lines.append(f"## 第{ch.chapter_number}章「{ch.chapter_title}」")
                    lines.append("")
                    lines.append(ch.content)
                    lines.append("")
        path.write_text("\n".join(lines))
        return str(path)

    def export_txt(self) -> str:
        path = self.output_dir / "完整版.txt"
        lines = [f"《{self.project.title}》", f"{self.project.premise}", ""]
        for vol in self.project.volumes:
            lines.append(f"第{vol.volume_number}卷「{vol.volume_title}」")
            for ch in vol.chapters:
                if ch.content:
                    lines.append(f"第{ch.chapter_number}章「{ch.chapter_title}」")
                    lines.append(ch.content)
                    lines.append("")
        path.write_text("\n".join(lines))
        return str(path)

    def export_epub(self) -> str:
        path = self.output_dir / f"{self.project.title}.epub"
        try:
            self._write_epub(str(path))
            return str(path)
        except ImportError:
            return f"EPUB导出需要: pip install ebooklib (跳过)"

    def export_pdf(self) -> str:
        path = self.output_dir / f"{self.project.title}.pdf"
        try:
            self._write_pdf(str(path))
            return str(path)
        except ImportError:
            # Fallback: use markdown as intermediate
            md_path = Path(self.export_markdown())
            try:
                import markdown, pdfkit
                html = markdown.markdown(md_path.read_text())
                pdfkit.from_string(html, str(path))
                return str(path)
            except ImportError:
                return f"PDF导出需要: pip install markdown pdfkit (跳过)"

    def export_docx(self) -> str:
        path = self.output_dir / f"{self.project.title}.docx"
        try:
            self._write_docx(str(path))
            return str(path)
        except ImportError:
            return f"DOCX导出需要: pip install python-docx (跳过)"

    def _write_epub(self, path: str):
        from ebooklib import epub
        book = epub.EpubBook()
        book.set_title(self.project.title)
        book.set_language("zh")
        book.add_author("DeepSeek Writer")

        chapters = []
        for vol in self.project.volumes:
            for ch in vol.chapters:
                if ch.content:
                    c = epub.EpubHtml(
                        title=ch.chapter_title,
                        file_name=f"v{vol.volume_number}_c{ch.chapter_number}.xhtml",
                    )
                    c.content = f"<h1>{ch.chapter_title}</h1>\n{ch.content.replace(chr(10), '<br/>')}"
                    book.add_item(c)
                    chapters.append(c)

        book.toc = chapters
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + chapters
        epub.write_epub(path, book)

    def _write_pdf(self, path: str):
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_font("CJK", "", "/System/Library/Fonts/PingFang.ttc", uni=True)
        pdf.add_page()
        pdf.set_font("CJK", "", 16)
        pdf.cell(0, 10, f"《{self.project.title}》", ln=True)
        pdf.set_font("CJK", "", 11)

        for vol in self.project.volumes:
            pdf.set_font("CJK", "", 14)
            pdf.cell(0, 10, f"第{vol.volume_number}卷「{vol.volume_title}」", ln=True)
            for ch in vol.chapters:
                if ch.content:
                    pdf.set_font("CJK", "", 13)
                    pdf.cell(0, 8, ch.chapter_title, ln=True)
                    pdf.set_font("CJK", "", 11)
                    for line in ch.content.split("\n"):
                        pdf.multi_cell(0, 6, line or " ")
                    pdf.ln(4)
        pdf.output(path)

    def _write_docx(self, path: str):
        from docx import Document
        doc = Document()
        doc.add_heading(f"《{self.project.title}》", 0)
        doc.add_paragraph(self.project.premise)
        for vol in self.project.volumes:
            doc.add_heading(f"第{vol.volume_number}卷「{vol.volume_title}」", 1)
            for ch in vol.chapters:
                if ch.content:
                    doc.add_heading(f"第{ch.chapter_number}章「{ch.chapter_title}」", 2)
                    for para in ch.content.split("\n"):
                        if para.strip():
                            doc.add_paragraph(para.strip())
        doc.save(path)
