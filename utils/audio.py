"""有声书导出模块 — 使用 Microsoft Edge TTS（免费）将小说转为音频。

依赖: pip install edge-tts

使用方法:
    from utils.audio import AudioExporter
    exporter = AudioExporter(project)
    exporter.export_m4a()        # 全本一章一个文件
    exporter.export_per_chapter()  # 每章独立文件

支持的 TTS 服务:
    - edge-tts (默认): Microsoft Edge 免费 TTS，支持流式中文字幕
    - gTTS 备选: 更简单但音质略差

中国声优推荐:
    - zh-CN-XiaoxiaoNeural: 晓晓（温柔女声，适合言情/叙事）
    - zh-CN-YunxiNeural: 云希（阳光男声，适合玄幻/冒险）
    - zh-CN-XiaoyiNeural: 晓伊（活泼女声）
    - zh-CN-YunyangNeural: 云扬（专业男声，适合旁白）
    - zh-CN-XiaohanNeural: 晓涵（自然女声）
    - zh-CN-YunjianNeural: 云健（磁性男声）
"""

from __future__ import annotations
import asyncio
import os
import re
import tempfile
import time
from pathlib import Path

from project import Project


# ── 中文语音列表 ─────────────────────────────

ZH_VOICES = [
    "zh-CN-XiaoxiaoNeural",   # 晓晓 - 温柔女声（推荐）
    "zh-CN-YunxiNeural",      # 云希 - 阳光男声
    "zh-CN-XiaoyiNeural",     # 晓伊 - 活泼女声
    "zh-CN-YunyangNeural",    # 云扬 - 专业男声（旁白）
    "zh-CN-XiaohanNeural",    # 晓涵 - 自然女声
    "zh-CN-YunjianNeural",    # 云健 - 磁性男声
    "zh-CN-XiaomengNeural",   # 晓梦 - 甜美女声
    "zh-CN-YunxiaNeural",     # 云霞 - 成熟女声
    "zh-TW-HsiaoChenNeural",  # 晓臻 - 台湾国语
]

