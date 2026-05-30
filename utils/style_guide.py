STYLE_GUIDES = {
    "网文爽文": {"narrative_mode": "第三人称", "pace": "快节奏", "tone": "热血激昂", "sentence_style": "简洁有力", "dialogue_ratio": "高", "description_density": "中低", "chapter_structure": "每3000-4000字结尾设钩子", "notes": "每章有爽点，主角有明显成长线"},
    "轻小说": {"narrative_mode": "第一人称", "pace": "轻快活泼", "tone": "轻松幽默", "sentence_style": "口语化", "dialogue_ratio": "高", "description_density": "中", "chapter_structure": "每2500-4000字", "notes": "二次元风格，角色互动为主"},
    "严肃文学": {"narrative_mode": "多视角", "pace": "中慢", "tone": "深沉内敛", "sentence_style": "精雕细琢", "dialogue_ratio": "中低", "description_density": "高", "chapter_structure": "每4000-8000字结构精巧", "notes": "注重语言质感和深度"},
    "悬疑推理": {"narrative_mode": "第三人称限知", "pace": "紧凑", "tone": "紧张悬疑", "sentence_style": "简洁精准", "dialogue_ratio": "中", "description_density": "中高", "chapter_structure": "每3000-5000字埋线索", "notes": "线索有出处和归处，逻辑自洽"},
    "科幻": {"narrative_mode": "第三人称", "pace": "中速", "tone": "理性宏大", "sentence_style": "清晰准确", "dialogue_ratio": "中", "description_density": "中高", "chapter_structure": "每4000-6000字", "notes": "科幻设定自洽，规则不可打破"},
    "武侠": {"narrative_mode": "第三人称全知", "pace": "张弛有度", "tone": "侠义豪迈", "sentence_style": "半文半白", "dialogue_ratio": "中", "description_density": "中高", "chapter_structure": "每4000-6000字文武交替", "notes": "打斗有画面感，江湖气息浓厚"},
    "言情": {"narrative_mode": "第一人称", "pace": "中等", "tone": "温暖甜蜜", "sentence_style": "细腻优美", "dialogue_ratio": "高", "description_density": "中", "chapter_structure": "每3000-5000字情感递进", "notes": "感情有层次和波折"},
    "历史": {"narrative_mode": "第三人称", "pace": "中慢", "tone": "厚重沉稳", "sentence_style": "典雅庄重", "dialogue_ratio": "中", "description_density": "高", "chapter_structure": "每5000-8000字", "notes": "历史背景考究，言行符合时代"},
}

def list_styles() -> list[str]:
    return list(STYLE_GUIDES.keys())

def get_style(style_name: str) -> dict:
    for name, guide in STYLE_GUIDES.items():
        if style_name in name or name in style_name:
            return guide
    return STYLE_GUIDES["网文爽文"]
