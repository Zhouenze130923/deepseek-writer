WRITER_SYSTEM = """你是一位专业小说作家。根据写作指南撰写高质量章节。

## 核心原则
1. 严格遵守角色设定——言行符合其特征和说话方式
2. 完成must_happen事件，展示而非说教
3. 章末钩子，遵守世界规则
4. 如果提供了待回收伏笔，本章必须回收
5. 如果提供了伏笔任务，本章必须植入

## 输出
【正文开始】（正文）【正文结束】
用***或---作为场景分隔符。"""

WRITER_CHAPTER_TEMPLATE = """## 作品: 《{title}》({genre}, {tone})
## 角色速查
{characters_brief}
## 本章任务
卷{volume_number}「{volume_title}」目标: {volume_goal}
第{chapter_number}章「{chapter_title}」: {must_happen} | 视角: {pov}
## 风格规则
{style_rules}
## 世界规则
{world_rules}
## 前情
{previous_context}
## 衔接提醒
{continuity_notes}
## 伏笔任务
{plant_foreshadowing}
{resolve_foreshadowing}
## 世界圣经
{bible_context}
直接输出本章正文。"""

WRITER_REVISE_TEMPLATE = """## 角色速查
{characters_brief}
## 风格规则
{style_rules}
## 世界规则
{world_rules}
## 原文
{original_content}
## 编辑意见
{editor_report}
逐条解决，保留好的部分。用【正文开始】和【正文结束】包裹。"""

WRITER_CONTINUE_TEMPLATE = """续写:
## 已写摘要
{written_summary}
## 接下来
{next_content}
## 角色速查
{characters_brief}
## 风格规则
{style_rules}
直接输出。"""
