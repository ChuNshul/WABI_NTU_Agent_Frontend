import os
import sys
import uvicorn
import asyncio
import json
from typing import List, Dict, Any, Optional, Union
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

# Import Core Agent Logic
from langgraph_app.orchestrator.state import GraphState
from langgraph_app.agents.UI.agent import generate_ui_plan

# Import Mock Data for Fallback/Simulation
try:
    from .mock_data import (
        MOCK_RECOGNITION_RESULT, 
        MOCK_RECOMMENDATION_TABLE_RESULT,
        MOCK_GUARDRAIL_RESULT,
        MOCK_USER_HISTORY
    )
except ImportError:
    from langgraph_app.agents.UI.mock_data import (
        MOCK_RECOGNITION_RESULT, 
        MOCK_RECOMMENDATION_TABLE_RESULT,
        MOCK_GUARDRAIL_RESULT,
        MOCK_USER_HISTORY
    )

# Set Mock Mode to False to use the Real UI Agent
MOCK_MODE = False
MOCK_STATE = {
    "is_corrected": False,
    "chat_history": [] # Store history in memory for demo
}

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: Union[str, List[Dict[str, Any]]]
    patient_id: Optional[str] = "demo_user"
    language: Optional[str] = "Chinese"
    device_info: Optional[str] = None # 'mobile', 'tablet', 'desktop'
    platform: Optional[str] = "web" # 'web', 'wechat', 'whatsapp'

def _truncate_log(data: Any, max_len: int = 100) -> Any:
    """Helper to truncate long strings/lists/dicts for logging"""
    if isinstance(data, str):
        if len(data) > max_len:
            return data[:max_len] + "..."
        return data
    elif isinstance(data, list):
        return [_truncate_log(x, max_len) for x in data]
    elif isinstance(data, dict):
        return {k: _truncate_log(v, max_len) for k, v in data.items()}
    return data

async def ui_generator(request: ChatRequest):
    """Async generator to stream progress and final result"""
    print(f"Received request: {_truncate_log(request.message)}")
    print(f"Device Info: {request.device_info}")
    print(f"Target Platform: {request.platform}")
    
    # 1. Processing Start
    yield json.dumps({"type": "progress", "step": "Initializing Request...", "progress": 10}) + "\n"
    await asyncio.sleep(0.5) 
    
    # Extract text and check for image
    msg_content = request.message
    text_content = ""
    is_image = False
    
    if isinstance(msg_content, str):
        text_content = msg_content
    elif isinstance(msg_content, list):
        for item in msg_content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_content += item.get("text", "")
                elif item.get("type") == "image_url" or "image" in item:
                    is_image = True
    
    # Add User Message to History
    MOCK_STATE["chat_history"].append(HumanMessage(content=text_content))

    # Prepare GraphState
    lang_instruction = f" (Please generate the UI plan in {request.language})"
    if request.device_info == 'mobile':
        lang_instruction += " (User is on Mobile. Keep text concise and avoid wide tables.)"
    
    state = GraphState(
        user_input=text_content + lang_instruction, # Dynamic language instruction
        patient_id=request.patient_id,
        has_image=is_image,
        chat_history=MOCK_STATE["chat_history"][-10:] # Pass last 10 messages
    )
    # Dynamically attach platform context to state instance
    # This avoids modifying the global GraphState definition
    state.platform = request.platform
    
    # 2. Intent Analysis
    yield json.dumps({"type": "progress", "step": "Analyzing Intent...", "progress": 30}) + "\n"
    await asyncio.sleep(0.5)

    # Simple Intent Simulation for Demo Purposes
    text_lower = text_content.lower()
    
    if is_image or "identify" in text_lower or "what is this" in text_lower:
        # Simulate Recognition Scenario
        state.intent = "recognition"
        state.agent_response = MOCK_RECOGNITION_RESULT["agent_response"]
        state.nutrition_facts = MOCK_RECOGNITION_RESULT["nutrition_facts"]
        state.food_detection_json = MOCK_RECOGNITION_RESULT.get("food_detection_json")
        
    elif "recommend" in text_lower or "restaurant" in text_lower or "hungry" in text_lower or "food" in text_lower or "餐厅" in text_lower:
        # Simulate Recommendation Scenario
        state.intent = "recommendation"
        state.agent_response = MOCK_RECOMMENDATION_TABLE_RESULT["agent_response"]
        state.recommended_restaurants = MOCK_RECOMMENDATION_TABLE_RESULT["recommended_restaurants"]
    
    elif any(k in text_lower for k in [
        "unclear", "not clear", "not sure", "unsure", "confused", "no clear", 
        "don't know", "do not know", "what do you do",
        "不清楚", "不明确", "不太明确", "不确定", "不太确定", "不明白", "不知道", "不太清楚", "迷惑", "看不懂"
    ]):
        # Clarification Scenario: user intent is ambiguous
        state.intent = "clarification"
        state.agent_response = (
            "我可以帮助你进行两类操作：\n"
            "1) 推荐附近更健康的餐饮选择\n"
            "2) 识别食物并给出营养信息\n\n"
            "请选择你需要的功能。"
        )
    
    elif "die" in text_lower or "kill" in text_lower or "suicide" in text_lower:
        # Simulate Guardrail Scenario
        state.intent = "guardrail"
        state.agent_response = MOCK_GUARDRAIL_RESULT["agent_response"]
        
        # Inject context from mock data so Adaptive UI Agent knows the resources
        if "ui_plan" in MOCK_GUARDRAIL_RESULT:
            sections = MOCK_GUARDRAIL_RESULT["ui_plan"].get("sections", [])
            for sec in sections:
                if sec["type"] == "key_value_list":
                    items = sec.get("items", [])
                    resource_text = "\n\nAvailable Resources:\n" + "\n".join([f"- {i['label']}: {i['value']}" for i in items])
                    state.agent_response += resource_text
                    break
                    
    elif any(k in text_lower for k in ["wrong", "mistake", "incorrect", "error", "错误", "不对", "不准"]):
        # Simulate Correction Scenario
        state.intent = "correction"
        state.agent_response = "I apologize for the error. Could you please correct me? I am always learning."

    elif any(k in text_lower for k in ["目标", "目标设定", "设定目标", "规划", "计划", "goal", "target", "set goal", "plan"]):
        state.intent = "goal_planning"
        state.user_history = MOCK_USER_HISTORY
        state.agent_response = "我会根据你最近的饮食历史，帮你设定下周的饮食目标并给出可执行的建议。"

    else:
        # Generic / Chat / Follow-up
        state.intent = "generic"
        
        # Simple heuristic: if previous turn was recognition, carry over context
        if len(MOCK_STATE["chat_history"]) > 2:
             state.nutrition_facts = MOCK_RECOGNITION_RESULT["nutrition_facts"] # Mock retrieval
             if any(k in text_lower for k in ["sort", "price", "dist", "cheap", "expensive", "near", "排序", "价格", "距离", "便宜", "贵"]):
                 state.recommended_restaurants = MOCK_RECOMMENDATION_TABLE_RESULT["recommended_restaurants"]
             
        state.agent_response = "I see. Let me help you with that based on the food we just discussed."
    
    # 3. Guardrails & Context
    yield json.dumps({"type": "progress", "step": f"Intent Detected: {state.intent}", "progress": 50}) + "\n"
    await asyncio.sleep(0.3)
    yield json.dumps({"type": "progress", "step": "Checking Guardrails & Context...", "progress": 60}) + "\n"
    await asyncio.sleep(0.3)

    # --- EXECUTE REAL UI AGENT ---
    try:
        print(f"Invoking UI Agent with Intent: {state.intent}")
        yield json.dumps({"type": "progress", "step": "Generating Adaptive UI...", "progress": 80}) + "\n"
        
        # Run synchronous agent code in thread pool to avoid blocking
        final_state = await asyncio.to_thread(generate_ui_plan, state)
        
        # Add AI Response to History
        if final_state.ui_plan:
             # Handle both dict and list formats for ui_plan
             if isinstance(final_state.ui_plan, dict):
                 summary = final_state.ui_plan.get("summary", "Here is the info.")
             else:
                 summary = "Here is the info."
                 
             MOCK_STATE["chat_history"].append(AIMessage(content=summary))
             
             # Direct Output (LLM handles adaptation)
             yield json.dumps({"type": "result", "web_ui_plan": final_state.ui_plan}) + "\n"
        else:
            yield json.dumps({"type": "error", "error": "UI Agent returned no plan"}) + "\n"
            
    except Exception as e:
        print(f"Error in UI Agent: {e}")
        yield json.dumps({"type": "error", "error": str(e)}) + "\n"

@app.post("/api/ui")
async def get_ui_response(request: ChatRequest):
    return StreamingResponse(ui_generator(request), media_type="application/x-ndjson")

