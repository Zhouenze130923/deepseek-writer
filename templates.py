from __future__ import annotations
"""写作模版库，定义章节节奏、伏笔布局、高潮分布。"""

TEMPLATES = {
    "网文升级流": {
        "description": "主角从弱到强的成长路线", "best_for": ["玄幻", "修仙", "都市异能"],
        "scale": "百万字级",
        "volume_structure": {"typical_volumes": (4, 8), "chapters_per_volume": (20, 40), "words_per_chapter": (2500, 4000)},
        "arc_pattern": [
            {"name": "开局", "volumes": "第1卷", "purpose": "世界构建、核心金手指、第一个小高潮"},
            {"name": "成长", "volumes": "第2-3卷", "purpose": "能力提升、势力建立、冲突展开"},
            {"name": "转折", "volumes": "第4-5卷", "purpose": "重大转折、真相揭露、中期高潮"},
            {"name": "巅峰", "volumes": "第6-7卷", "purpose": "终极冲突、各方势力汇聚"},
            {"name": "收官", "volumes": "第8卷", "purpose": "结局、各线收束"},
        ],
        "foreshadowing_rules": {"plant_every": "每3-5章", "resolve_within": "1-3卷内", "long_threads": "2-3条超长线"},
        "chapter_rhythm": ["开篇钩子→冲突升级→小高潮→悬念收尾", "每5章小高潮，卷尾大高潮"],
        "quality_checks": ["主角每卷有成长？", "反派动机合理？", "升级体系一致？", "配角有独立弧线？"],
    },
    "史诗奇幻": {
        "description": "多线叙事、宏大世界观", "best_for": ["奇幻", "科幻史诗", "历史架空"],
        "scale": "百万字级",
        "volume_structure": {"typical_volumes": (3, 6), "chapters_per_volume": (15, 30), "words_per_chapter": (4000, 7000)},
        "arc_pattern": [
            {"name": "暗流涌动", "volumes": "第1卷", "purpose": "多视角引入、世界构建、冲突暗示"},
            {"name": "风暴来袭", "volumes": "第2-3卷", "purpose": "冲突爆发、阵营形成、中期大事件"},
            {"name": "至暗时刻", "volumes": "第4-5卷", "purpose": "主角受挫、重大牺牲、真相揭露"},
            {"name": "最终之战", "volumes": "第6卷", "purpose": "终局对决、各线收束"},
        ],
        "foreshadowing_rules": {"plant_every": "每章1处细节", "long_threads": "5-8条跨卷长线"},
        "chapter_rhythm": ["多视角交替，每章1-3个视角", "卷末多线汇聚"],
        "quality_checks": ["各视角平衡？", "世界观自洽？", "势力关系动态变化？"],
    },
    "悬疑解谜": {
        "description": "环环相扣的谜题，层层反转", "best_for": ["悬疑", "推理", "惊悚"],
        "scale": "中长篇",
        "volume_structure": {"typical_volumes": (1, 3), "chapters_per_volume": (12, 24), "words_per_chapter": (3000, 5000)},
        "arc_pattern": [
            {"name": "谜面", "volumes": "前1/3", "purpose": "核心谜题、线索铺设"},
            {"name": "深入", "volumes": "中间1/3", "purpose": "线索收束、反转、误导揭露"},
            {"name": "真相", "volumes": "后1/3", "purpose": "最终反转、真相大白"},
        ],
        "foreshadowing_rules": {"plant_every": "每章2-3处线索", "fair_play": "线索在揭晓前展示"},
        "chapter_rhythm": ["新线索→推理→新疑问→推进", "每3章一个反转"],
        "quality_checks": ["核心诡计自洽？", "所有线索可回溯？", "反转有铺垫？"],
    },
    "三幕剧经典": {
        "description": "经典好莱坞结构", "best_for": ["言情", "都市", "成长"],
        "scale": "中篇到长篇",
        "volume_structure": {"typical_volumes": (1, 3), "chapters_per_volume": (10, 20), "words_per_chapter": (3000, 5000)},
        "arc_pattern": [
            {"name": "建置", "volumes": "前25%", "purpose": "日常、触发事件、不可逆选择"},
            {"name": "对抗", "volumes": "中间50%", "purpose": "障碍升级、中点转折、最暗时刻"},
            {"name": "解决", "volumes": "后25%", "purpose": "最终对决、角色成长完成"},
        ],
        "foreshadowing_rules": {"plant_every": "每5-8章", "resolve_within": "同卷内"},
        "chapter_rhythm": ["场景→反应→困境→决策→新场景"],
        "quality_checks": ["主角有清晰弧线？", "情感转折有铺垫？"],
    },
    "英雄之旅": {
        "description": "坎贝尔神话结构", "best_for": ["奇幻冒险", "武侠", "少年漫"],
        "scale": "长篇",
        "volume_structure": {"typical_volumes": (3, 5), "chapters_per_volume": (12, 25), "words_per_chapter": (3000, 5000)},
        "arc_pattern": [
            {"name": "启程", "volumes": "第1卷", "purpose": "平凡世界→冒险召唤→跨越门槛"},
            {"name": "启蒙", "volumes": "第2-3卷", "purpose": "考验之路→最大磨难→奖励"},
            {"name": "归来", "volumes": "第4-5卷", "purpose": "回归之路→最终复活→带着灵药归来"},
        ],
        "foreshadowing_rules": {"plant_every": "每5章", "mentor_fate": "导师命运开篇暗示"},
        "chapter_rhythm": ["冒险→挑战→领悟→前进"],
        "quality_checks": ["每个阶段完成叙事功能？", "导师恰当退场？"],
    },
    "多主角群像剧": {
        "description": "多主角各自发展，命运交织", "best_for": ["群像剧", "战争史诗", "家族saga"],
        "scale": "百万字级",
        "volume_structure": {"typical_volumes": (4, 8), "chapters_per_volume": (15, 30), "words_per_chapter": (3000, 5000)},
        "arc_pattern": [
            {"name": "各自登场", "volumes": "第1-2卷", "purpose": "各主角独立引入，暗示交汇点"},
            {"name": "命运交织", "volumes": "第3-4卷", "purpose": "各线交汇，关系网形成"},
            {"name": "共同危机", "volumes": "第5-6卷", "purpose": "共同威胁，个人vs集体"},
            {"name": "终局", "volumes": "第7-8卷", "purpose": "各线收束，角色弧线完成"},
        ],
        "foreshadowing_rules": {"plant_every": "每章每主角1处", "long_threads": "每人1-2条+2-3条群像交汇线"},
        "chapter_rhythm": ["每章2-3视角交替", "卷末至少3线交汇"],
        "quality_checks": ["各主角平衡？", "交汇自然？", "各自主角可区分？"],
    },
}

def list_templates() -> list[str]:
    return list(TEMPLATES.keys())

def get_template(name: str) -> dict | None:
    for key in TEMPLATES:
        if name in key or key in name: return TEMPLATES[key]
    return None

def template_to_prompt(template: dict) -> str:
    lines = [f"## 结构模版: {template.get('description','')}", f"适合篇幅: {template.get('scale','')}", "", "### 卷结构"]
    for arc in template.get("arc_pattern", []):
        lines.append(f"- **{arc['name']}**({arc['volumes']}): {arc['purpose']}")
    lines.append("\n### 章节节奏")
    for r in template.get("chapter_rhythm", []): lines.append(f"- {r}")
    lines.append("\n### 伏笔规则")
    for k, v in template.get("foreshadowing_rules", {}).items(): lines.append(f"- {k}: {v}")
    lines.append("\n### 质量检查")
    for q in template.get("quality_checks", []): lines.append(f"- [ ] {q}")
    return "\n".join(lines)
