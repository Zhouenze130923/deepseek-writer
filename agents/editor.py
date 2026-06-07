import concurrent.futures

from agents.base import BaseAgent
from prompts.editor import (
    EDITOR_SYSTEM, EDITOR_USER_TEMPLATE,
    LOGIC_SYSTEM, STYLE_SYSTEM, FORESHADOW_EDITOR_SYSTEM,
)


# 每位编辑的超时时间（秒）
_EDITOR_TIMEOUT = 90


class EditorAgent(BaseAgent):
    """冷血编辑——支持单一审查或三项专项并行审查。

    strictness: 1-5
      1 = 极宽松
      2 = 宽松
      3 = 适中
      4 = 严格
      5 = 极其严格
    """
    name = "editor"

    def __init__(self, client, config):
        super().__init__(client, config)
        self.strictness = getattr(config, 'strictness', 3)

    # ── 严格度配置 ─────────────────────────────────────

    _STRICTNESS_MAP = {
        1: {  # 极宽松
            'label': '极宽松',
            'header': '你是温和的编辑助手。你的目标是帮作者省token，只找读者绝对会注意到的致命问题。',
            'scope': '只找以下问题：\n1. 【致命矛盾】核心设定被推翻\n2. 【关键信息错误】人名/关键事实错误\n其余一切忽略。宁漏勿滥。',
            'logic': '只找致命逻辑错误。小瑕疵全部忽略。写「逻辑通过」或指出1-2个最严重的问题。',
            'style': '只找毁灭性叙事问题（如全部是对话没有叙述）。小问题全部忽略。写「节奏通过」或指出。',
            'foreshadow': '只找该收的伏笔完全没提的情况。小线索强弱不查。写「连贯通过」或指出。',
            'pass_threshold': 2,  # 2/3 通过就跳过
            'report_min_len': 200,  # 报告字数 > 这个才算有问题
        },
        2: {  # 宽松
            'label': '宽松',
            'header': '你是善意的编辑。只找明显影响阅读体验的问题，不给作者添堵。',
            'scope': '只找以下问题：\n1. 【明显矛盾】人物行为与设定冲突、前后事实不一致\n2. 【严重拖沓】连续800字无推进\n3. 【重大漏洞】剧情依赖巧合/降智\n小瑕疵一律忽略。',
            'logic': '只找明显的人物矛盾、设定冲突。小bug忽略。写「逻辑通过」或指出问题。',
            'style': '只找明显的展示vs说教失衡、拖沓段落。不影响阅读的不查。写「节奏通过」或指出。',
            'foreshadow': '只找明显的伏笔断裂、该收没收。写「连贯通过」或指出。',
            'pass_threshold': 2,
            'report_min_len': 120,
        },
        3: {  # 适中（默认）
            'label': '适中',
            'header': '你是负责任的编辑。影响阅读体验的问题都要指出，但不过度挑刺。',
            'scope': '逐项检查以下内容，发现任何实质问题都要指出：\n1. 【逻辑一致】人物行为是否合设定、事实是否连贯、因果是否合理、世界观规则是否遵守\n2. 【叙事质量】展示vs说教、对话辨识度、描写效率\n3. 【节奏结构】段落拖沓(500字标准)、章末收束\n4. 【伏笔连贯】伏笔推进、大纲对齐\n不过度纠结细微差异。',
            'logic': '逐项检查人物一致性、事实连贯性、因果关系、世界观规则。写「逻辑通过」或指出问题。',
            'style': '逐项检查展示vs说教、对话辨识度、描写效率、信息重复。写「节奏通过」或指出问题。',
            'foreshadow': '逐项检查伏笔处理、章末收束、情节连贯、大纲对齐。写「连贯通过」或指出问题。',
            'pass_threshold': 3,
            'report_min_len': 60,
        },
        4: {  # 严格
            'label': '严格',
            'header': '你是严格的编辑。任何可能降低文章质量的问题都不要放过。',
            'scope': '全面审查以下内容，每项必须给出结论：\n1. 【逻辑细节】人物行为/对话是否符合设定、时间线精确、事实无矛盾、因果链条完整\n2. 【叙事细节】展示过多说教、对话辨识度不够、描写的有效性、信息重复\n3. 【节奏细节】段落是否拖沓(300字标准)、情节推进效率、章末处理\n4. 【伏笔细节】伏笔位置是否合理、该提的是否提到、大纲方向是否吻合\n5. 【语言细节】是否有明显啰嗦、表意不清的句子',
            'logic': '全面检查逻辑细节：人物设定一致性、对话是否符合性格、时间线精确性、因果合理性。写「逻辑通过」或列出全部问题。',
            'style': '全面检查叙事细节：展示vs说教比例、每个角色的对话辨识度、描写是否服务于情节。写「节奏通过」或列出全部问题。',
            'foreshadow': '全面检查伏笔细节：每个伏笔的状态（该收/该推/维持）、章末处理、大纲对齐。写「连贯通过」或列出全部问题。',
            'pass_threshold': 3,
            'report_min_len': 30,
        },
        5: {  # 极其严格
            'label': '极其严格',
            'header': '你是苛刻的编辑。逐字逐句审查，不放过任何瑕疵。假设这是要出版的终稿。',
            'scope': '逐字逐句审查：\n1. 【逻辑】任何可能产生疑问的设定、行为、对话、事实都要标注\n2. 【叙事】所有展示vs说教、对话辨识度、描写效率、信息重复逐项评估\n3. 【节奏】每个段落的有效性评估，200字无明显推进就标注\n4. 【伏笔】所有伏笔精确状态追溯，章末强度评估\n5. 【语言】啰嗦表达、重复用词、表意不清、语法问题',
            'logic': '逐字审查：每处人物行为是否100%符合设定、时间线精确到天、因果链条无断裂。列出所有问题。',
            'style': '逐字审查：每段展示vs说教比例、每个角色的独特说话方式、描写的必要性。列出所有问题。',
            'foreshadow': '逐字审查：每个伏笔的开合状态精确标注、章末钩子强度评估、大纲偏差分析。列出所有问题。',
            'pass_threshold': 3,
            'report_min_len': 1,
        },
    }

    def _strict_cfg(self, key: str):
        s = max(1, min(5, self.strictness))
        return self._STRICTNESS_MAP.get(s, self._STRICTNESS_MAP[3]).get(key)

    def _build_strict_system(self, base_system: str, role_suffix: str) -> str:
        """根据严格度构建带语气调整的系统提示。"""
        cfg = self._strict_cfg(None) if False else None
        header = self._strict_cfg('header')
        scope = self._strict_cfg('scope')
        return f"""{header}

{base_system}

## 审查范围
{scope}

{role_suffix}"""

    def _build_context(self, title, genre, volume_number, volume_title, chapter_number, chapter_title,
                       content, brief, bible_context):
        chars_list = brief.get("characters_brief", []) if brief else []
        chars_text = "\n".join(
            f"- {c.get('name','')}({c.get('role','')}): {c.get('core','')} 说话:{c.get('voice','')}"
            for c in chars_list
        )
        style_text = "\n".join(f"- {r}" for r in brief.get("style_rules", [])) if brief else ""
        world_text = "\n".join(f"- {r}" for r in brief.get("world_rules", [])) if brief else ""

        return {
            "title": title, "genre": genre,
            "volume_number": volume_number, "volume_title": volume_title,
            "chapter_number": chapter_number, "chapter_title": chapter_title,
            "content": content,
            "characters_brief": chars_text or "无",
            "style_rules": style_text or "无",
            "world_rules": world_text or "无",
            "bible_context": bible_context or "无",
        }

    def _strict_system(self, base_system: str) -> str:
        """给系统提示加上严格度前缀。"""
        header = self._strict_cfg('header')
        scope = self._strict_cfg('scope')
        return f"""{header}

{base_system}

## 审查范围（严格度 {self.strictness}/5）
{scope}

每条问题用⚠标注。无问题写对应关键词。"""

    def review(self, title, genre, volume_number, volume_title,
               chapter_number, chapter_title, content, brief, bible_context=""):
        ctx = self._build_context(title, genre, volume_number, volume_title,
                                  chapter_number, chapter_title, content, brief, bible_context)
        user_message = EDITOR_USER_TEMPLATE.format(**ctx)
        system = self._strict_system(EDITOR_SYSTEM)
        return self.run(system, user_message, temperature=0.4, max_tokens=2048)

    def review_stream(self, title, genre, volume_number, volume_title,
                      chapter_number, chapter_title, content, brief, bible_context=""):
        ctx = self._build_context(title, genre, volume_number, volume_title,
                                  chapter_number, chapter_title, content, brief, bible_context)
        user_message = EDITOR_USER_TEMPLATE.format(**ctx)
        system = self._strict_system(EDITOR_SYSTEM)
        return self.run(system, user_message, stream=True, temperature=0.4, max_tokens=2048)

    # --- Parallel triple-editor review ---

    @staticmethod
    def _safe_run(runner, name: str) -> str:
        """安全运行单个编辑，异常隔离。"""
        try:
            result = runner()
            return result or f'{name}通过'
        except Exception as e:
            return f'⚠ {name}审查异常: {e}'

    def review_parallel(self, title, genre, volume_number, volume_title,
                        chapter_number, chapter_title, content, brief, bible_context="") -> str:
        """三项专项编辑并行审查，合并报告。

        三个编辑（逻辑/风格/伏笔）同时并发调用 LLM API，
        各自独立、互不影响。任一编辑失败不影响其他两个。
        所有 API 调用使用统一的连接池，节省等待时间。
        """
        ctx = self._build_context(title, genre, volume_number, volume_title,
                                  chapter_number, chapter_title, content, brief, bible_context)
        base_msg = EDITOR_USER_TEMPLATE.format(**ctx)

        strict_tag = f'（严格度 {self.strictness}/5）'
        logic_hint = self._strict_cfg('logic')
        style_hint = self._strict_cfg('style')
        foreshadow_hint = self._strict_cfg('foreshadow')

        # 注：每个编辑的 max_tokens 随严格度增加，给严格模式更多输出空间
        edit_tokens = {1: 1024, 2: 1536, 3: 2048, 4: 3072, 5: 4096}.get(self.strictness, 2048)

        def _call_logic():
            logic_system = f'{LOGIC_SYSTEM}\n\n{strict_tag}\n{logic_hint}'
            return self.run(logic_system,
                base_msg,
                stream=False, temperature=0.4, max_tokens=edit_tokens)

        def _call_style():
            style_system = f'{STYLE_SYSTEM}\n\n{strict_tag}\n{style_hint}'
            return self.run(style_system,
                base_msg,
                stream=False, temperature=0.4, max_tokens=edit_tokens)

        def _call_foreshadow():
            shadow_system = f'{FORESHADOW_EDITOR_SYSTEM}\n\n{strict_tag}\n{foreshadow_hint}'
            return self.run(shadow_system,
                base_msg,
                stream=False, temperature=0.4, max_tokens=edit_tokens)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            # 三个编辑并行提交，互不依赖
            futures = {
                pool.submit(self._safe_run, _call_logic, '逻辑'): '逻辑',
                pool.submit(self._safe_run, _call_style, '风格'): '风格',
                pool.submit(self._safe_run, _call_foreshadow, '伏笔'): '伏笔',
            }

            results = {}
            for future in concurrent.futures.as_completed(futures, timeout=_EDITOR_TIMEOUT):
                name = futures[future]
                try:
                    results[name] = future.result(timeout=5)
                except concurrent.futures.TimeoutError:
                    results[name] = f'⚠ {name}审查超时(>{_EDITOR_TIMEOUT}s)'
                except Exception as e:
                    results[name] = f'⚠ {name}审查异常: {e}'

        return f"""## 🔍 三专项编辑联合审查

### 逻辑编辑（一致性/矛盾/因果）
{results.get('逻辑', '逻辑通过')}

### 风格编辑（文笔/展示/对话）
{results.get('风格', '节奏通过')}

### 伏笔编辑（线索/钩子/节奏）
{results.get('伏笔', '连贯通过')}
"""

    # ── 外部接口：供 main/webui 获取严格度配置 ──────

    def get_strictness_config(self) -> dict:
        """返回当前严格度的相关参数，供 issue 检测逻辑使用。"""
        return {
            'strictness': self.strictness,
            'pass_threshold': self._strict_cfg('pass_threshold'),
            'report_min_len': self._strict_cfg('report_min_len'),
            'label': self._strict_cfg('label'),
        }
