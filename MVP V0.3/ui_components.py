# -*- coding: utf-8 -*-
"""
UI Component Library
Defines the available UI components and their schemas for the Adaptive UI Agent.
The LLM uses this definition to decide how to present information.
"""

UI_COMPONENTS = {
    "text": {
        "description": "Displays a block of text. Use for general information, conversational responses, explanations, or greetings.",
        "props": {
            "content": "string (The text content to display. Supports markdown **bold**)"
        }
    },
    "key_value_list": {
        "description": "Displays a list of key-value pairs. Use for structured data like nutrition facts, product details, specifications, or summary stats.",
        "props": {
            "title": "string (Optional title for the list)",
            "items": "list of objects: [{'label': 'string', 'value': 'string', 'highlight': 'boolean (optional)'}]"
        }
    },
    "highlight_box": {
        "description": "A colored box to highlight important information like warnings, success messages, key stats, or health scores.",
        "props": {
            "content": "string (The text content)",
            "variant": "string (One of: 'success', 'warning', 'info', 'error')"
        }
    },
    "carousel": {
        "description": "A horizontally scrollable list of cards. Use for displaying recipes, food items, or simple lists where sorting is not needed.",
        "props": {
            "title": "string (Optional title for the carousel)",
            "items": "list of objects: [{'title': 'string', 'subtitle': 'string', 'image_url': 'string (optional)', 'details': 'object (optional full data)'}]"
        }
    },
    "image_display": {
        "description": "Displays a single image with an optional caption. Use when a specific image is relevant to the context (e.g., the user's uploaded food image).",
        "props": {
            "image_url": "string (URL of the image)",
            "caption": "string (Optional caption text)"
        }
    },
    "dynamic_place_table": {
        "description": "A specialized table for displaying a list of places/restaurants. MUST be used for restaurant recommendations to enable sorting by price/distance and filtering.",
        "props": {
            "title": "string (e.g., 'Nearby Options')",
            "items": "list of restaurant objects (Pass the full object from the data source, including id, name, rating, price, dist, etc.)"
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
3. **Generate Suggestions**: Provide 3-4 short, actionable follow-up buttons (Quick Replies) in the `suggestions` array.
   - **IMPORTANT**: Suggestions MUST be answerable by YOU (the AI) directly in the chat.
   - **DO NOT** suggest actions that require external app features like "Log meal", "Track exercise", "Set goals", "Remind me".
   - **DO** suggest conversational follow-ups: "Is this healthy?", "How much sodium?", "Recipe for this", "Sort by Price ⬇️", "Vegetarian options".
4. **Utilize Mock Data**: Ensure you pass *all* relevant fields (like `id`, `price_str`, `rating`, `is_veg`) into the component props so the frontend can render them correctly.

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
