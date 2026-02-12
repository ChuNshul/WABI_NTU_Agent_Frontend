from typing import Any, Dict, List, Optional
import json
import os
import boto3
import re
import pathlib
from langgraph_app.orchestrator.state import GraphState
from langgraph_app.agents.UI.ui_components import UI_COMPONENTS, SYSTEM_PROMPT_TEMPLATE

def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        load_dotenv = None  # type: ignore
    env_paths = [
        pathlib.Path("/home/songlh/WABI_NTU_Agent_Backend/.env"),
        pathlib.Path(".env"),
    ]
    for p in env_paths:
        if not p.is_file():
            continue
        if load_dotenv:
            load_dotenv(str(p), override=False)
        else:
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

_load_env()

# --- Bedrock Setup ---
REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-southeast-1"
MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"

def _get_bedrock_client():
    try:
        return boto3.client(
            "bedrock-runtime",
            region_name=REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        )
    except Exception as e:
        print(f"Warning: Failed to initialize Bedrock client: {e}")
        return None

def generate_ui_plan(state: GraphState) -> GraphState:
    """
    Generates a UI Plan based on the current state intent and data.
    Uses LLM for adaptive generation.
    """
    # Try Adaptive Generation
    print("Attempting Adaptive UI Generation...")
    adaptive_plan = _generate_adaptive_ui_plan(state)
    if adaptive_plan:
        print("Using Adaptive UI Plan.")
        state.ui_plan = adaptive_plan
        return state

    # Basic Fallback if LLM fails (minimal valid response)
    print("Fallback to minimal UI generation.")
    state.ui_plan = {
        "mode": "error",
        "summary": "Sorry, I encountered an issue generating the display. Here is the raw response.",
        "sections": [
            {
                "type": "text",
                "content": state.agent_response or "Please try again later."
            }
        ],
        "suggestions": []
    }
    return state

