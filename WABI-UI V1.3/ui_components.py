# -*- coding: utf-8 -*-
"""
UI 组件库
定义了自适应 UI 代理可用的 UI 组件及其模式。
LLM 使用此定义来决定如何呈现信息。
"""

UI_COMPONENTS = {
    "text": {
        "description": "General text block with optional markdown and tone.",
        "props": {
            "content": "string",
            "markdown": "boolean (default true)",
            "tone": "string (neutral|positive|warning|error)",
            "size": "string (sm|md|lg)"
        }
    },
    "key_value_list": {
        "description": "Structured key-value pairs for facts and summaries.",
        "props": {
            "title": "string",
            "items": "list of objects: [{'label': 'string', 'value': 'string', 'highlight': 'boolean', 'icon': 'string'}]",
            "columns": "number (1|2)"
        }
    },
    "highlight_box": {
        "description": "Emphasis box for alerts and callouts.",
        "props": {
            "content": "string",
            "variant": "string (success|warning|info|error)",
            "icon": "string",
            "dismissible": "boolean"
        }
    },
    "carousel": {
        "description": "Horizontal card list for items or recipes.",
        "props": {
            "title": "string",
            "items": "list of objects: [{'title': 'string', 'subtitle': 'string', 'image_url': 'string', 'details': 'object'}]",
            "autoplay": "boolean",
            "interval_ms": "number"
        }
    },
    "image_display": {
        "description": "Single image with optional caption.",
        "props": {
            "image_url": "string",
            "caption": "string",
            "rounded": "boolean",
            "width": "number",
            "height": "number"
        }
    },
    "dynamic_place_table": {
        "description": "Interactive table for places/restaurants with sorting/filtering.",
        "props": {
            "title": "string",
            "items": "list of restaurant objects",
            "sortable_fields": "list of strings"
        }
    },
    "custom_html": {
        "description": "Custom HTML component for advanced bespoke layouts.",
        "props": {
            "html_content": "string",
            "description": "string"
        }
    },
    "button_group": {
        "description": "A group of actionable buttons for user choices.",
        "props": {
            "title": "string",
            "buttons": "list of objects: [{'label': 'string', 'value': 'string', 'variant': 'string (primary|secondary|outline)'}]"
        }
    },
    "progress_bar": {
        "description": "Progress indicator for goals and metrics.",
        "props": {
            "label": "string",
            "value": "number",
            "max": "number",
            "variant": "string (primary|success|warning|error)",
            "show_percent": "boolean"
        }
    },
    "comparison_table": {
        "description": "Side-by-side comparison table.",
        "props": {
            "title": "string",
            "columns": "list of strings",
            "rows": "list of lists",
            "footnote": "string",
            "sort_by": "string"
        }
    },
    "statistic_grid": {
        "description": "Compact grid of key metrics.",
        "props": {
            "title": "string",
            "items": "list of objects: [{'label': 'string', 'value': 'string|number', 'unit': 'string', 'trend': 'string (+|-|=)', 'variant': 'string'}]",
            "columns": "number"
        }
    },
    "tag_list": {
        "description": "Badge list of tags and attributes.",
        "props": {
            "title": "string",
            "tags": "list of strings",
            "selectable": "boolean"
        }
    },
    "steps_list": {
        "description": "Ordered steps for recipes or actions.",
        "props": {
            "title": "string",
            "steps": "list of strings",
            "numbered": "boolean",
            "icons": "list of strings"
        }
    },
    "bar_chart": {
        "description": "Bar chart for comparing values.",
        "props": {
            "title": "string",
            "items": "list of objects: [{'label': 'string', 'value': 'number'}]",
            "max": "number",
            "unit": "string",
            "orientation": "string (horizontal|vertical)",
            "colors": "list of strings"
        }
    },
    "pie_chart": {
        "description": "Pie chart for proportions.",
        "props": {
            "title": "string",
            "items": "list of objects: [{'label': 'string', 'value': 'number'}]",
            "unit": "string",
            "donut": "boolean",
            "colors": "list of strings"
        }
    },
    "line_chart": {
        "description": "Line chart for trends over ordered categories or time.",
        "props": {
            "title": "string",
            "points": "list of numbers",
            "labels": "list of strings",
            "unit": "string",
            "color": "string"
        }
    },
    "radar_chart": {
        "description": "Radar chart for comparing multiple axes of a single item.",
        "props": {
            "title": "string",
            "axes": "list of strings",
            "values": "list of numbers",
            "max": "number",
            "color": "string"
        }
    }
}

SYSTEM_PROMPT_TEMPLATE = """You are an expert UI designer for a health chatbot (Wabi). 
Your goal is to design the user interface response based on the user's intent and the available system data.

**Available UI Components:**
{components_json}

**Instructions:**
1. **Analyze Data**: Look carefully at the 'Current State Data'. 
   - If `recommended_restaurants` is present and not empty, you MUST use `dynamic_place_table` to display them.
   - If `nutrition_facts` is present, use `key_value_list` and `highlight_box`.
2. **Select Components**: Choose components that maximize usability.
   - **Restaurants**: Use `dynamic_place_table` so users can sort/filter. Do NOT use `carousel` for restaurants unless there are fewer than 3 items.
   - **Warnings**: Use `highlight_box` (variant='warning') for high calories or health risks.
   - **Creative Generation**: If standard components cannot fulfill the user's specific visualization or layout request, use the `custom_html` component to generate a bespoke solution.
     - **Self-Check**: When generating `custom_html`, ensure the HTML is valid and safe. Use Tailwind CSS for styling to match the system theme (blue/gray).
     - **Validation**: Ensure all tags are closed and class names are correct.
     - **Interactivity**: Use `data-wabi-action='value'` on clickable elements (like buttons) to trigger a message send with that value.
3. **Generate Suggestions**: Provide 3-4 short, actionable follow-up buttons (Quick Replies) in the `suggestions` array.
   - **IMPORTANT**: Suggestions MUST be answerable by YOU (the AI) directly in the chat.
   - **DO NOT** suggest actions that require external app features like "Log meal", "Track exercise", "Set goals", "Remind me".
   - **DO** suggest conversational follow-ups: "Is this healthy?", "How much sodium?", "Recipe for this", "Sort by Price â¬‡ï¸", "Vegetarian options".
4. **Utilize Mock Data**: Ensure you pass all relevant fields (like id, price_str, rating, is_veg) into props so the frontend can render correctly.
5. **Responsiveness & Accessibility**: Prefer concise summaries, set size on text, keep tables readable on mobile, and avoid complex layouts for chat platforms.
6. **Charts**: Use bar_chart for comparisons, pie_chart for proportions, progress_bar for goals. Keep legends short and units consistent.

**Output Format:**
Return ONLY a valid JSON object with the following structure:
{{
  "mode": "<intent string>",
  "summary": "<short summary string in the requested language>",
  "sections": [
    {{ "type": "<component_type>", ...<props> }}
  ],
  "suggestions": ["<short string>", "<short string>"]
}}
"""
