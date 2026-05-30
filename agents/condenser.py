class CondenserAgent:
    name = "condenser"

    def condense(self, outline: dict, characters: dict, writing_style: dict) -> dict:
        chars_brief = []
        for c in characters.get("characters", []):
            tags = (c.get("quirks", []) or [])[:2]
            chars_brief.append({
                "name": c.get("name", ""), "role": c.get("role", ""),
                "core": f"{c.get('personality','')[:60]}，动机：{c.get('motivation','')[:40]}",
                "voice": c.get("speech_style", "")[:60], "tags": tags,
            })

        volume_plan = []
        for v in outline.get("volumes", []):
            chapters = []
            for ch in v.get("chapters", []):
                chapters.append({
                    "ch": ch.get("chapter_number", 0), "title": ch.get("chapter_title", ""),
                    "must_happen": ch.get("synopsis", "")[:120], "pov": ch.get("pov_character", ""),
                })
            volume_plan.append({
                "volume": v.get("volume_number", 0), "title": v.get("volume_title", ""),
                "goal": v.get("synopsis", "")[:120], "chapters": chapters,
            })

        ws = characters.get("writing_style", {}) or {}
        style_rules = [
            f"叙事: {ws.get('narrative_mode','第三人称')}", f"节奏: {ws.get('pace','中速')}",
            f"基调: {ws.get('tone','')}", f"句式: {ws.get('sentence_style','')}",
            f"对话占比: {ws.get('dialogue_ratio','中')}",
        ]
        for feat in ws.get("language_features", [])[:3]:
            style_rules.append(f"特点: {feat}")

        wb = characters.get("world_building", {}) or {}
        world_rules = wb.get("rules", [])[:10]

        continuity = ""
        if characters.get("style_reference", {}).get("style_notes"):
            continuity = characters["style_reference"]["style_notes"][:200]

        return {
            "title": outline.get("title", ""), "genre": outline.get("genre", ""),
            "tone": outline.get("tone", ""), "characters_brief": chars_brief,
            "volume_plan": volume_plan, "style_rules": style_rules,
            "world_rules": world_rules, "continuity_notes": continuity,
        }