def _generate_adaptive_ui_plan(state: GraphState) -> Optional[Dict[str, Any]]:
    """
    Uses LLM to generate an adaptive UI plan.
    Returns None if generation fails.
    """
    platform = getattr(state, 'platform', 'web')
    
    # Deterministic handling for clarification intent (no LLM needed)
    if str(state.intent).lower() in ["clarification", "clarify", "澄清"]:
        lang = getattr(state, 'language', 'Chinese')
        
        if platform == "web":
            if lang == 'English':
                summary = "I can provide restaurant recommendations or food recognition."
                text_content = "Please choose from the options below: 'I want restaurant recommendations' or 'I want to recognize food'."
                html_title = "Please select the function you need:"
                button1_text = "🍽️ Restaurant Rec"
                button1_onclick_val = "I want restaurant recommendations"
                button2_text = "🔍 Food Recognition"
                button2_onclick_val = "I want to recognize food"
            else:
                summary = "我可以为你提供餐厅推荐或食物识别。"
                text_content = "请从下方选择：‘我要餐厅推荐’ 或 ‘我要食物识别’。"
                html_title = "请选择你需要的功能："
                button1_text = "🍽️ 我要餐厅推荐"
                button1_onclick_val = "我要餐厅推荐"
                button2_text = "🔍 我要食物识别"
                button2_onclick_val = "我要食物识别"

            html = (
                f'<div class="p-4" style="background: var(--card-bg);">'
                f'<div class="text-sm mb-3" style="color: var(--text-color);">{html_title}</div>'
                '<div class="flex gap-2 flex-wrap">'
                f'<button class="px-3 py-2 rounded-full border text-sm" '
                'style="background: var(--bg-color); color: var(--text-color); border-color: var(--border-color);" '
                f'onclick="document.getElementById(\'userInput\').value=\'{button1_onclick_val}\'; sendMessage()">{button1_text}</button>'
                f'<button class="px-3 py-2 rounded-full border text-sm" '
                'style="background: var(--bg-color); color: var(--text-color); border-color: var(--border-color);" '
                f'onclick="document.getElementById(\'userInput\').value=\'{button2_onclick_val}\'; sendMessage()">{button2_text}</button>'
                '</div>'
                '</div>'
            )
            return {
                "mode": "clarification",
                "language": lang,
                "summary": summary,
                "sections": [
                    {
                        "type": "text",
                        "content": text_content
                    },
                    {
                        "type": "custom_html",
                        "description": "Clarification Options",
                        "html_content": html
                    }
                ],
                "suggestions": []
            }
        else:
            if lang == 'English':
                summary = "Your request is a bit unclear, let me help you choose a direction."
                content = (
                    "*Please select the function you need:*\n"
                    "1) Restaurant Recommendation (Reply: recommend/restaurant)\n"
                    "2) Food Recognition (Reply: recognize/image)\n"
                    "Tip: Reply with the corresponding number or keyword to begin."
                )
            else:
                summary = "你的需求不太明确，我来帮你选择方向。"
                content = (
                    "*请选择你需要的功能：*\n"
                    "1) 餐厅推荐（回复：推荐/餐厅）\n"
                    "2) 食物识别（回复：识别/图片）\n"
                    "提示：直接回复对应数字或关键词即可开始。"
                )
            return {
                "mode": "clarification",
                "summary": summary,
                "sections": [
                    { "type": "text", "content": content }
                ],
                "suggestions": []
            }

    # Deterministic handling for food recognition without an image
    if str(state.intent).lower() in ["food_recognition", "食物识别", "识别", "拍食物"]:
        if not getattr(state, 'has_image', False):
            lang = getattr(state, 'language', 'Chinese')
            if lang == 'English':
                summary = "Please upload a food image and I will analyze it for you."
                content = "To start food recognition, drag or click the area below to upload a photo."
                suggestions = ["How to use this?", "Go back"]
            else:
                summary = "请上传一张食物图片，我来帮您分析。"
                content = "要开始食物识别，请拖拽或点击下方区域上传一张照片。"
                suggestions = ["这个功能怎么用？", "返回"]
            return {
                "mode": "image_upload_request",
                "language": lang,
                "summary": summary,
                "sections": [{
                    "type": "text",
                    "content": content
                }],
                "suggestions": suggestions
            }

    if str(state.intent).lower() in ["goal_planning", "goal", "target", "目标", "目标设定", "规划", "计划"]:
        history = getattr(state, "user_history", None)
        days = history.get("days", []) if isinstance(history, dict) else []
        if not days:
            return {
                "mode": "goal_planning",
                "summary": "我还没有你的历史饮食数据，先从本周开始记录吧。",
                "sections": [{"type": "text", "content": "暂无历史数据可用于目标设定。"}],
                "suggestions": ["给我一个简单目标", "如何开始记录饮食", "今天吃什么更健康？"]
            }
    
    client = _get_bedrock_client()
    if not client:
        return None

    # Format Chat History
    history_str = ""
    if state.chat_history:
        for msg in state.chat_history:
            role = "User" if msg.type == "human" else "Assistant"
            content = str(msg.content)[:500] # Truncate long messages
            history_str += f"{role}: {content}\n"

    # Prepare Context for LLM
    context_data = {
        "intent": state.intent,
        "platform": platform, # Pass platform to LLM
        "user_input": str(state.user_input)[:1000] if state.user_input else None, 
        "agent_response": str(state.agent_response)[:1000] if state.agent_response else None,
        "nutrition_facts": state.nutrition_facts,
        "recommended_restaurants": state.recommended_restaurants,
        "has_image": state.has_image,
        "image_path": state.food_vis_path,
        "chat_history_summary": history_str,
        "user_history": getattr(state, "user_history", None)
    }

    # Combine System Prompt and User Data
    full_prompt = SYSTEM_PROMPT_TEMPLATE.format(components_json=json.dumps(UI_COMPONENTS, indent=2))
    
    # Add Platform Instructions
    if platform == 'wechat':
        full_prompt += "\n\nCRITICAL PLATFORM INSTRUCTION: The user is on WeChat. You MUST NOT use Markdown (no bold **, no italic _). You MUST NOT use complex components like tables or carousels. Convert all content into plain text lists or simple text with emojis. Use strictly line breaks for formatting. Do NOT generate any 'suggestions' list."
    elif platform == 'whatsapp':
        full_prompt += "\n\nCRITICAL PLATFORM INSTRUCTION: The user is on WhatsApp. You MUST use 'text' components, but you SHOULD utilize advanced Markdown features to present rich information. Use Markdown Tables for structured data (like restaurant lists or nutrition facts). Use Blockquotes (> text) for highlights or summaries. Use Headers (###) for sections. Use *bold* and _italic_ for emphasis. Do NOT generate any 'suggestions' list."
    else:
        full_prompt += "\n\nPLATFORM INSTRUCTION: The user is on a Web Browser. You can use all rich UI components (carousels, tables, highlight boxes, etc.)."

    if str(state.intent).lower() in ["goal_planning", "goal", "target", "目标", "目标设定", "规划", "计划"]:
        full_prompt += (
            "\n\nGOAL PLANNING INSTRUCTION: You MUST make recommendations by analyzing the provided user_history. "
            "Do NOT use generic or hardcoded targets; derive insights, risks, and next-week goals from the actual history data. "
            "Prefer concrete, measurable goals and an actionable weekly plan. "
            "For Web, prefer a mix of statistic_grid, line_chart, bar_chart, pie_chart (donut optional), progress_bar, and steps_list. "
            "All numbers shown must be computable from user_history; if something cannot be computed, clearly say it and avoid inventing."
        )
        
    full_prompt += f"\n\nCurrent State Data:\n{json.dumps(context_data, indent=2, default=str)}"

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.5,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": full_prompt}]}
        ]
    }

    try:
        response = client.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        
        # Extract Token Usage
        input_tokens = 0
        output_tokens = 0
        
        # Bedrock response headers contain usage info
        # 'x-amzn-bedrock-input-token-count': '123'
        # 'x-amzn-bedrock-output-token-count': '456'
        if 'ResponseMetadata' in response and 'HTTPHeaders' in response['ResponseMetadata']:
            headers = response['ResponseMetadata']['HTTPHeaders']
            input_tokens = int(headers.get('x-amzn-bedrock-input-token-count', 0))
            output_tokens = int(headers.get('x-amzn-bedrock-output-token-count', 0))
            
        print(f"Bedrock Token Usage - Input: {input_tokens}, Output: {output_tokens}")

        result = json.loads(response["body"].read())
        output_text = result["content"][0]["text"]
        print("Raw UI Plan output:\n" + (output_text if isinstance(output_text, str) else str(output_text)))
        
        # Extract JSON from output
        json_match = re.search(r"\{[\s\S]*\}", output_text)
        if json_match:
            try:
                # Try parsing directly first
                plan = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                # If failed, try to clean control characters (newlines in strings)
                # This regex replaces unescaped newlines within JSON strings with \n
                # However, a simpler approach for strict=False might be sufficient or just replacing actual newlines
                json_str = json_match.group(0)
                # Replace real newlines with \n, but be careful not to break structure
                # A safer bet is strict=False which allows control characters in some python versions, 
                # but standard json.loads doesn't support unescaped newlines in strings.
                # Let's try a robust cleanup: escape newlines that are not formatting newlines
                # This is hard to do perfectly with regex. 
                # Let's try strict=False which is allowed in standard lib json.loads? No, it's not.
                # Let's try replacing actual newlines with \\n if they seem to be inside strings.
                
                # Fallback: Just try replacing all newlines with space or \n if parsing fails, 
                # but that breaks the JSON structure newlines.
                
                # Alternative: The LLM might be outputting newlines in the text content.
                # Let's try to parse with strict=False (if using a library that supports it, but here we use 'json')
                # Python's json.loads allows control characters if strict=False is NOT passed? No, strict=False allows *control characters*, 
                # but invalid escape sequences. Actually strict=False allows control characters like \n in strings.
                try:
                    plan = json.loads(json_match.group(0), strict=False)
                except:
                    print("JSON parsing with strict=False failed. Attempting to sanitize.")
                    # Last ditch effort: Escape unescaped control characters
                    # We can use a regex to find newlines that are NOT followed by specific JSON tokens, but it's risky.
                    # Simple fix: If the error is specific, we might not fix it easily.
                    # But for now, strict=False usually fixes "Invalid control character".
                    raise 
            
            # Inject token usage into the plan for frontend display
            plan['token_usage'] = {
                'input': input_tokens,
                'output': output_tokens,
                'total': input_tokens + output_tokens
            }
            plan['language'] = getattr(state, 'language', 'Chinese') # Inject language
            
            # Validation Step: Check for Custom HTML validity and Platform Compliance
            if "sections" in plan and isinstance(plan["sections"], list):
                for section in plan["sections"]:
                    # Platform Enforcement: Force unsupported components to text for WeChat/WhatsApp
                    if platform in ['wechat', 'whatsapp'] and section.get("type") not in ['text', 'image_display']:
                        print(f"Warning: Non-text component '{section.get('type')}' generated for {platform}. Forcing fallback to text.")
                        # Best effort conversion if LLM ignored instructions
                        content = ""
                        if section.get("title"):
                            content += f"*{section.get('title')}*\n"
                        
                        if section.get("items") and isinstance(section.get("items"), list):
                            for item in section.get("items"):
                                if isinstance(item, dict):
                                    label = item.get("label") or item.get("title") or ""
                                    value = item.get("value") or item.get("subtitle") or item.get("description") or ""
                                    if label and value:
                                        content += f"{label}: {value}\n"
                                    elif label:
                                        content += f"{label}\n"
                                    elif value:
                                        content += f"{value}\n"
                        elif section.get("content"):
                            content += str(section.get("content"))
                            
                        section["type"] = "text"
                        section["content"] = content

                    if section.get("type") == "custom_html":
                        html_content = section.get("html_content", "")
                        # Basic Self-Correction/Validation for safety
                        if "<script>" in html_content:
                            print("Warning: Script tag detected in custom_html. Removing for safety.")
                            html_content = html_content.replace("<script>", "").replace("</script>", "")
                            section["html_content"] = html_content
                        
                        # Check for basic HTML structure (lightweight validation)
                        if html_content.count("<div") != html_content.count("</div>"):
                             print("Warning: Mismatched div tags in custom_html. Attempting basic fix.")
                             # Very basic fix: append missing div
                             missing_divs = html_content.count("<div") - html_content.count("</div>")
                             if missing_divs > 0:
                                 html_content += "</div>" * missing_divs
                                 section["html_content"] = html_content

                return plan
            else:
                print(f"Invalid UI Plan structure: {plan.keys()}")
    except Exception as e:
        print(f"Adaptive UI generation failed: {e}")
    
    return None