# 单人 narrator 的默认推荐
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class AudioExporter:
    """有声书导出器。

    使用 Microsoft Edge 免费 TTS 将章节转换为音频文件。
    支持 m4a 和 mp3 格式（通过 ffmpeg 转码）。
    """

    def __init__(self, project: Project, output_dir: str = "", voice: str = DEFAULT_VOICE):
        self.project = project
        self.output_dir = Path(output_dir) if output_dir else (
            Path.home() / "Desktop" / "DeepSeekWriter" / project.title / "audiobook"
        )
        self.voice = voice

    # ── 公共接口 ─────────────────────────────

    def export_m4a(self, per_chapter: bool = True) -> str:
        """导出为 m4a 格式。

        per_chapter=True → 每章一个文件
        per_chapter=False → 合并为一个文件
        """
        return self._export("m4a", per_chapter)

    def export_mp3(self, per_chapter: bool = True) -> str:
        """导出为 mp3 格式。

        per_chapter=True → 每章一个文件
        per_chapter=False → 合并为一个文件
        """
        return self._export("mp3", per_chapter)

    def _export(self, ext: str, per_chapter: bool) -> str:
        """通用导出逻辑。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 第一步：将各章转为 WAV（edge-tts 输出）
        chapter_files = []
        total_chapters = sum(
            1 for v in self.project.volumes for c in v.chapters if c.content
        )
        current = 0

        for vi, vol in enumerate(self.project.volumes):
            for ci, ch in enumerate(vol.chapters):
                if not ch.content:
                    continue
                current += 1
                text = self._prepare_text(vi, ci, ch)
                wav_path = str(self.output_dir / f"ch{ch.chapter_number:04d}.wav")
                self._log(f"🎤 正在朗读 [{current}/{total_chapters}] 第{ch.chapter_number}章「{ch.chapter_title}」...")
                self._tts_to_wav(text, wav_path)
                chapter_files.append((ch, wav_path))

                if per_chapter:
                    # 直接转单章为最终格式
                    final_path = str(self.output_dir / f"第{ch.chapter_number}章_{ch.chapter_title}.{ext}")
                    self._convert_to_final(wav_path, final_path, ext)
                    self._log(f"  ✅ 已生成: {final_path}")

        if not per_chapter and chapter_files:
            # 合并所有章节
            merged_path = str(self.output_dir / f"《{self.project.title}》完整版.{ext}")
            self._log(f"🔗 合并 {len(chapter_files)} 章为 {ext}...")
            self._merge_files([p for _, p in chapter_files], merged_path, ext)
            self._log(f"  ✅ 已生成: {merged_path}")

        # 清理临时 .wav 文件（如果是单章模式且 wav 还在）
        for _, wav_path in chapter_files:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

        self._log(f"📂 输出目录: {self.output_dir}")
        return str(self.output_dir)

    # ── 文本处理 ─────────────────────────────

    def _prepare_text(self, vi: int, ci: int, ch) -> str:
        """拼接卷章标题和正文，清理格式。"""
        volume = self.project.volumes[vi]
        parts = [
            f"第{volume.volume_number}卷「{volume.volume_title}」",
            f"第{ch.chapter_number}章「{ch.chapter_title}」",
            self._clean_text(ch.content),
        ]
        return "\n\n".join(parts)

    def _clean_text(self, text: str) -> str:
        """清理文本以适合 TTS 朗读。"""
        # 移除 markdown 标记
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'~~.+?~~', '', text)
        text = re.sub(r'`{1,3}[^`]*`{1,3}', '', text)

        # 替换场景分隔符为停顿提示
        text = re.sub(r'^[\*\-]{3,}$', '（停顿）', text, flags=re.MULTILINE)
        text = re.sub(r'\* \* \*', '（停顿）', text)

        # 清理多余空白
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text

    # ── TTS 调用 ─────────────────────────────

    def _tts_to_wav(self, text: str, output_path: str):
        """使用 edge-tts 将文本转为 wav。

        对长文本分段处理（单段 ≤ 2000 字），再拼接为完整 wav。
        """
        segments = self._split_text(text, max_chars=1800)
        temp_files = []

        for i, seg in enumerate(segments):
            seg_path = output_path.replace(".wav", f"_{i:04d}.wav")
            temp_files.append(seg_path)
            self._edge_tts_single(seg, seg_path)

        if len(temp_files) == 1:
            os.rename(temp_files[0], output_path)
        else:
            self._concatenate_wavs(temp_files, output_path)
            for tf in temp_files:
                try:
                    os.remove(tf)
                except OSError:
                    pass

    def _edge_tts_single(self, text: str, output_path: str):
        """调用 edge-tts 生成单段音频。"""
        try:
            import edge_tts
        except ImportError:
            raise RuntimeError(f"Edge TTS 失败: 请安装 edge-tts (pip install edge-tts)")
        try:
            asyncio.run(self._async_tts(text, output_path, edge_tts))
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                # 在已有事件循环的线程中运行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._async_tts(text, output_path, edge_tts))
                    return future.result()
            raise RuntimeError(f"Edge TTS 失败: {e}")
        except Exception as e:
            raise RuntimeError(f"Edge TTS 失败: {e}")

    @staticmethod
    async def _async_tts(text: str, output_path: str, edge_tts=None):
        """edge-tts 异步调用（兼容 5.x 和 7.x）。"""
        if edge_tts is None:
            import edge_tts
        import inspect
        sig = inspect.signature(edge_tts.Communicate.__init__)
        params = list(sig.parameters.keys())
        if 'text' in params and 'voice' in params:
            # v7.x: Communicate(text, voice, ...)
            tts = edge_tts.Communicate(text, DEFAULT_VOICE)
        else:
            # v5.x: Communicate() with setter methods
            tts = edge_tts.Communicate()
            tts.text = text
            tts.voice = DEFAULT_VOICE
        await tts.save(output_path)

    @staticmethod
    def _split_text(text: str, max_chars: int = 2000) -> list[str]:
        """将长文本按自然断点切分段，每段不超过 max_chars。

        按句子或标点断句，保证朗读时断点自然。
        """
        if len(text) <= max_chars:
            return [text]

        # 先按段落切
        paragraphs = text.split("\n")
        segments = []
        current = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                if current:
                    current += "\n"
                continue

            # 检查当前段落本身是否就超长
            if len(para) > max_chars:
                # 先把当前累积的存入
                if current:
                    segments.append(current.strip())
                    current = ""
                # 对超长段落，按标点断句再切
                sub_segs = AudioExporter._split_by_sentence(para, max_chars)
                for sub in sub_segs:
                    if len(current) + len(sub) > max_chars and current:
                        segments.append(current.strip())
                        current = sub + "\n"
                    else:
                        current += sub + "\n"
                continue

            if len(current) + len(para) > max_chars and current:
                segments.append(current.strip())
                current = para + "\n"
            else:
                current += para + "\n"

        if current.strip():
            segments.append(current.strip())

        if not segments:
            segments = [text[:max_chars]]

        return segments

    @staticmethod
    def _split_by_sentence(text: str, max_chars: int) -> list[str]:
        """按句号、问号、感叹号等句子边界切分一段超长文本。"""
        # 用正则分割句子，保留分隔符
        parts = re.split(r'(?<=[。！？；\.\!\?;])\s*', text)
        parts = [p.strip() for p in parts if p.strip()]
        if not parts:
            return [text[:max_chars]]

        result = []
        current = ""
        for part in parts:
            if len(part) > max_chars:
                # 单个句子都超长，强硬截断
                if current:
                    result.append(current)
                for i in range(0, len(part), max_chars):
                    result.append(part[i:i + max_chars])
                current = ""
            elif len(current) + len(part) > max_chars:
                result.append(current)
                current = part
            else:
                current += part
        if current:
            result.append(current)

        return result

    @staticmethod
    def _concatenate_wavs(input_files: list[str], output_path: str):
        """使用 ffmpeg 拼接多个 wav 文件。"""
        import subprocess
        list_file = output_path + ".list"
        with open(list_file, "w") as f:
            for wav in input_files:
                f.write(f"file '{os.path.abspath(wav)}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
             "-c", "copy", output_path],
            capture_output=True, timeout=120,
        )
        if os.path.exists(list_file):
            os.remove(list_file)

    @staticmethod
    def _convert_to_final(input_wav: str, output_path: str, ext: str):
        """转 wav 为最终格式（m4a 或 mp3）。"""
        import subprocess

        # 检测 ffmpeg
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # 没有 ffmpeg，直接保留 wav
            os.rename(input_wav, output_path.replace(f".{ext}", ".wav"))
            return

        codec = {"m4a": "aac", "mp3": "libmp3lame"}.get(ext, "aac")
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_wav,
             "-c:a", codec, "-b:a", "128k",
             "-metadata", f"title={Path(output_path).stem}",
             output_path],
            capture_output=True, timeout=300,
        )

    @staticmethod
    def _merge_files(wav_files: list[str], output_path: str, ext: str):
        """合并多个 wav 为单文件。"""
        import subprocess

        if ext == "wav":
            AudioExporter._concatenate_wavs(wav_files, output_path)
            return

        # 先合并为临时 wav
        merged_wav = output_path + ".merged.wav"
        AudioExporter._concatenate_wavs(wav_files, merged_wav)

        # 再转码
        codec = {"m4a": "aac", "mp3": "libmp3lame"}.get(ext, "aac")
        subprocess.run(
            ["ffmpeg", "-y", "-i", merged_wav,
             "-c:a", codec, "-b:a", "128k",
             output_path],
            capture_output=True, timeout=300,
        )
        if os.path.exists(merged_wav):
            os.remove(merged_wav)

    # ── 工具 ─────────────────────────────────

    def _log(self, msg: str):
        """打印进度日志。"""
        # 不做 fancy 日志，直接 print；WebUI 可捕获 stdout
        print(msg)

    def get_available_voices(self) -> list[str]:
        """返回可用中文语音列表。"""
        return ZH_VOICES

    @staticmethod
    def list_voices():
        """打印所有可用中文语音。"""
        print("可用中文语音:")
        for v in ZH_VOICES:
            name = v.replace("zh-CN-", "").replace("zh-TW-", "台·")
            print(f"  {v}")
        print(f"\n默认: {DEFAULT_VOICE}")