@app.post("/api/reset")
async def reset_state():
    MOCK_STATE["is_corrected"] = False
    MOCK_STATE["chat_history"] = []
    return JSONResponse(content={"status": "success", "message": "State reset"})

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wabi Agent - UI Demo (Adaptive)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --sidebar-width: 280px;
            --primary-color: #2563eb;
            --primary-hover: #1d4ed8;
            --bg-color: #f3f4f6;
            --sidebar-bg: #1f2937;
            --text-color: #1f2937;
            --text-secondary: #6b7280;
            --card-bg: #ffffff;
            --border-color: #e5e7eb;
            --font-size-base: 16px;
        }

        /* Themes */
        .theme-care {
            --primary-color: #d97706;
            --primary-hover: #b45309;
            --bg-color: #fff7ed;
            --sidebar-bg: #78350f;
            --text-color: #000000;
            --text-secondary: #431407;
            --card-bg: #ffffff;
            --border-color: #fed7aa;
            --font-size-base: 20px;
        }
        .theme-youth {
            --primary-color: #059669;
            --primary-hover: #047857;
            --bg-color: #f0fdf4;
            --sidebar-bg: #064e3b;
            --text-color: #064e3b;
            --text-secondary: #065f46;
            --card-bg: #ffffff;
            --border-color: #a7f3d0;
        }

        /* Platform Preview Styles */
        .platform-wechat {
            --bg-color: #ededed;
            --card-bg: #f5f5f5; /* Sidebar becomes grey */
            --border-color: #dcdcdc;
        }
        .platform-wechat .message-bubble {
            border-radius: 4px;
            box-shadow: none;
            font-size: 15px;
        }
        .platform-wechat .user-message .message-bubble {
            background: #95ec69; /* WeChat Green */
            color: #000;
        }
        .platform-wechat .user-message .message-bubble * { color: #000; }
        .platform-wechat .ai-message .message-bubble {
            background: #ffffff;
        }
        .platform-wechat .header { background: #ededed; border-bottom: 1px solid #dcdcdc; }
        .platform-wechat .input-wrapper { background: #f7f7f7; border-top: 1px solid #dcdcdc; }
        .platform-wechat .input-box { background: #ffffff; border-radius: 4px; }

        .platform-whatsapp {
            --bg-color: #efeae2; /* WhatsApp Wallpaper color approx */
            --card-bg: #ffffff;
            --primary-color: #00a884;
        }
        .platform-whatsapp .chat-history {
            background-image: url("https://user-images.githubusercontent.com/15075759/28719144-86dc0f70-73b1-11e7-911d-60d70fcded21.png");
            background-repeat: repeat;
            background-size: 400px;
        }
        .platform-whatsapp .message-bubble {
            border-radius: 8px;
            box-shadow: 0 1px 0.5px rgba(0,0,0,0.13);
            font-size: 14.2px;
        }
        .platform-whatsapp .user-message .message-bubble {
            background: #d9fdd3; /* WhatsApp Green Bubble */
            color: #111b21;
        }
        .platform-whatsapp .user-message .message-bubble * { color: #111b21; }
        .platform-whatsapp .ai-message .message-bubble {
            background: #ffffff;
        }
        
        /* WhatsApp Rich Markdown Styles */
        .platform-whatsapp .markdown-content table { 
            border-collapse: collapse !important; 
            width: 100%; 
            margin: 10px 0; 
            font-size: 0.9em; 
            display: table !important; /* Force table display */
        }
        .platform-whatsapp .markdown-content th, 
        .platform-whatsapp .markdown-content td { 
            border: 1px solid #d1d5db !important; /* Visible gray border */
            padding: 8px !important; 
            text-align: left; 
        }
        .platform-whatsapp .markdown-content th { 
            background-color: #f3f4f6 !important; 
            font-weight: 700 !important; 
        }
        .platform-whatsapp .markdown-content tr:nth-child(even) {
            background-color: #f9fafb;
        }
        .platform-whatsapp .markdown-content blockquote { border-left: 4px solid #00a884; margin: 10px 0; padding-left: 10px; color: #555; background: rgba(0,0,0,0.02); font-style: italic; }
        .platform-whatsapp .markdown-content h1, .platform-whatsapp .markdown-content h2, .platform-whatsapp .markdown-content h3 { font-weight: bold; margin-top: 12px; margin-bottom: 6px; color: #00a884; }
        .platform-whatsapp .markdown-content code { background: rgba(0,0,0,0.05); padding: 2px 4px; border-radius: 3px; font-family: monospace; font-size: 0.9em; }
        .platform-whatsapp .markdown-content pre { background: rgba(0,0,0,0.05); padding: 10px; border-radius: 6px; overflow-x: auto; }

        body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: var(--font-size-base); color: var(--text-color); background: var(--bg-color); transition: background 0.3s, color 0.3s; }
        
        /* Layout */
        .app-container { display: flex; height: 100vh; background: var(--bg-color); }
        
        /* Sidebar */
        .sidebar {
            width: var(--sidebar-width);
            background: var(--sidebar-bg);
            color: white;
            display: flex;
            flex-direction: column;
            padding: 20px;
            box-shadow: 2px 0 5px rgba(0,0,0,0.1);
            transition: background 0.3s;
        }
        .logo-area { font-size: 24px; font-weight: bold; margin-bottom: 30px; display: flex; align-items: center; gap: 10px; }
        .nav-item { padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 10px; }
        .nav-item:hover { background: rgba(255,255,255,0.1); }
        .nav-item.active { background: var(--primary-color); }
        .nav-icon { width: 20px; height: 20px; }
        
        /* Main Chat Area */
        .main-content { flex: 1; display: flex; flex-direction: column; position: relative; }
        
        /* Header */
        .header { background: var(--card-bg); padding: 15px 30px; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; transition: background 0.3s, border-color 0.3s; position: relative; z-index: 30; }
        .header-title { font-size: 1.125rem; font-weight: 600; color: var(--text-color); }
        .status-badge { font-size: 0.75rem; padding: 4px 12px; border-radius: 12px; background: rgba(37,99,235,0.1); color: var(--primary-color); }

        .chat-history { flex: 1; overflow-y: auto; padding: 30px; display: flex; flex-direction: column; gap: 24px; scroll-behavior: smooth; }
        
        /* Message Styles */
        .message-group { position: relative; }
        .ai-message-container { display: flex; gap: 16px; max-width: 85%; animation: fadeIn 0.3s ease; }
        .user-message-container { display: flex; justify-content: flex-end; align-items: center; margin-bottom: 10px; animation: fadeIn 0.3s ease; position: relative; }
        
        /* Delete & Favorite Button */
        .msg-actions {
            opacity: 0;
            transition: all 0.2s;
            display: flex;
            gap: 4px;
            margin-right: 8px; /* Space between actions and bubble */
        }
        .message-group:hover .msg-actions { opacity: 1; }
    
        .user-message .msg-actions { 
             order: -1;
             margin-right: 8px;
        }
        .ai-message .msg-actions { display: none; }

        .action-btn {
            cursor: pointer;
            color: var(--text-secondary);
            padding: 6px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px; height: 28px;
        }
        .action-btn:hover { color: var(--primary-color); background-color: rgba(0,0,0,0.05); }
        .delete-btn:hover { color: #ef4444; background-color: rgba(239,68,68,0.1); }
        
        .avatar {
            width: 36px; height: 36px; border-radius: 50%; 
            display: flex; align-items: center; justify-content: center;
            font-weight: bold; font-size: 14px; flex-shrink: 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .avatar.ai { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; }
        .avatar.user { background: var(--border-color); color: var(--text-secondary); }
        
        .message-bubble {
            padding: 16px 20px; border-radius: 16px; line-height: 1.6;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05); position: relative;
        }
        .ai-message .message-bubble { background: var(--card-bg); border-top-left-radius: 4px; color: var(--text-color); }
        .user-message .message-bubble { background: var(--primary-color); color: #ffffff; border-top-right-radius: 4px; }
        
        /* Ensure text inside bubbles inherits theme colors correctly */
        .ai-message .message-bubble * { color: inherit; }
        /* User bubble text should always be white/light for contrast against primary color */
        .user-message .message-bubble * { color: #ffffff; }

        /* Input Area */
        .input-wrapper { background: var(--card-bg); padding: 20px; border-top: 1px solid var(--border-color); transition: background 0.3s, border-color 0.3s; }
        .input-box { 
            max-width: 900px; margin: 0 auto; background: var(--card-bg); 
            border: 1px solid var(--border-color); border-radius: 24px; 
            padding: 8px 16px; display: flex; gap: 12px; align-items: center;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            transition: box-shadow 0.2s, background 0.3s, border-color 0.3s;
        }
        .input-box:focus-within { box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-color: var(--primary-color); }
        
        textarea {
            width: 100%; border: none; resize: none; outline: none; max-height: 120px; overflow-y: auto;
            padding: 8px 0; font-size: inherit; line-height: 1.5; background: transparent; color: var(--text-color);
        }
        textarea::-webkit-resizer { display: none; }
        textarea::-webkit-scrollbar { width: 4px; }
        textarea::-webkit-scrollbar-thumb { background-color: rgba(0,0,0,0.1); border-radius: 4px; }
        
        /* Circular Send Button */
        #sendBtn {
            width: 40px; height: 40px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0; padding: 0;
        }

        /* Settings Card */
        .theme-card {
            border: 2px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.2s;
            background: var(--card-bg);
            color: var(--text-color);
        }
        .theme-card:hover { border-color: var(--primary-color); transform: translateY(-2px); }
        .theme-card.active { border-color: var(--primary-color); background: rgba(37,99,235,0.05); box-shadow: 0 0 0 2px var(--primary-color); }
        .theme-preview { height: 40px; border-radius: 8px; margin-bottom: 12px; display: flex; gap: 4px; padding: 4px; background: #eee; }
        .tp-sidebar { width: 20%; height: 100%; border-radius: 4px; }
        .tp-main { flex: 1; height: 100%; border-radius: 4px; display: flex; flex-direction: column; gap: 4px; padding: 4px; }
        .tp-bubble { height: 8px; width: 60%; border-radius: 4px; }

        /* Animations */
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Process Steps */
        .process-steps { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-color); }
        .step-item { display: flex; align-items: center; gap: 8px; font-size: 0.85em; color: var(--text-secondary); margin-bottom: 6px; }
        .step-icon { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--border-color); }
        .step-item.active .step-icon { border-color: var(--primary-color); border-top-color: transparent; animation: spin 1s linear infinite; }
        .step-item.done .step-icon { background: #10b981; border-color: #10b981; position: relative; }
        .step-item.done .step-icon::after { content: '✓'; color: white; font-size: 9px; position: absolute; top: -1px; left: 2px; }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        /* Highlight Animation */
        @keyframes highlightPulse {
            0% { background-color: rgba(37, 99, 235, 0.1); }
            50% { background-color: rgba(37, 99, 235, 0.3); }
            100% { background-color: transparent; }
        }
        .highlight-msg { animation: highlightPulse 2s ease-out; }

        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        /* Responsive Design: Mobile (Bottom Nav), Tablet (Rail), Desktop (Sidebar) */
        
        /* Default Desktop Styles (Sidebar already defined above) */

        /* Tablet (640px - 1024px): Navigation Rail */
        @media (min-width: 640px) and (max-width: 1024px) {
            .sidebar {
                width: 80px; /* Slim width */
                align-items: center;
                padding: 20px 10px;
            }
            .logo-area { 
                font-size: 0; /* Hide text */
                margin-bottom: 40px; 
                justify-content: center;
            }
            .nav-item {
                flex-direction: column;
                gap: 4px;
                padding: 12px 4px;
                font-size: 9px; /* Reduced from 10px */
                text-align: center;
                width: 100%;
                overflow: hidden; /* Prevent spill */
            }
            .nav-item span { 
                font-size: 10px; /* Force small text for labels */
                white-space: nowrap; 
                text-overflow: ellipsis; 
                overflow: hidden; 
                max-width: 100%;
            } 
            .nav-item svg { width: 24px; height: 24px; } /* Explicit icon size */
            
            /* Hide footer text */
            .sidebar > div:last-child { display: none; }
        }

        /* Mobile (< 640px): Bottom Navigation */
        .bottom-nav { display: none; } /* Hidden by default */

        @media (max-width: 640px) {
            .sidebar { display: none !important; } /* Completely hide sidebar */
            .sidebar-overlay { display: none !important; } /* No overlay needed */
            
            .app-container { flex-direction: column; }
            
            .main-content {
                height: calc(100vh - 60px); /* Leave space for bottom nav */
            }

            .bottom-nav {
                display: flex;
                position: fixed;
                bottom: 0; left: 0; right: 0;
                height: 64px; /* Increased height */
                background: var(--card-bg);
                border-top: 1px solid var(--border-color);
                z-index: 50;
                justify-content: space-around;
                align-items: center;
                padding-bottom: env(safe-area-inset-bottom);
                box-shadow: 0 -2px 10px rgba(0,0,0,0.05); /* Soft shadow */
            }
            
            .bn-item {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: var(--text-secondary);
                font-size: 10px; /* Reduced from 11px */
                gap: 4px; /* More spacing */
                transition: all 0.2s;
                position: relative;
            }
            .bn-item span { font-size: 10px; } /* Label size */
            .bn-item svg { width: 22px; height: 22px; transition: transform 0.2s; }
            
            .bn-item.active { 
                color: var(--primary-color); 
                font-weight: 600;
            }
            .bn-item.active svg {
                transform: translateY(-2px); /* Subtle bounce */
            }
            /* Active indicator line */
            .bn-item.active::after {
                content: '';
                position: absolute;
                top: 0;
                width: 40%;
                height: 3px;
                background: var(--primary-color);
                border-radius: 0 0 4px 4px;
            }
            
            /* Adjust header */
            .header { padding: 10px 16px; }
            .header button.md\\:hidden { display: none; } /* Hide hamburger */
            
            /* Adjust input area to not overlap bottom nav */
            .input-wrapper {
                padding: 10px;
                padding-bottom: 74px; /* Ensure input isn't hidden by bottom nav (64px + 10px) */
            }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar Overlay (Mobile) -->
        <div class="sidebar-overlay hidden fixed inset-0 bg-black/50 z-40 transition-opacity" onclick="toggleSidebar()"></div>

        <!-- Sidebar -->
        <div class="sidebar" id="appSidebar">
            <div class="logo-area">
                <div style="width:32px;height:32px;background:#3b82f6;border-radius:8px;"></div>
                WABI Agent
            </div>
            
            <div class="nav-item active" onclick="switchView('chat')">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                <span>Chat</span>
            </div>
            <div class="nav-item" onclick="switchView('favorites')">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                <span>Favorites</span>
            </div>
            <div class="nav-item" onclick="switchView('settings')">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                <span>Settings</span>
            </div>
            
            <div style="margin-top:auto; font-size:12px; color:rgba(255,255,255,0.5);">
                v0.8 (Adaptive)<br>Project Wabi-C
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="header">
                <div class="flex items-center gap-3">
                    <button class="md:hidden text-gray-500 hover:text-blue-600 transition" onclick="toggleSidebar()">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
                    </button>
                    <div class="header-title">Food Recognition & Recommendation</div>
                </div>
                <div class="flex items-center gap-4">
                    <div class="relative z-50">
                        <button id="platformMenuButton" onclick="togglePlatformMenu()" class="flex items-center gap-2 text-sm bg-transparent border border-gray-300 rounded-lg px-3 py-1 focus:outline-none hover:border-blue-500">
                            <span id="platformMenuIcon" class="inline-flex items-center">
                                <svg id="platformIconSvg" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                            </span>
                            <span id="platformMenuLabel">Web Preview</span>
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                        </button>
                        <div id="platformMenuList" class="absolute right-0 mt-2 w-44 bg-white border border-gray-200 rounded-md shadow-xl hidden z-50 pointer-events-auto">
                            <button onclick="selectPlatform('web')" class="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                                <span id="platformOptionWeb">Web Preview</span>
                            </button>
                            <button onclick="selectPlatform('wechat')" class="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                                <span id="platformOptionWeChat">WeChat</span>
                            </button>
                            <button onclick="selectPlatform('whatsapp')" class="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92V19a2 2 0 0 1-2 2h-4l-4 3v-3H6a2 2 0 0 1-2-2v-2"></path><path d="M2 6V5a2 2 0 0 1 2-2h4l4-3v3h6a2 2 0 0 1 2 2v1"></path><path d="M22 8v8"></path><path d="M2 16V8"></path></svg>
                                <span id="platformOptionWhatsApp">WhatsApp</span>
                            </button>
                        </div>
                    </div>
                    <button id="clearChatBtn" onclick="resetChat()" class="text-sm text-red-500 hover:text-red-700 flex items-center gap-1 font-medium px-3 py-1 rounded-lg hover:bg-red-50 transition">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
                        Clear Chat
                    </button>
                    <div class="status-badge">● Online</div>
                </div>
            </div>

            <div class="chat-history" id="chatHistory">
                <!-- Welcome Message -->
                <div class="ai-message-container">
                    <div class="avatar ai">AI</div>
                    <div class="message-bubble">
                        你好！我是 Wabi。我可以帮你识别食物热量或推荐附近的健康餐厅。<br>Hello! I'm Wabi. How can I help you?
                    </div>
                </div>
            </div>

            <!-- Favorites View (Hidden by default) -->
            <div id="favoritesView" class="hidden flex-1 overflow-y-auto p-8">
                <h2 class="text-2xl font-bold mb-6 flex items-center gap-2" style="color: var(--text-color);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-red-500"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg> 
                    <span>Saved Favorites</span>
                </h2>
                
                <div class="mb-8">
                    <h3 class="text-lg font-semibold mb-4 border-b pb-2" style="color: var(--text-color); border-color: var(--border-color);">Conversations (Q&A)</h3>
                    <div id="fav-qa" class="grid grid-cols-1 gap-4">
                        <p id="emptyStateText" class="text-sm" style="color: var(--text-secondary);">No saved conversations yet.</p>
                    </div>
                </div>
            </div>

            <!-- Settings View (Hidden by default) -->
            <div id="settingsView" class="hidden flex-1 overflow-y-auto p-8">
                <h2 class="text-2xl font-bold mb-6 flex items-center gap-2" style="color: var(--text-color);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-500"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                    <span>Settings</span>
                </h2>

                <div class="mb-8">
                    <h3 class="text-lg font-semibold mb-4 border-b pb-2" style="color: var(--text-color); border-color: var(--border-color);">Language / 语言</h3>
                    <div class="flex gap-4">
                        <button onclick="setLanguage('Chinese')" id="lang-Chinese" class="px-4 py-2 rounded-lg border transition hover:bg-gray-100" style="border-color: var(--border-color); color: var(--text-color);">中文 (Chinese)</button>
                        <button onclick="setLanguage('English')" id="lang-English" class="px-4 py-2 rounded-lg border transition hover:bg-gray-100" style="border-color: var(--border-color); color: var(--text-color);">English</button>
                    </div>
                </div>

                <div class="mb-8" id="themeSection">
                    <h3 class="text-lg font-semibold mb-4 border-b pb-2" style="color: var(--text-color); border-color: var(--border-color);">Appearance & Theme</h3>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <!-- Standard Theme -->
                        <div class="theme-card active" onclick="setTheme('standard')" id="theme-standard">
                            <div class="theme-preview">
                                <div class="tp-sidebar" style="background:#1f2937"></div>
                                <div class="tp-main" style="background:#f3f4f6">
                                    <div class="tp-bubble" style="background:#2563eb"></div>
                                    <div class="tp-bubble" style="background:#fff; width:40%; align-self:flex-end"></div>
                                </div>
                            </div>
                            <div class="font-bold mb-1">Standard</div>
                            <div id="theme-desc-standard" class="text-xs opacity-70">Default blue & gray theme.</div>
                        </div>

                        <!-- Care Mode -->
                        <div class="theme-card" onclick="setTheme('care')" id="theme-care">
                            <div class="theme-preview">
                                <div class="tp-sidebar" style="background:#78350f"></div>
                                <div class="tp-main" style="background:#fff7ed">
                                    <div class="tp-bubble" style="background:#d97706"></div>
                                    <div class="tp-bubble" style="background:#fff; width:40%; align-self:flex-end"></div>
                                </div>
                            </div>
                            <div class="font-bold mb-1">Care Mode</div>
                            <div id="theme-desc-care" class="text-xs opacity-70">High contrast & larger text.</div>
                        </div>

                        <!-- Youth Mode -->
                        <div class="theme-card" onclick="setTheme('youth')" id="theme-youth">
                            <div class="theme-preview">
                                <div class="tp-sidebar" style="background:#064e3b"></div>
                                <div class="tp-main" style="background:#f0fdf4">
                                    <div class="tp-bubble" style="background:#059669"></div>
                                    <div class="tp-bubble" style="background:#fff; width:40%; align-self:flex-end"></div>
                                </div>
                            </div>
                            <div class="font-bold mb-1">Youth Mode</div>
                            <div id="theme-desc-youth" class="text-xs opacity-70">Fresh green & protective.</div>
                        </div>
                    </div>
                </div>

                <div class="mb-8">
                    <h3 class="text-lg font-semibold mb-4 border-b pb-2" style="color: var(--text-color); border-color: var(--border-color);">About</h3>
                    <div class="p-4 rounded-xl border" style="background: var(--card-bg); border-color: var(--border-color);">
                        <p class="mb-2"><strong>WABI Agent Web Demo</strong></p>
                        <p class="text-sm opacity-70">Version: 0.8 (Adaptive UI)</p>
                        <p class="text-sm opacity-70">Powered by Linhan Song</p>
                        <p class="text-sm opacity-70 mt-2 border-t pt-2" style="border-color: var(--border-color);">Detected Device: <span id="debug-device" class="font-mono font-bold">Unknown</span></p>
                    </div>
                </div>
            </div>

            <div class="input-wrapper" id="inputArea">
                <div id="imagePreview" class="hidden max-w-[900px] mx-auto mb-2 pl-2">
                    <div class="relative inline-block">
                        <img id="previewImg" src="" class="h-16 rounded-lg border border-gray-200 shadow-sm object-cover">
                        <button onclick="clearImage()" class="absolute -top-2 -right-2 bg-gray-800 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs shadow-md hover:bg-black transition border-2 border-white">×</button>
                    </div>
                </div>
                
                <div class="input-box">
                    <button onclick="document.getElementById('fileInput').click()" class="p-2 text-gray-400 hover:text-blue-600 transition rounded-lg hover:bg-gray-50">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
                    </button>
                    <input type="file" id="fileInput" accept="image/*" class="hidden" onchange="handleFileSelect(this)">
                    
                    <textarea id="userInput" rows="1" placeholder="输入消息或上传食物图片..." oninput="autoResize(this)" onkeypress="handleKeyPress(event)"></textarea>
                    
                    <button id="sendBtn" onclick="sendMessage()" class="bg-blue-600 text-white rounded-full hover:bg-blue-700 transition shadow-sm">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </div>
                <div class="text-center text-xs text-gray-400 mt-2">Wabi AI may produce inaccurate information. Please verify.</div>
            </div>
        </div>

        <!-- Bottom Navigation (Mobile Only) -->
        <div class="bottom-nav">
            <div class="bn-item active" onclick="switchView('chat')">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                <span>Chat</span>
            </div>
            <div class="bn-item" onclick="switchView('favorites')">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                <span>Favorites</span>
            </div>
            <div class="bn-item" onclick="switchView('settings')">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                <span>Settings</span>
            </div>
        </div>
    </div>

    <script>
        let currentImageBase64 = null;
        let placeTableData = []; 
        let currentPlatform = 'web';

        // Language Resources
        const LANG_RESOURCES = {
            'Chinese': {
                'title': '食物识别与推荐',
                'nav_chat': '聊天界面',
                'nav_fav': '收藏夹',
                'nav_settings': '设置',
                'nav_chat_short': '聊天',
                'nav_fav_short': '收藏',
                'nav_settings_short': '设置',
                'placeholder': '输入消息或上传食物图片...',
                'welcome': "你好！我是 Wabi。我可以帮你识别食物热量或推荐附近的健康餐厅。",
                'clear_chat': '清空聊天',
                'online': '在线',
                'saved_fav': '已保存的收藏',
                'conv_qa': '对话记录（问答）',
                'no_saved': '暂无保存的对话。',
                'settings_title': '设置',
                'lang_title': '语言设置',
                'theme_title': '外观与主题',
                'theme_standard_desc': '默认蓝灰主题。',
                'theme_care_desc': '高对比度与大字体。',
                'theme_youth_desc': '清新绿色与护眼。',
                'about_title': '关于',
                'disclaimer': 'Wabi AI 可能提供不准确的信息，请自行核实。',
                'detected_device': '检测到设备：',
                'platform_web': 'Web 预览',
                'platform_wechat': '微信',
                'platform_whatsapp': 'WhatsApp'
            },
            'English': {
                'title': 'Food Recognition & Recommendation',
                'nav_chat': 'Chat Interface',
                'nav_fav': 'Favorites',
                'nav_settings': 'Settings',
                'nav_chat_short': 'Chat',
                'nav_fav_short': 'Favorites',
                'nav_settings_short': 'Settings',
                'placeholder': 'Type a message or upload food image...',
                'welcome': "Hello! I'm Wabi. I can help you identify food calories or recommend healthy restaurants nearby.",
                'clear_chat': 'Clear Chat',
                'online': 'Online',
                'saved_fav': 'Saved Favorites',
                'conv_qa': 'Conversations (Q&A)',
                'no_saved': 'No saved conversations yet.',
                'settings_title': 'Settings',
                'lang_title': 'Language',
                'theme_title': 'Appearance & Theme',
                'theme_standard_desc': 'Default blue & gray theme.',
                'theme_care_desc': 'High contrast & larger text.',
                'theme_youth_desc': 'Fresh green & protective.',
                'about_title': 'About',
                'disclaimer': 'Wabi AI may produce inaccurate information. Please verify.',
                'detected_device': 'Detected Device:',
                'platform_web': 'Web Preview',
                'platform_wechat': 'WeChat',
                'platform_whatsapp': 'WhatsApp'
            }
        };

        let chatState = [
             {
                id: 'welcome-msg',
                role: 'ai',
                content: LANG_RESOURCES['Chinese']['welcome']
            }
        ];

        let favorites = { qa: [] };

        function setPlatform(platform) {
            currentPlatform = platform;
            document.body.classList.remove('platform-wechat', 'platform-whatsapp');
            
            // Handle Theme Setting Visibility/Availability
            const themeSection = document.getElementById('themeSection');
            
            if (platform !== 'web') {
                document.body.classList.add(`platform-${platform}`);
                // Disable Theme Settings in WeChat/WhatsApp mode
                if(themeSection) {
                    themeSection.style.opacity = '0.5';
                    themeSection.style.pointerEvents = 'none';
                }
                // Force standard theme to avoid conflicts with platform styles
                setTheme('standard');
            } else {
                // Enable Theme Settings in Web mode
                if(themeSection) {
                    themeSection.style.opacity = '1';
                    themeSection.style.pointerEvents = 'auto';
                }
            }
            
            // Auto clear chat when switching platforms
            resetChat();
            updatePlatformMenuLabel();
        }

        // Initialize Theme (Always default to standard)
        setTheme('standard');
        
        // Initialize Language (Default to Chinese)
        let currentLang = 'Chinese';
        setLanguage('Chinese');

        // Initial device check
        updateDebugDevice();
        window.addEventListener('resize', updateDebugDevice);

        function updateDebugDevice() {
            const dev = getDeviceInfo();
            const el = document.getElementById('debug-device');
            if(el) el.textContent = dev.charAt(0).toUpperCase() + dev.slice(1);
            
            // Also ensure correct view mode (e.g. if switching from mobile to desktop, ensure sidebar is visible)
            if (dev !== 'mobile') {
                const sidebar = document.getElementById('appSidebar');
                if (sidebar) sidebar.style.display = ''; // Reset inline display style if any
            }
        }

        function toggleSidebar() {
            const sidebar = document.getElementById('appSidebar');
            const overlay = document.querySelector('.sidebar-overlay');
            sidebar.classList.toggle('open');
            if (sidebar.classList.contains('open')) {
                overlay.classList.remove('hidden');
            } else {
                overlay.classList.add('hidden');
            }
        }

        function setLanguage(lang) {
            currentLang = lang;
            document.querySelectorAll('[id^="lang-"]').forEach(el => {
                el.classList.remove('bg-blue-100', 'border-blue-500', 'text-blue-700');
                el.style.backgroundColor = '';
                el.style.borderColor = 'var(--border-color)';
            });
            const activeBtn = document.getElementById(`lang-${lang}`);
            if (activeBtn) {
                activeBtn.classList.add('bg-blue-100', 'border-blue-500', 'text-blue-700');
                activeBtn.style.backgroundColor = 'rgba(37,99,235,0.1)';
                activeBtn.style.borderColor = 'var(--primary-color)';
            }
            updateStaticText(lang);
            updatePlatformMenuLabel();
        }

        function updateStaticText(lang) {
            const res = LANG_RESOURCES[lang];
            if (!res) return;

            // Header & Sidebar
            document.querySelector('.header-title').textContent = res.title;
            const navSpans = document.querySelectorAll('.nav-item span');
            if(navSpans.length >= 3) {
                navSpans[0].textContent = res.nav_chat;
                navSpans[1].textContent = res.nav_fav;
                navSpans[2].textContent = res.nav_settings;
            }
            
            // Bottom Nav
            const bnSpans = document.querySelectorAll('.bn-item span');
            if(bnSpans.length >= 3) {
                bnSpans[0].textContent = res.nav_chat_short;
                bnSpans[1].textContent = res.nav_fav_short;
                bnSpans[2].textContent = res.nav_settings_short;
            }

            // Input
            document.getElementById('userInput').placeholder = res.placeholder;
            
            // Clear Chat Button
            const clearBtn = document.getElementById('clearChatBtn');
            if(clearBtn) {
                clearBtn.innerHTML = clearBtn.innerHTML.split('</svg>')[0] + '</svg> ' + res.clear_chat;
            }
            
            // Status
            document.querySelector('.status-badge').textContent = '● ' + res.online;
            
            // Titles
            const favTitle = document.querySelector('#favoritesView h2 span');
            if(favTitle) favTitle.textContent = res.saved_fav;
            
            const emptyState = document.getElementById('emptyStateText');
            if(emptyState) emptyState.textContent = res.no_saved;
            
            const settingsTitle = document.querySelector('#settingsView h2 span');
            if(settingsTitle) settingsTitle.textContent = res.settings_title;
            
            const h3s = document.querySelectorAll('#settingsView h3');
            if(h3s.length >= 3) {
                h3s[0].textContent = res.lang_title;
                h3s[1].textContent = res.theme_title;
                h3s[2].textContent = res.about_title;
            }
            
            // Theme Descriptions
            const themeStd = document.getElementById('theme-desc-standard');
            if(themeStd) themeStd.textContent = res.theme_standard_desc;
            
            const themeCare = document.getElementById('theme-desc-care');
            if(themeCare) themeCare.textContent = res.theme_care_desc;
            
            const themeYouth = document.getElementById('theme-desc-youth');
            if(themeYouth) themeYouth.textContent = res.theme_youth_desc;
            
            const qaTitle = document.querySelector('#favoritesView h3');
            if(qaTitle) qaTitle.textContent = res.conv_qa;
            
            // Disclaimer & Debug
            document.querySelector('.text-center.text-xs.text-gray-400').textContent = res.disclaimer;
            
            const debugP = document.querySelector('#settingsView p:last-child');
            if(debugP) {
                const debugSpan = debugP.querySelector('span');
                debugP.innerHTML = res.detected_device + ' ';
                if(debugSpan) debugP.appendChild(debugSpan);
            }

            // Update Welcome Message if it exists and hasn't been modified (simple check by ID)
            const welcomeMsg = chatState.find(m => m.id === 'welcome-msg');
            if (welcomeMsg) {
                welcomeMsg.content = res.welcome;
                renderChatHistory(); // Re-render chat to show updated welcome message
            }
        }

        function togglePlatformMenu() {
            const list = document.getElementById('platformMenuList');
            if (!list) return;
            list.classList.toggle('hidden');
        }

        function selectPlatform(p) {
            setPlatform(p);
            const list = document.getElementById('platformMenuList');
            if (list) list.classList.add('hidden');
        }

        function updatePlatformMenuLabel() {
            const res = LANG_RESOURCES[currentLang] || LANG_RESOURCES['English'];
            const labelMap = {
                'web': res.platform_web,
                'wechat': res.platform_wechat,
                'whatsapp': res.platform_whatsapp
            };
            const labelEl = document.getElementById('platformMenuLabel');
            const iconSvg = document.getElementById('platformIconSvg');
            const optWeb = document.getElementById('platformOptionWeb');
            const optWeChat = document.getElementById('platformOptionWeChat');
            const optWhatsApp = document.getElementById('platformOptionWhatsApp');
            if (optWeb) optWeb.textContent = res.platform_web;
            if (optWeChat) optWeChat.textContent = res.platform_wechat;
            if (optWhatsApp) optWhatsApp.textContent = res.platform_whatsapp;
            if (labelEl) labelEl.textContent = labelMap[currentPlatform] || res.platform_web;
            if (iconSvg) {
                if (currentPlatform === 'web') {
                    iconSvg.setAttribute('stroke', '#2563eb');
                    iconSvg.innerHTML = '<circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>';
                } else if (currentPlatform === 'wechat') {
                    iconSvg.setAttribute('stroke', '#10b981');
                    iconSvg.innerHTML = '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>';
                } else {
                    iconSvg.setAttribute('stroke', '#ef4444');
                    iconSvg.innerHTML = '<path d="M22 16.92V19a2 2 0 0 1-2 2h-4l-4 3v-3H6a2 2 0 0 1-2-2v-2"></path><path d="M2 6V5a2 2 0 0 1 2-2h4l4-3v3h6a2 2 0 0 1 2 2v1"></path><path d="M22 8v8"></path><path d="M2 16V8"></path>';
                }
            }
        }

        document.addEventListener('click', function(e) {
            const btn = document.getElementById('platformMenuButton');
            const list = document.getElementById('platformMenuList');
            if (!btn || !list) return;
            if (!btn.contains(e.target) && !list.contains(e.target)) {
                list.classList.add('hidden');
            }
        });

        function setTheme(themeName) {
            document.body.className = ''; // Clear existing
            if (themeName !== 'standard') {
                document.body.classList.add(`theme-${themeName}`);
            }
            // Removed localStorage persistence to ensure standard mode on reload
            
            // Update active state in settings
            document.querySelectorAll('.theme-card').forEach(el => el.classList.remove('active'));
            const activeCard = document.getElementById(`theme-${themeName}`);
            if (activeCard) activeCard.classList.add('active');
        }

        function switchView(viewName) {
            const chatHistory = document.getElementById('chatHistory');
            const favView = document.getElementById('favoritesView');
            const settingsView = document.getElementById('settingsView');
            const inputArea = document.getElementById('inputArea');
            const navItems = document.querySelectorAll('.nav-item');
            const bnItems = document.querySelectorAll('.bn-item'); // Get bottom nav items
            
            navItems.forEach(el => el.classList.remove('active'));
            bnItems.forEach(el => el.classList.remove('active')); // Reset bottom nav
            
            chatHistory.classList.add('hidden');
            favView.classList.add('hidden');
            if(settingsView) settingsView.classList.add('hidden');
            inputArea.classList.add('hidden');

            let index = 0;
            if (viewName === 'chat') {
                chatHistory.classList.remove('hidden');
                inputArea.classList.remove('hidden');
                index = 0;
                setTimeout(() => chatHistory.scrollTop = chatHistory.scrollHeight, 0);
            } else if (viewName === 'favorites') {
                favView.classList.remove('hidden');
                index = 1;
                renderFavorites();
            } else if (viewName === 'settings') {
                if(settingsView) settingsView.classList.remove('hidden');
                index = 2;
            }
            
            // Sync Active State
            if(navItems[index]) navItems[index].classList.add('active');
            if(bnItems[index]) bnItems[index].classList.add('active');

            // Close sidebar on mobile if open (though sidebar is hidden on mobile now, logic kept for safety)
            if (window.innerWidth <= 768) {
                const sidebar = document.getElementById('appSidebar');
                if (sidebar && sidebar.classList.contains('open')) {
                    toggleSidebar();
                }
            }
        }

        
        function scrollToMessage(msgId) {
            switchView('chat');
            setTimeout(() => {
                const el = document.getElementById(msgId);
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    el.classList.add('highlight-msg');
                    setTimeout(() => el.classList.remove('highlight-msg'), 2000);
                } else {
                    alert('Message not found in current session.');
                }
            }, 100);
        }

        function addToFavorites(type, item) {
            if (type === 'qa') {
                if (!favorites.qa.find(q => q.id === item.id)) {
                    favorites.qa.push(item);
                    alert('Conversation saved!');
                } else {
                    alert('Already saved.');
                }
            }
        }

        function saveQAPair(aiMsgId, userMsgId) {
            const aiMsg = chatState.find(m => m.id === aiMsgId);
            const userMsg = chatState.find(m => m.id === userMsgId);
            
            if (aiMsg && userMsg) {
                const qaItem = {
                    id: aiMsgId,
                    userMsgId: userMsgId,
                    question: userMsg.text || "[Image Upload]",
                    answer: aiMsg.plan ? aiMsg.plan.summary : aiMsg.content,
                    timestamp: new Date().toLocaleString()
                };
                addToFavorites('qa', qaItem);
            }
        }

        function addToFavoritesById(id) {
            // Functionality removed for restaurants
            console.log("Restaurant favorites removed.");
        }

        function removeFromFavorites(type, id) {
            if (type === 'qa') {
                favorites.qa = favorites.qa.filter(q => q.id !== id);
            }
            renderFavorites();
        }

        function renderFavorites() {
            const qaContainer = document.getElementById('fav-qa');

            // QA
            if (favorites.qa.length === 0) {
                qaContainer.innerHTML = '<p class="text-gray-400 text-sm">No saved conversations.</p>';
            } else {
                qaContainer.innerHTML = favorites.qa.map(q => `
                    <div class="bg-white border rounded-xl p-4 shadow-sm hover:shadow-md transition relative cursor-pointer" onclick="scrollToMessage('${q.userMsgId}')">
                        <div class="flex justify-between items-start mb-2">
                            <div class="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded">Q: ${q.question}</div>
                            <button onclick="event.stopPropagation(); removeFromFavorites('qa', '${q.id}')" class="text-gray-300 hover:text-red-500 transition flex-shrink-0 ml-2">×</button>
                        </div>
                        <div class="text-sm text-gray-700 pl-2 border-l-2 border-green-200 mb-2">${q.answer}</div>
                        <div class="flex justify-between items-center mt-2">
                            <span class="text-[10px] text-gray-400">${q.timestamp}</span>
                            <span class="text-xs text-blue-500 font-medium hover:underline">View in Chat →</span>
                        </div>
                    </div>
                `).join('');
            }
        }

        function renderPlaceTable(containerId, data) {
            placeTableData = data;
            const container = document.getElementById(containerId);
            if(!container) return;
            updatePlaceTable(containerId);
        }

        function updatePlaceTable(containerId, sortBy = null, filterVeg = false) {
            const container = document.getElementById(containerId);
            if(!container) return;

            let displayData = [...placeTableData];
            const isVegChecked = document.getElementById(`veg-filter-${containerId}`)?.checked || false;
            if (isVegChecked) displayData = displayData.filter(item => item.is_veg);

            const sortVal = document.getElementById(`sort-select-${containerId}`)?.value || 'default';
            if (sortVal === 'price_asc') displayData.sort((a, b) => a.price - b.price);
            else if (sortVal === 'dist_asc') displayData.sort((a, b) => a.dist - b.dist);

            let controlsHtml = `
                <div class="flex flex-wrap items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <div class="flex items-center gap-2">
                        <span class="text-sm text-gray-600 font-medium">Sort:</span>
                        <select id="sort-select-${containerId}" onchange="updatePlaceTable('${containerId}')" class="text-sm border-gray-300 rounded-md p-1 border">
                            <option value="default" ${sortVal === 'default' ? 'selected' : ''}>Default</option>
                            <option value="price_asc" ${sortVal === 'price_asc' ? 'selected' : ''}>Price: Low to High</option>
                            <option value="dist_asc" ${sortVal === 'dist_asc' ? 'selected' : ''}>Distance: Nearest</option>
                        </select>
                    </div>
                    <div class="flex items-center gap-2">
                        <label class="inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="veg-filter-${containerId}" onchange="updatePlaceTable('${containerId}')" class="rounded border-gray-300 text-blue-600" ${isVegChecked ? 'checked' : ''}>
                            <span class="ml-2 text-sm text-gray-600">Veg Only 🥦</span>
                        </label>
                    </div>
                </div>
            `;

            let tableHtml = `
                <div class="overflow-x-auto border rounded-xl shadow-sm">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rating</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Dist</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
            `;

            if (displayData.length === 0) {
                tableHtml += `<tr><td colspan="4" class="px-4 py-8 text-center text-sm text-gray-500">No results.</td></tr>`;
            } else {
                displayData.forEach(item => {
                    tableHtml += `
                        <tr class="hover:bg-gray-50 transition cursor-pointer">
                            <td class="px-4 py-3 whitespace-nowrap">
                                <div class="text-sm font-medium text-gray-900">${item.name}</div>
                                <div class="text-xs text-gray-500 truncate max-w-[120px]">${item.desc}</div>
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap"><span class="text-yellow-500">★</span> ${item.rating}</td>
                            <td class="px-4 py-3 whitespace-nowrap"><span class="px-2 text-xs rounded-full bg-green-100 text-green-800">${item.price_str}</span></td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">${item.dist_str}</td>
                        </tr>
                    `;
                });
            }
            tableHtml += `</tbody></table></div>`;
            container.innerHTML = controlsHtml + tableHtml;
        }

        function handleKeyPress(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        }

        function autoResize(textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        }

        function handleFileSelect(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    currentImageBase64 = e.target.result;
                    document.getElementById('previewImg').src = currentImageBase64;
                    document.getElementById('imagePreview').classList.remove('hidden');
                };
                reader.readAsDataURL(input.files[0]);
            }
        }

        function clearImage() {
            currentImageBase64 = null;
            document.getElementById('fileInput').value = '';
            document.getElementById('imagePreview').classList.add('hidden');
        }

        function setLoadingState(isLoading) {
            const sendBtn = document.getElementById('sendBtn');
            const userInput = document.getElementById('userInput');
            if (isLoading) {
                sendBtn.disabled = true;
                sendBtn.classList.add('opacity-50', 'cursor-not-allowed');
                userInput.disabled = true;
            } else {
                sendBtn.disabled = false;
                sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                userInput.disabled = false;
                userInput.focus();
            }
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const text = input.value.trim();
            await processMessage(text);
        }

        async function handleFormSubmit(inputId) {
            const input = document.getElementById(inputId);
            const text = input.value.trim();
            if (text) await processMessage("Correction: " + text);
        }

        async function resetChat() {
            try { await fetch('/api/reset', { method: 'POST' }); } catch (e) {}
            // Use localized welcome message if available
            const welcomeText = LANG_RESOURCES[currentLang] ? LANG_RESOURCES[currentLang].welcome : "Hello! I'm Wabi.";
            chatState = [{ id: 'welcome-msg', role: 'ai', content: welcomeText }];
            renderChatHistory();
            document.getElementById('userInput').value = '';
            document.getElementById('userInput').style.height = 'auto';
            clearImage();
        }

        function regenerateMessage(userMsgId, aiMsgId) {
            const userMsg = chatState.find(m => m.id === userMsgId);
            if (!userMsg) return;

            // Remove the old AI response and loading state if exists
            chatState = chatState.filter(msg => msg.id !== aiMsgId);
            renderChatHistory(); // Update UI to remove old answer

            // Trigger process with existing user content
            // We need to temporarily set currentImageBase64 if the message had an image
            const originalImage = currentImageBase64;
            if (userMsg.image) currentImageBase64 = userMsg.image;
            
            // Re-send logic
            const text = userMsg.text;
            const uniqueId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
            const newLoadingId = 'loading-' + uniqueId;
            
            // Update the user message to point to new AI pair ID
            userMsg.aiPairId = newLoadingId;
            
            // Add new loading state
            chatState.push({ id: newLoadingId, role: 'ai', isLoading: true, step: 0 });
            renderChatHistory();

            // Prepare payload
            let payload;
            const deviceInfo = getDeviceInfo();
            if (currentImageBase64) {
                payload = { message: [{ "type": "image_url", "image_url": {"url": currentImageBase64} }], language: currentLang, device_info: deviceInfo, platform: currentPlatform };
                if (text) payload.message.unshift({"type": "text", "text": text});
            } else {
                payload = { message: text, language: currentLang, device_info: deviceInfo, platform: currentPlatform };
            }
            
            // Restore global image state
            currentImageBase64 = originalImage;

            // Call API (Reused logic from processMessage but without adding user msg again)
            setLoadingState(true);
            (async () => {
                try {
                    const response = await fetch('/api/ui', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        
                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\\n');
                        buffer = lines.pop(); 

                        for (const line of lines) {
                            if (!line.trim()) continue;
                            try {
                                const msg = JSON.parse(line);
                                if (msg.type === 'progress') {
                                    const logEl = document.getElementById(`log-${newLoadingId}`);
                                    const progEl = document.getElementById(`progress-${newLoadingId}`);
                                    if (logEl && progEl) {
                                        logEl.textContent = msg.step;
                                        progEl.style.width = msg.progress + '%';
                                    }
                                } else if (msg.type === 'result') {
                                    const aiMsgIndex = chatState.findIndex(m => m.id === newLoadingId);
                                    if (aiMsgIndex !== -1) {
                                        let plan = msg.web_ui_plan;
                                        if (plan && plan.adapted) {
                                            // Convert adapted items to text content for simple display in chat
                                            const textContent = plan.items.map(item => {
                                                if(item.type === 'text') return item.content;
                                                if(item.type === 'image') return '<img src="' + item.url + '" style="max-width:100%; border-radius:4px; margin-top:5px;">';
                                                return '';
                                            }).join('\\n\\n');
                                            
                                            // Create a fake 'text' plan for rendering
                                            plan = { sections: [{ type: 'text', content: textContent }] };
                                        }
                                        chatState[aiMsgIndex] = { id: newLoadingId, role: 'ai', isLoading: false, plan: plan };
                                        renderChatHistory();
                                    }
                                } else if (msg.type === 'error') {
                                    const aiMsgIndex = chatState.findIndex(m => m.id === newLoadingId);
                                    if (aiMsgIndex !== -1) {
                                        chatState[aiMsgIndex] = { id: newLoadingId, role: 'ai', isLoading: false, error: msg.error };
                                        renderChatHistory();
                                    }
                                }
                            } catch (e) { console.error(e); }
                        }
                    }
                } catch (error) {
                    const aiMsgIndex = chatState.findIndex(m => m.id === newLoadingId);
                    if (aiMsgIndex !== -1) {
                        chatState[aiMsgIndex] = { id: newLoadingId, role: 'ai', isLoading: false, error: "Network Error" };
                        renderChatHistory();
                    }
                } finally {
                    setLoadingState(false);
                }
            })();
        }

        function deleteMessagePair(userMsgId, aiMsgId) {
            chatState = chatState.filter(msg => msg.id !== userMsgId && msg.id !== aiMsgId);
            renderChatHistory();
        }

        function renderChatHistory() {
            const history = document.getElementById('chatHistory');
            history.innerHTML = ''; 

            chatState.forEach(msg => {
                const pairId = msg.role === 'user' ? msg.aiPairId : (chatState.find(m => m.aiPairId === msg.id)?.id);
                const userMsgId = msg.role === 'user' ? msg.id : pairId;
                const aiMsgId = msg.role === 'ai' ? msg.id : (chatState.find(m => m.id === msg.aiPairId)?.id);
                
                if (msg.role === 'user') {
                    const userContainer = document.createElement('div');
                    userContainer.id = msg.id;
                    userContainer.className = 'user-message-container user-message message-group';
                    let displayHtml = '';
                    if (msg.image) displayHtml += `<img src="${msg.image}" class="max-h-48 rounded-lg mb-2 border border-blue-400 block">`;
                    if (msg.text) displayHtml += `<div>${msg.text}</div>`;
                    
                    // Move actions to User side (left of bubble)
                    let actionsHtml = '';
                    if (msg.aiPairId) {
                         actionsHtml = `
                            <div class="msg-actions">
                                <button onclick="saveQAPair('${aiMsgId}', '${userMsgId}')" class="action-btn" title="Save Conversation">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                                </button>
                                <button onclick="regenerateMessage('${userMsgId}', '${aiMsgId}')" class="action-btn" title="Regenerate">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/></svg>
                                </button>
                                <button onclick="deleteMessagePair('${msg.id}', '${msg.aiPairId}')" class="action-btn delete-btn" title="Delete Pair">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                                </button>
                            </div>
                         `;
                    }
                    userContainer.innerHTML = actionsHtml + `<div class="message-bubble">${displayHtml}</div>`;
                    history.appendChild(userContainer);
                } else if (msg.role === 'ai') {
                    const aiContainer = document.createElement('div');
                    aiContainer.id = msg.id;
                    aiContainer.className = 'ai-message-container ai-message message-group';
                    let contentHtml = '';
                    if (msg.isLoading) {
                         // Dynamic Progress Bar
                         contentHtml = `
                            <div class="message-bubble" style="min-width: 320px; padding: 16px;">
                               <div class="flex items-center gap-2 mb-3">
                                   <div class="w-5 h-5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"></div>
                                   <div class="text-sm font-semibold text-gray-700" id="log-${msg.id}">Initializing...</div>
                               </div>
                               <div class="h-2 w-full bg-gray-100 rounded-full overflow-hidden shadow-inner">
                                   <div class="h-full bg-gradient-to-r from-blue-400 to-blue-600 transition-all duration-500 ease-out relative" style="width: 5%" id="progress-${msg.id}">
                                       <div class="absolute inset-0 bg-white/30 w-full h-full animate-[shimmer_1.5s_infinite]"></div>
                                   </div>
                               </div>
                            </div>`;
                    } else if (msg.plan) {
                        contentHtml = `<div class="message-bubble w-full"><div id="content-${msg.id}"></div></div>`;
                    } else if (msg.content) {
                         contentHtml = `<div class="message-bubble">${msg.content}</div>`;
                    } else if (msg.error) {
                        contentHtml = `<div class="message-bubble text-red-600">Error: ${msg.error}</div>`;
                    }
                    
                    // Removed actions from AI side
                    aiContainer.innerHTML = `<div class="avatar ai">AI</div>${contentHtml}`;
                    history.appendChild(aiContainer);
                    if (msg.plan) {
                        const contentDiv = aiContainer.querySelector(`#content-${msg.id}`);
                        if(contentDiv) renderWebComponents(contentDiv, msg.plan);
                    }
                }
            });
            history.scrollTop = history.scrollHeight;
        }

        function getDeviceInfo() {
            const width = window.innerWidth;
            if (width <= 640) return 'mobile';
            if (width <= 1024) return 'tablet';
            return 'desktop';
        }

        async function processMessage(text) {
            if (!text && !currentImageBase64) return;
            const uniqueId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
            const userMsgId = 'msg-' + uniqueId;
            const loadingId = 'loading-' + uniqueId;
            
            chatState.push({ id: userMsgId, role: 'user', text: text, image: currentImageBase64, aiPairId: loadingId });
            chatState.push({ id: loadingId, role: 'ai', isLoading: true, step: 0 });
            renderChatHistory();

            let payload;
            const deviceInfo = getDeviceInfo();
            if (currentImageBase64) {
                payload = { message: [{ "type": "image_url", "image_url": {"url": currentImageBase64} }], language: currentLang, device_info: deviceInfo, platform: currentPlatform };
                if (text) payload.message.unshift({"type": "text", "text": text});
            } else {
                payload = { message: text, language: currentLang, device_info: deviceInfo, platform: currentPlatform };
            }

            document.getElementById('userInput').value = '';
            document.getElementById('userInput').style.height = 'auto';
            clearImage();

            setLoadingState(true);
            try {
                const response = await fetch('/api/ui', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\\n');
                    buffer = lines.pop(); // Keep incomplete line in buffer

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const msg = JSON.parse(line);
                            if (msg.type === 'progress') {
                                const logEl = document.getElementById(`log-${loadingId}`);
                                const progEl = document.getElementById(`progress-${loadingId}`);
                                if (logEl && progEl) {
                                    logEl.textContent = msg.step;
                                    progEl.style.width = msg.progress + '%';
                                }
                            } else if (msg.type === 'result') {
                                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                                if (aiMsgIndex !== -1) {
                                    let plan = msg.web_ui_plan;
                                    if (plan && plan.adapted) {
                                        // Convert adapted items to text content
                                        const textContent = plan.items.map(item => {
                                            if(item.type === 'text') return item.content;
                                            if(item.type === 'image') return '<img src="' + item.url + '" style="max-width:100%; border-radius:4px; margin-top:5px;">';
                                            return '';
                                        }).join('\\n\\n');
                                        
                                        plan = { sections: [{ type: 'text', content: textContent }] };
                                    }
                                    chatState[aiMsgIndex] = { id: loadingId, role: 'ai', isLoading: false, plan: plan };
                                    renderChatHistory();
                                }
                            } else if (msg.type === 'error') {
                                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                                if (aiMsgIndex !== -1) {
                                    chatState[aiMsgIndex] = { id: loadingId, role: 'ai', isLoading: false, error: msg.error };
                                    renderChatHistory();
                                }
                            }
                        } catch (e) {
                            console.error('Error parsing stream:', e);
                        }
                    }
                }
            } catch (error) {
                console.error(error);
                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                if (aiMsgIndex !== -1) {
                    chatState[aiMsgIndex] = { id: loadingId, role: 'ai', isLoading: false, error: "Network Error" };
                    renderChatHistory();
                }
            } finally {
                setLoadingState(false);
            }
        }

        function renderWebComponents(container, plan) {
            const wrapper = document.createElement('div');
            wrapper.className = 'space-y-4';

            if (plan.summary) wrapper.innerHTML += `<div class="text-base mb-3" style="color: var(--text-color);">${plan.summary}</div>`;

            plan.sections.forEach(section => {
                if (section.type === 'carousel') {
                    let itemsHtml = '';
                    section.items.forEach(item => {
                        itemsHtml += `
                            <div class="min-w-[240px] border rounded-xl shadow-sm overflow-hidden mr-4 flex-shrink-0 transition hover:shadow-md cursor-pointer" style="background: var(--card-bg); border-color: var(--border-color);">
                                <div class="p-4">
                                    <h3 class="font-bold truncate" style="color: var(--text-color);">${item.title}</h3>
                                    <p class="text-xs mt-1 line-clamp-2" style="color: var(--text-secondary);">${item.subtitle}</p>
                                </div>
                            </div>`;
                    });
                    wrapper.innerHTML += `<div class="mt-4"><h3 class="text-sm font-bold mb-3 uppercase" style="color: var(--text-secondary);">🍽️ ${section.title}</h3><div class="flex overflow-x-auto pb-4 scrollbar-hide -mx-1 px-1">${itemsHtml}</div></div>`;
                } else if (section.type === 'dynamic_place_table') {
                    const tableContainerId = 'table-' + Math.random().toString(36).substr(2, 9);
                    wrapper.innerHTML += `<div class="mt-4"><h3 class="text-sm font-bold mb-3 uppercase" style="color: var(--text-secondary);">🍽️ ${section.title}</h3><div id="${tableContainerId}"></div></div>`;
                    setTimeout(() => renderPlaceTable(tableContainerId, section.items), 0);
                } else if (section.type === 'key_value_list') {
                    let rows = '';
                    section.items.forEach(item => {
                        rows += `<div class="flex justify-between py-2 border-b border-dashed last:border-0" style="border-color: var(--border-color);"><span class="text-sm" style="color: var(--text-secondary);">${item.label}</span><span class="text-sm font-mono font-bold ${item.highlight===false?'text-red-500':'text-green-600'}">${item.value}</span></div>`;
                    });
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">📊 ${section.title}</h3><div class="space-y-1">${rows}</div></div>`;
                } else if (section.type === 'highlight_box') {
                    const isWarn = section.variant === 'warning';
                    const isInfo = section.variant === 'info';
                    const boxClass = isWarn
                        ? 'bg-amber-50 text-amber-800 border border-amber-100'
                        : isInfo
                            ? 'bg-blue-50 text-blue-800 border border-blue-100'
                            : 'bg-emerald-50 text-emerald-800 border border-emerald-100';
                    const icon = isWarn ? '⚠️' : isInfo ? 'ℹ️' : '✅';
                    wrapper.innerHTML += `<div class="p-4 rounded-xl font-medium text-center text-sm mt-3 flex items-center justify-center gap-2 ${boxClass}"><span>${icon}</span>${section.content}</div>`;
                } else if (section.type === 'text') {
                    let content = section.content;
                    if (currentPlatform === 'whatsapp') {
                        // Use marked.js for robust Markdown rendering
                        // Configure marked for line breaks and GFM
                        marked.setOptions({ 
                            breaks: true,
                            gfm: true
                        });
                        content = marked.parse(content);
                        // Optional: Adjust styles for WhatsApp specific look if needed, 
                        // but standard HTML from Markdown is usually sufficient.
                    } else {
                        // Standard Markdown (Basic)
                        content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                         .replace(/\\n/g, '<br>');
                    }
                    wrapper.innerHTML += `<div class="text-sm leading-relaxed markdown-content" style="color: var(--text-color);">${content}</div>`;
                } else if (section.type === 'custom_html') {
                    // Safe render for Custom HTML
                    const customDiv = document.createElement('div');
                    customDiv.className = 'mt-4 border rounded-xl overflow-hidden';
                    customDiv.style.borderColor = 'var(--border-color)';
                    // In a real app, use DOMPurify here. For demo, we trust the backend validation.
                    customDiv.innerHTML = section.html_content; 
                    
                    // Add a label
                    const label = document.createElement('div');
                    label.className = 'bg-gray-50 px-3 py-1 text-xs text-gray-500 border-b flex justify-between items-center';
                    label.style.backgroundColor = 'var(--bg-color)';
                    label.style.borderColor = 'var(--border-color)';
                    label.innerHTML = `<span>✨ Generated UI</span><span class="text-[10px] uppercase tracking-wide opacity-70">${section.description || 'Custom Component'}</span>`;
                    
                    wrapper.appendChild(label);
                    wrapper.appendChild(customDiv);
                } else if (section.type === 'steps_list') {
                    const steps = Array.isArray(section.steps) ? section.steps : [];
                    const title = section.title || '';
                    const itemsHtml = steps.map(s => `<li class="py-1">${s}</li>`).join('');
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">📝 ${title}</h3><ol class="list-decimal pl-5 text-sm" style="color: var(--text-color);">${itemsHtml}</ol></div>`;
                } else if (section.type === 'progress_bar') {
                    const label = section.label || '';
                    const value = Number(section.value || 0);
                    const max = Number(section.max || 100);
                    const pct = Math.max(0, Math.min(100, max > 0 ? (value / max) * 100 : 0));
                    const variant = section.variant || 'primary';
                    const colorClass = variant === 'success' ? 'bg-emerald-500' : variant === 'warning' ? 'bg-amber-500' : variant === 'error' ? 'bg-red-500' : 'bg-blue-500';
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><div class="flex justify-between items-center mb-2"><div class="text-sm font-medium" style="color: var(--text-color);">${label}</div><div class="text-xs" style="color: var(--text-secondary);">${value}/${max}</div></div><div class="w-full h-2 bg-gray-200 rounded-full overflow-hidden"><div class="h-2 ${colorClass}" style="width:${pct}%;"></div></div></div>`;
                } else if (section.type === 'comparison_table') {
                    const title = section.title || '';
                    const columns = Array.isArray(section.columns) ? section.columns : [];
                    const rows = Array.isArray(section.rows) ? section.rows : [];
                    const th = columns.map(c => `<th class="px-3 py-2 text-left text-xs" style="color: var(--text-secondary); border-color: var(--border-color);">${c}</th>`).join('');
                    const tr = rows.map(r => `<tr>${r.map(v => `<td class="px-3 py-2 text-sm border-t" style="color: var(--text-color); border-color: var(--border-color);">${v}</td>`).join('')}</tr>`).join('');
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm overflow-x-auto" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">📋 ${title}</h3><table class="min-w-full border" style="border-color: var(--border-color);"><thead class="bg-gray-50">${th ? `<tr>${th}</tr>` : ''}</thead><tbody>${tr}</tbody></table></div>`;
                } else if (section.type === 'statistic_grid') {
                    const title = section.title || '';
                    const items = Array.isArray(section.items) ? section.items : [];
                    const cards = items.map(it => {
                        const label = it.label || '';
                        const value = it.value != null ? it.value : '';
                        const unit = it.unit ? `<span class="text-xs opacity-60 ml-1">${it.unit}</span>` : '';
                        const trend = it.trend === '+' ? '▲' : it.trend === '-' ? '▼' : '';
                        return `<div class="border rounded-lg p-3 flex flex-col" style="background: var(--card-bg); border-color: var(--border-color);"><div class="text-xs" style="color: var(--text-secondary);">${label}</div><div class="text-lg font-semibold flex items-baseline" style="color: var(--text-color);"><span>${value}</span>${unit}${trend ? `<span class="text-xs ml-2 ${it.trend==='+'?'text-green-600':it.trend==='-'?'text-red-500':'text-gray-400'}">${trend}</span>` : ''}</div></div>`;
                    }).join('');
                    wrapper.innerHTML += `<div class="mt-3"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">📈 ${title}</h3><div class="grid grid-cols-2 md:grid-cols-3 gap-3">${cards}</div></div>`;
                } else if (section.type === 'tag_list') {
                    const title = section.title || '';
                    const tags = Array.isArray(section.tags) ? section.tags : [];
                    const tagHtml = tags.map(t => `<span class="px-3 py-1 rounded-full text-xs border" style="background: var(--bg-color); color: var(--text-color); border-color: var(--border-color);">${t}</span>`).join(' ');
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">🏷️ ${title}</h3><div class="flex flex-wrap gap-2">${tagHtml}</div></div>`;
                } else if (section.type === 'bar_chart') {
                    const title = section.title || '';
                    const unit = section.unit || '';
                    const items = Array.isArray(section.items) ? section.items : [];
                    const values = items.map(i => Number(i.value || 0));
                    const maxVal = Number(section.max || Math.max(1, ...values));
                    const palette = ['#2563eb','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#84cc16','#d946ef'];
                    const orientation = (section.orientation || 'horizontal').toLowerCase();
                    if (orientation === 'vertical') {
                        const cw = container.getBoundingClientRect().width || 360;
                        const chartW = Math.max(240, Math.min(Math.floor(cw * 0.9), 720));
                        const barW = Math.max(24, Math.floor(chartW / Math.max(4, items.length + 2)));
                        const maxH = 160;
                        const bars = items.map((i, idx) => {
                            const v = Number(i.value || 0);
                            const h = Math.max(2, Math.min(maxH, (v / maxVal) * maxH));
                            const color = palette[idx % palette.length];
                            return `<div class="flex flex-col items-center" style="width:${barW}px;"><div class="rounded-t-md" style="height:${h}px; width:${barW-6}px; background: linear-gradient(180deg, ${color} 0%, ${color}99 100%); box-shadow: 0 2px 6px rgba(0,0,0,0.12)"></div><div class="text-[10px] mt-2" style="color: var(--text-secondary);">${i.label || ''}</div><div class="text-[10px]" style="color: var(--text-secondary);">${v}${unit ? ' ' + unit : ''}</div></div>`;
                        }).join('');
                        wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">📊 ${title}</h3><div class="flex items-end gap-3" style="height:${maxH+40}px">${bars}</div></div>`;
                    } else {
                        const bars = items.map((i, idx) => {
                            const v = Number(i.value || 0);
                            const pct = Math.max(0, Math.min(100, (v / maxVal) * 100));
                            const color = palette[idx % palette.length];
                            return `<div class="mb-3"><div class="flex justify-between items-center text-xs mb-1" style="color: var(--text-secondary);"><span>${i.label || ''}</span><span>${v}${unit ? ' ' + unit : ''}</span></div><div class="w-full h-3 bg-gray-200 rounded-full overflow-hidden"><div class="h-3 rounded-full" style="width:${pct}%; background: linear-gradient(90deg, ${color} 0%, ${color}99 100%); transition: width .4s ease"></div></div></div>`;
                        }).join('');
                        wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">📊 ${title}</h3>${bars}</div>`;
                    }
                } else if (section.type === 'pie_chart') {
                    const title = section.title || '';
                    const unit = section.unit || '';
                    const items = Array.isArray(section.items) ? section.items : [];
                    const total = items.reduce((s, i) => s + Number(i.value || 0), 0) || 1;
                    const palette = ['#2563eb','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#84cc16','#d946ef'];
                    let start = 0, grad = '';
                    items.forEach((i, idx) => {
                        const v = Number(i.value || 0);
                        const p = Math.max(0, (v / total) * 100);
                        const end = start + p;
                        const color = palette[idx % palette.length];
                        grad += `${color} ${start}% ${end}%,`;
                        start = end;
                    });
                    grad = grad.replace(/,+$/, '');
                    const donut = !!section.donut;
                    const chart = `<div class="mx-auto relative rounded-full" style="width: clamp(160px, 30vw, 320px); aspect-ratio: 1 / 1; background: conic-gradient(${grad}); box-shadow: 0 6px 16px rgba(0,0,0,0.08)">${donut?`<div class="absolute inset-0 m-auto rounded-full" style="width: 55%; height: 55%; background: var(--card-bg)"></div>`:''}</div>`;
                    const legend = items.map((i, idx) => {
                        const color = palette[idx % palette.length];
                        const v = Number(i.value || 0);
                        return `<div class="flex items-center gap-2 text-xs" style="color: var(--text-secondary);"><span class="w-3 h-3 rounded-sm" style="background:${color}"></span><span>${i.label || ''}</span><span>${v}${unit ? ' ' + unit : ''}</span></div>`;
                    }).join('');
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">🟠 ${title}</h3><div class="flex items-center gap-6">${chart}<div class="space-y-1">${legend}</div></div></div>`;
                } else if (section.type === 'line_chart') {
                    const title = section.title || '';
                    const points = Array.isArray(section.points) ? section.points.map(Number) : [];
                    const labels = Array.isArray(section.labels) ? section.labels : [];
                    const color = section.color || '#2563eb';
                    const cw = container.getBoundingClientRect().width || 360;
                    const w = Math.max(300, Math.min(Math.floor(cw * 0.9), 720));
                    const h = Math.max(180, Math.floor(w * 0.45));
                    const pad = 24;
                    const max = Math.max(1, ...points);
                    const stepX = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0;
                    const coordsArr = points.map((v, i) => {
                        const x = pad + i * stepX;
                        const y = h - pad - (v / max) * (h - pad * 2);
                        return {x,y,v};
                    });
                    const coords = coordsArr.map(p => `${p.x},${p.y}`).join(' ');
                    const areaPath = `M ${pad} ${h-pad} L ${coordsArr.map(p=>`${p.x} ${p.y}`).join(' L ')} L ${pad + (points.length-1)*stepX} ${h-pad} Z`;
                    let ticks = '';
                    if (labels.length === points.length) {
                        labels.forEach((lb, i) => {
                            const x = pad + i * stepX;
                            ticks += `<text x="${x}" y="${h - 6}" font-size="10" text-anchor="middle" fill="var(--text-secondary)">${lb}</text>`;
                        });
                    }
                    const grid = `<line x1="${pad}" y1="${pad}" x2="${pad}" y2="${h - pad}" stroke="#e5e7eb"/><line x1="${pad}" y1="${h - pad}" x2="${w - pad}" y2="${h - pad}" stroke="#e5e7eb"/>`;
                    const dots = coordsArr.map(p=>`<circle cx="${p.x}" cy="${p.y}" r="3" fill="${color}"/>`).join('');
                    const svg = `<svg viewBox="0 0 ${w} ${h}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet"><defs><linearGradient id="lg1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity="0.25"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><g>${grid}<path d="${areaPath}" fill="url(#lg1)"/><polyline points="${coords}" fill="none" stroke="${color}" stroke-width="2"/>${dots}${ticks}</g></svg>`;
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">📈 ${title}</h3>${svg}</div>`;
                } else if (section.type === 'radar_chart') {
                    const title = section.title || '';
                    const axes = Array.isArray(section.axes) ? section.axes : [];
                    const values = Array.isArray(section.values) ? section.values.map(Number) : [];
                    const max = Number(section.max || Math.max(1, ...values));
                    const color = section.color || '#10b981';
                    const cw = container.getBoundingClientRect().width || 360;
                    const size = Math.max(220, Math.min(Math.floor(cw * 0.35), 360));
                    const cx = size/2, cy = size/2, r = size/2 - 30;
                    const N = Math.max(axes.length, values.length);
                    const pts = [];
                    for (let i = 0; i < N; i++) {
                        const angle = (Math.PI * 2 * i) / N - Math.PI / 2;
                        const val = Number(values[i] || 0);
                        const rr = (Math.max(0, Math.min(max, val)) / max) * r;
                        const x = cx + rr * Math.cos(angle);
                        const y = cy + rr * Math.sin(angle);
                        pts.push(`${x},${y}`);
                    }
                    const spokes = [];
                    for (let i = 0; i < N; i++) {
                        const a = (Math.PI * 2 * i) / N - Math.PI / 2;
                        const x = cx + r * Math.cos(a);
                        const y = cy + r * Math.sin(a);
                        spokes.push(`<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#e5e7eb"/>`);
                    }
                    let labelsHtml = '';
                    for (let i = 0; i < N; i++) {
                        const a = (Math.PI * 2 * i) / N - Math.PI / 2;
                        const x = cx + (r + 12) * Math.cos(a);
                        const y = cy + (r + 12) * Math.sin(a);
                        const lb = axes[i] || '';
                        labelsHtml += `<text x="${x}" y="${y}" font-size="10" text-anchor="middle" fill="var(--text-secondary)">${lb}</text>`;
                    }
                    const svg = `<svg viewBox="0 0 ${size} ${size}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet"><defs><radialGradient id="rg1" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="${color}" stop-opacity="0.15"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></radialGradient></defs><circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#e5e7eb"/>${spokes.join('')}<polygon points="${pts.join(' ')}" fill="url(#rg1)" stroke="${color}" stroke-width="2"/>${labelsHtml}</svg>`;
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">🕸️ ${title}</h3>${svg}</div>`;
                }
            });

            if (plan.suggestions && plan.suggestions.length > 0) {
               let btnsHtml = '';
               plan.suggestions.forEach(s => {
                   btnsHtml += `<button onclick="document.getElementById('userInput').value='${s}'; sendMessage()" class="px-3 py-1 rounded-full text-xs border transition" style="background: var(--bg-color); color: var(--text-color); border-color: var(--border-color);">${s}</button>`;
               });
               wrapper.innerHTML += `<div class="flex flex-wrap gap-2 mt-4 pt-2 border-t" style="border-color: var(--border-color);">${btnsHtml}</div>`;
            }

            if (plan.token_usage) {
                const usage = plan.token_usage;
                wrapper.innerHTML += `
                    <div class="mt-2 pt-2 border-t flex justify-end items-center text-[10px] opacity-50" style="border-color: var(--border-color); color: var(--text-secondary);">
                        <span title="Input Tokens">📥 ${usage.input}</span>
                        <span class="mx-1">|</span>
                        <span title="Output Tokens">📤 ${usage.output}</span>
                        <span class="mx-1">|</span>
                        <span title="Total Tokens">∑ ${usage.total}</span>
                    </div>
                `;
            }

            container.appendChild(wrapper);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
