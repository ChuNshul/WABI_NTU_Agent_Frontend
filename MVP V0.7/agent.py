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
        if platform == "web":
            # Web: show two clear action buttons with fallback text
            html = (
                '<div class="p-4" style="background: var(--card-bg);">'
                '<div class="text-sm mb-3" style="color: var(--text-color);">请选择你需要的功能：</div>'
                '<div class="flex gap-2 flex-wrap">'
                '<button class="px-3 py-2 rounded-full border text-sm" '
                'style="background: var(--bg-color); color: var(--text-color); border-color: var(--border-color);" '
                'onclick="document.getElementById(\'userInput\').value=\'我要餐厅推荐\'; sendMessage()">🍽️ 我要餐厅推荐</button>'
                '<button class="px-3 py-2 rounded-full border text-sm" '
                'style="background: var(--bg-color); color: var(--text-color); border-color: var(--border-color);" '
                'onclick="document.getElementById(\'userInput\').value=\'我要食物识别\'; sendMessage()">🔍 我要食物识别</button>'
                '</div>'
                '</div>'
            )
            return {
                "mode": "clarification",
                "summary": "我可以为你提供餐厅推荐或食物识别。",
                "sections": [
                    {
                        "type": "text",
                        "content": "请从下方选择：‘我要餐厅推荐’ 或 ‘我要食物识别’。"
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
            # WeChat / WhatsApp: use text with clear numbered options
            # WhatsApp supports Markdown; WeChat should be plain text (prompt enforces later)
            content = (
                "*请选择你需要的功能：*\n"
                "1) 餐厅推荐（回复：推荐/餐厅）\n"
                "2) 食物识别（回复：识别/图片）\n"
                "提示：直接回复对应数字或关键词即可开始。"
            )
            return {
                "mode": "clarification",
                "summary": "你的需求不太明确，我来帮你选择方向。",
                "sections": [
                    { "type": "text", "content": content }
                ],
                "suggestions": []
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
        "chat_history_summary": history_str
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
