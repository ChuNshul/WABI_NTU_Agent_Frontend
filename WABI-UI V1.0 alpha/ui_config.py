# -*- coding: utf-8 -*-
"""
UI Agent Configuration
All constants, intent→route mappings, platform prompt fragments, and i18n
copy live here. Change behaviour by editing data — not node code.
"""

import os

# ── Bedrock ────────────────────────────────────────────────────────────────────
BEDROCK_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-southeast-1"
BEDROCK_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
BEDROCK_MAX_TOKENS = 4096
BEDROCK_TEMPERATURE = 0.5

# ── Intent → route mapping ─────────────────────────────────────────────────────
# The router iterates this dict; first match wins.
# Special keys "food_recognition_no_image" and "goal_planning" carry extra
# guard logic in the router node itself.
INTENT_ROUTES: dict[str, set[str]] = {
    "clarification":              {"clarification", "clarify", "澄清"},
    "food_recognition_no_image":  {"food_recognition", "食物识别", "识别", "拍食物"},
    "goal_planning":              {"goal_planning", "goal", "target", "目标", "目标设定", "规划", "计划"},
}

# Convenience alias used in prompt enrichment
GOAL_INTENTS: set[str] = INTENT_ROUTES["goal_planning"]

# Platforms where rich components must be downgraded to plain text
TEXT_ONLY_PLATFORMS: set[str] = {"wechat", "whatsapp"}

# ── Platform prompt fragments ──────────────────────────────────────────────────
# Appended to the base system prompt before sending to the LLM.
PLATFORM_PROMPTS: dict[str, str] = {
    "wechat": (
        "\n\nCRITICAL PLATFORM INSTRUCTION: The user is on WeChat. "
        "You MUST NOT use Markdown or complex components (no tables, carousels). "
        "Use plain text with emojis and line breaks only. "
        "Do NOT generate any 'suggestions' list."
    ),
    "whatsapp": (
        "\n\nCRITICAL PLATFORM INSTRUCTION: The user is on WhatsApp. "
        "Use 'text' components with Markdown: Tables for structured data, "
        "Blockquotes (> text) for highlights, ### for headers, *bold*, _italic_. "
        "Do NOT generate any 'suggestions' list."
    ),
    "web": (
        "\n\nPLATFORM INSTRUCTION: The user is on Web. "
        "Use all rich UI components freely (carousels, tables, highlight boxes, charts, etc.)."
    ),
}

GOAL_PLANNING_PROMPT: str = (
    "\n\nGOAL PLANNING INSTRUCTION: Derive all recommendations from the provided "
    "user_history — no generic targets. Compute real insights, risks, and measurable "
    "next-week goals from the data. For Web prefer: statistic_grid, line_chart, "
    "bar_chart, pie_chart, progress_bar, steps_list."
)

# ── Language output instruction ────────────────────────────────────────────────
# Appended last so it is the final, highest-priority instruction the LLM sees.
LANGUAGE_PROMPTS: dict[str, str] = {
    "Chinese": (
        "\n\nLANGUAGE INSTRUCTION (HIGHEST PRIORITY): "
        "You MUST write ALL output text in Simplified Chinese (简体中文). "
        "This includes: summary, every section's content/title/items/steps/labels, "
        "and every suggestion. Do NOT use any English words except proper nouns, "
        "brand names, or numeric values."
    ),
    "English": (
        "\n\nLANGUAGE INSTRUCTION (HIGHEST PRIORITY): "
        "You MUST write ALL output text in English. "
        "This includes: summary, every section's content/title/items/steps/labels, "
        "and every suggestion."
    ),
}

# ── I18n copy for deterministic nodes ─────────────────────────────────────────
# Structure: CLARIFICATION_COPY[platform_class][language]
# platform_class is "web" or "messaging" (covers wechat / whatsapp).

CLARIFICATION_COPY: dict[str, dict[str, dict]] = {
    "web": {
        "Chinese": {
            "summary":      "我可以为你提供餐厅推荐或食物识别。",
            "text_content": "请从下方选择：'我要餐厅推荐' 或 '我要食物识别'。",
            "title":        "请选择你需要的功能：",
            "buttons": [
                {"text": "🍽️ 我要餐厅推荐", "value": "我要餐厅推荐"},
                {"text": "🔍 我要食物识别", "value": "我要食物识别"},
            ],
        },
        "English": {
            "summary":      "I can provide restaurant recommendations or food recognition.",
            "text_content": "Please choose from the options below.",
            "title":        "Please select the function you need:",
            "buttons": [
                {"text": "🍽️ Restaurant Rec",  "value": "I want restaurant recommendations"},
                {"text": "🔍 Food Recognition", "value": "I want to recognize food"},
            ],
        },
    },
    "messaging": {
        "Chinese": {
            "summary": "你的需求不太明确，我来帮你选择方向。",
            "content": (
                "*请选择你需要的功能：*\n"
                "1) 餐厅推荐（回复：推荐/餐厅）\n"
                "2) 食物识别（回复：识别/图片）\n"
                "提示：直接回复对应数字或关键词即可开始。"
            ),
        },
        "English": {
            "summary": "Your request is a bit unclear — let me help you choose.",
            "content": (
                "*Please select the function you need:*\n"
                "1) Restaurant Recommendation (Reply: recommend/restaurant)\n"
                "2) Food Recognition (Reply: recognize/image)\n"
                "Tip: Reply with the number or keyword to begin."
            ),
        },
    },
}

FOOD_RECOGNITION_NO_IMAGE_COPY: dict[str, dict[str, str]] = {
    "Chinese": {
        "summary":     "请上传一张食物图片，我来帮您分析。",
        "content":     "要开始食物识别，请拖拽或点击下方区域上传一张照片。",
        "suggestion1": "这个功能怎么用？",
        "suggestion2": "返回",
    },
    "English": {
        "summary":     "Please upload a food image and I will analyse it for you.",
        "content":     "To start food recognition, drag or click the area below to upload a photo.",
        "suggestion1": "How to use this?",
        "suggestion2": "Go back",
    },
}
