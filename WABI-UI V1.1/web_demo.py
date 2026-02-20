# -*- coding: utf-8 -*-
"""
web_demo.py — FastAPI entry-point for the Wabi UI Agent (LangGraph edition)

The HTTP layer is kept deliberately thin.  All business logic lives inside
the LangGraph graph (UI/graph.py).  The endpoint:

  1. Parses the incoming ChatRequest.
  2. Builds an initial GraphState dict.
  3. Streams progress events while invoking the graph asynchronously.
  4. Returns the final `rendered_output` as a streaming NDJSON response.

Endpoints
─────────
  POST /api/ui     → main streaming chat endpoint
  POST /api/reset  → clears server-side chat history
  GET  /           → serves the single-page HTML chat UI
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Union

# 确保用户 site-packages 在路径中（用于找到 dashscope）
user_site_311 = os.path.expanduser('~/.local/lib/python3.11/site-packages')
user_site_312 = os.path.expanduser('~/.local/lib/python3.12/site-packages')
if user_site_311 not in sys.path:
    sys.path.insert(0, user_site_311)
if user_site_312 not in sys.path:
    sys.path.insert(0, user_site_312)

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

load_dotenv()


# ---------------------------------------------------------------------------
# Path resolution (allows running directly from the UI folder)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from UI.graph import graph          # compiled LangGraph pipeline
from UI.state import GraphState     # TypedDict
from UI.streaming_graph import (
    streaming_graph,
    StreamingEvent,
    DynamicUIRenderer,
    stream_ui_plan,
)
from UI.llm_config import get_available_models, validate_model_name

# ---------------------------------------------------------------------------
# In-memory session state (demo only — replace with Redis for production)
# ---------------------------------------------------------------------------
_SESSION: Dict[str, Any] = {
    "chat_history": [],
    # 保留上一轮的数据字段，用于意图跟随
    "last_nutrition_facts": None,
    "last_food_detection_json": None,
    "last_recommended_restaurants": None,
    "last_user_history": None,
    "last_intent": None,
}

# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message:     Union[str, List[Dict[str, Any]]]
    patient_id:  Optional[str] = "demo_user"
    language:    Optional[str] = None
    device_info: Optional[str] = None    # 'mobile' | 'tablet' | 'desktop'
    platform:    Optional[str] = "web"   # 'web' | 'wechat' | 'whatsapp'
    llm_model:   Optional[str] = None    # 'claude-3.5-sonnet' | 'qwen-plus'


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Wabi UI Agent (LangGraph)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_message(message: Union[str, List]) -> tuple[str, bool]:
    """
    Extract (text_content, has_image) from the raw message payload.
    """
    if isinstance(message, str):
        return message, False

    text   = ""
    is_img = False
    for item in message:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            text += item.get("text", "")
        elif item.get("type") in ("image_url", "image"):
            is_img = True
    return text, is_img


# ---------------------------------------------------------------------------
# Streaming generator — progress + final result
# ---------------------------------------------------------------------------

async def _stream_graph(request: ChatRequest):
    """Async generator that yields NDJSON lines."""

    async def _emit(data: dict) -> str:
        return json.dumps(data) + "\n"

    yield await _emit({"type": "progress", "step": "Initialising request…",   "progress": 10})
    await asyncio.sleep(0.3)

    # ── Parse message ────────────────────────────────────────────────────
    text_content, has_image = _parse_message(request.message)
    language = request.language or "Chinese"
    platform = request.platform or "web"

    # Append user message to session history
    _SESSION["chat_history"].append(HumanMessage(content=text_content))

    yield await _emit({"type": "progress", "step": "Detecting intent…",        "progress": 25})
    await asyncio.sleep(0.2)

    # ── Build initial GraphState ─────────────────────────────────────────
    # 传递上一轮的数据字段，支持意图跟随
    # 使用默认模型如果请求中没有指定
    from UI.llm_config import DEFAULT_MODEL
    llm_model = request.llm_model or DEFAULT_MODEL
    
    initial_state: GraphState = {
        "user_input":   text_content,
        "patient_id":   request.patient_id or "demo_user",
        "language":     language,
        "platform":     platform,
        "has_image":    has_image,
        "chat_history": _SESSION["chat_history"][-10:],   # last 10 turns
        "llm_model":    llm_model,                        # LLM模型选择
        # 传递上一轮数据用于意图跟随
        "nutrition_facts": _SESSION.get("last_nutrition_facts"),
        "food_detection_json": _SESSION.get("last_food_detection_json"),
        "recommended_restaurants": _SESSION.get("last_recommended_restaurants"),
        "user_history": _SESSION.get("last_user_history"),
    }

    yield await _emit({"type": "progress", "step": "Running graph pipeline…",  "progress": 45})
    await asyncio.sleep(0.2)

    # ── Invoke the LangGraph pipeline (sync → thread pool) ───────────────
    try:
        final_state: GraphState = await asyncio.to_thread(graph.invoke, initial_state)

        yield await _emit({"type": "progress", "step": "Rendering UI components…", "progress": 85})
        await asyncio.sleep(0.2)

        rendered = final_state.get("rendered_output")
        if not rendered:
            yield await _emit({"type": "error", "error": "Graph returned no rendered output"})
            return

        # Append AI summary to session history (包含 ui_plan 用于意图跟随检测)
        _SESSION["chat_history"].append(
            AIMessage(
                content=rendered.get("summary", ""),
                additional_kwargs={"ui_plan": rendered}
            )
        )
        
        # 保存数据字段到 session，用于下一轮意图跟随
        _SESSION["last_intent"] = final_state.get("intent")
        _SESSION["last_nutrition_facts"] = final_state.get("nutrition_facts")
        _SESSION["last_food_detection_json"] = final_state.get("food_detection_json")
        _SESSION["last_recommended_restaurants"] = final_state.get("recommended_restaurants")
        _SESSION["last_user_history"] = final_state.get("user_history")

        yield await _emit({"type": "progress", "step": "Done.", "progress": 100})
        yield await _emit({"type": "result",   "web_ui_plan": rendered})

    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield await _emit({"type": "error", "error": str(exc)})


# ---------------------------------------------------------------------------
# Enhanced Streaming Generator with Node-level Events
# ---------------------------------------------------------------------------

async def _stream_graph_enhanced(request: ChatRequest):
    """
    增强版流式生成器
    
    支持：
    - 节点级事件（node_start, node_output, node_end）
    - 动态UI渲染（ui_delta, render_instruction）
    - 实时进度反馈
    """
    async def _emit(data: dict) -> str:
        return json.dumps(data, default=str) + "\n"
    
    # Parse message
    text_content, has_image = _parse_message(request.message)
    language = request.language or "Chinese"
    platform = request.platform or "web"
    
    # Append user message to session history
    _SESSION["chat_history"].append(HumanMessage(content=text_content))
    
    # Build initial state
    # 使用默认模型如果请求中没有指定
    from UI.llm_config import DEFAULT_MODEL
    llm_model = request.llm_model or DEFAULT_MODEL
    
    initial_state: GraphState = {
        "user_input": text_content,
        "patient_id": request.patient_id or "demo_user",
        "language": language,
        "platform": platform,
        "has_image": has_image,
        "chat_history": _SESSION["chat_history"][-10:],
        "llm_model": llm_model,  # LLM模型选择
        "nutrition_facts": _SESSION.get("last_nutrition_facts"),
        "food_detection_json": _SESSION.get("last_food_detection_json"),
        "recommended_restaurants": _SESSION.get("last_recommended_restaurants"),
        "user_history": _SESSION.get("last_user_history"),
    }
    
    final_state = None
    
    try:
        # Use streaming graph
        async for event in streaming_graph.astream(initial_state, include_intermediate=True):
            # Map internal events to client-facing events
            if event["type"] == StreamingEvent.NODE_START:
                yield await _emit({
                    "type": "progress",
                    "step": f"Running {event['node']}...",
                    "progress": event["progress"],
                    "node": event["node"],
                    "detail": "start",
                })
                
            elif event["type"] == StreamingEvent.NODE_OUTPUT:
                # Include key output data
                data = event.get("data", {})
                output_summary = {}
                
                if "intent" in data:
                    output_summary["intent"] = data["intent"]
                if "agent_response" in data:
                    output_summary["agent_response"] = data["agent_response"][:200] if data["agent_response"] else ""
                if "data_source" in data:
                    output_summary["data_source"] = data["data_source"]
                
                yield await _emit({
                    "type": "node_output",
                    "node": event["node"],
                    "progress": event["progress"],
                    "data": output_summary,
                })
                
            elif event["type"] == StreamingEvent.UI_DELTA:
                # Dynamic UI rendering event
                delta = event.get("delta", {})
                yield await _emit({
                    "type": "ui_delta",
                    "progress": event["progress"],
                    "mode": delta.get("mode"),
                    "summary": delta.get("summary"),
                    "sections_count": delta.get("sections_count"),
                    "section_types": delta.get("section_types"),
                })
                
            elif event["type"] == StreamingEvent.NODE_END:
                yield await _emit({
                    "type": "progress",
                    "step": f"Completed {event['node']}",
                    "progress": event["progress"],
                    "node": event["node"],
                    "detail": "end",
                })
                
            elif event["type"] == StreamingEvent.COMPLETE:
                final_state = event.get("state", {})
                
            elif event["type"] == StreamingEvent.ERROR:
                yield await _emit({
                    "type": "error",
                    "error": event.get("error"),
                    "node": event.get("node"),
                    "progress": event.get("progress", 0),
                })
                return
        
        # Save session state
        if final_state:
            rendered = final_state.get("rendered_output")
            if rendered:
                _SESSION["chat_history"].append(
                    AIMessage(
                        content=rendered.get("summary", ""),
                        additional_kwargs={"ui_plan": rendered}
                    )
                )
                
                _SESSION["last_intent"] = final_state.get("intent")
                _SESSION["last_nutrition_facts"] = final_state.get("nutrition_facts")
                _SESSION["last_food_detection_json"] = final_state.get("food_detection_json")
                _SESSION["last_recommended_restaurants"] = final_state.get("recommended_restaurants")
                _SESSION["last_user_history"] = final_state.get("user_history")
                
                yield await _emit({
                    "type": "result",
                    "web_ui_plan": rendered,
                    "progress": 100,
                })
            else:
                yield await _emit({
                    "type": "error",
                    "error": "No rendered output",
                })
                
    except Exception as exc:
        import traceback
        traceback.print_exc()
        yield await _emit({"type": "error", "error": str(exc)})


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.post("/api/ui")
async def get_ui_response(request: ChatRequest):
    """标准流式端点（向后兼容）"""
    return StreamingResponse(
        _stream_graph(request),
        media_type="application/x-ndjson",
    )


@app.post("/api/ui/stream")
async def get_ui_response_streaming(request: ChatRequest):
    """
    增强流式端点
    
    提供节点级事件和动态UI渲染支持
    """
    return StreamingResponse(
        _stream_graph_enhanced(request),
        media_type="application/x-ndjson",
    )


@app.get("/api/models")
async def get_models():
    """
    获取可用LLM模型列表
    
    返回所有支持的模型信息，供前端选择
    """
    models = get_available_models()
    return JSONResponse({
        "status": "success",
        "models": models,
        "default": "claude-3.5-sonnet"
    })


@app.post("/api/reset")
async def reset_state():
    _SESSION["chat_history"] = []
    _SESSION["last_nutrition_facts"] = None
    _SESSION["last_food_detection_json"] = None
    _SESSION["last_recommended_restaurants"] = None
    _SESSION["last_user_history"] = None
    _SESSION["last_intent"] = None
    return JSONResponse({"status": "success", "message": "Session reset"})


class FeedbackRequest(BaseModel):
    patient_id: str
    feedback_content: str


@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    提交用户反馈
    
    将用户文字反馈更新到 CSV 记录中
    """
    from UI.feedback_logger import update_feedback_content
    
    success = update_feedback_content(
        patient_id=request.patient_id,
        feedback_content=request.feedback_content
    )
    
    if success:
        return JSONResponse({
            "status": "success",
            "message": "Feedback recorded successfully"
        })
    else:
        return JSONResponse(
            {"status": "error", "message": "Failed to record feedback"},
            status_code=500
        )


# ---------------------------------------------------------------------------
# Static HTML shell (identical UI to original web_demo.py)
# ---------------------------------------------------------------------------

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
                v1.0 (Adaptive)<br>Project Wabi-C
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
                        <p class="text-sm opacity-70">Version: 1.0 (Adaptive UI)</p>
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
                    
                    <!-- 模型选择下拉框 -->
                    <div class="relative whitespace-nowrap" id="modelSelectorContainer" style="z-index: 100;">
                        <button type="button"
                            onclick="event.stopPropagation(); toggleModelDropdown();"
                            class="flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border"
                            style="color: var(--text-secondary); background: var(--bg-color); border-color: var(--border-color); white-space: nowrap;"
                            id="modelSelectorBtn">
                            <span id="currentModelLabel" style="white-space: nowrap;">Qwen</span>
                            <svg id="modelDropdownArrow" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="transition-transform duration-200 opacity-60 flex-shrink-0">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </button>
                        <div id="modelDropdownMenu" 
                            class="hidden absolute bottom-full left-0 mb-2 w-36 rounded-lg shadow-lg border py-1 transform origin-bottom-left transition-all duration-200"
                            style="background: var(--card-bg); border-color: var(--border-color); box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
                            <button type="button" 
                                onclick="event.stopPropagation(); selectModel('qwen-plus');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center gap-3 hover:opacity-80"
                                style="color: var(--text-color);"
                                id="modelBtnQwen">
                                <span class="w-2 h-2 rounded-full" style="background: linear-gradient(135deg, #3b82f6, #8b5cf6);"></span>
                                <span id="modelOptionQwen">Qwen</span>
                            </button>
                            <button type="button" 
                                onclick="event.stopPropagation(); selectModel('claude-3.5-sonnet');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center gap-3 hover:opacity-80"
                                style="color: var(--text-color);"
                                id="modelBtnClaude">
                                <span class="w-2 h-2 rounded-full" style="background: linear-gradient(135deg, #f97316, #ef4444);"></span>
                                <span id="modelOptionClaude">Claude</span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- 流式输出切换按钮 -->
                    <button id="streamingToggle" onclick="toggleStreaming()" class="p-2 text-gray-400 hover:text-blue-600 transition rounded-lg hover:bg-gray-50 relative" title="切换流式输出">
                        <svg id="streamingIconOff" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        <svg id="streamingIconOn" class="hidden" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--primary-color);"><polygon points="5 3 19 12 5 21 5 3"></polygon><path d="M5 3v18" stroke-dasharray="4 2"></path></svg>
                        <span id="streamingBadge" class="hidden absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full"></span>
                    </button>
                    
                    <button id="sendBtn" onclick="sendMessage()" class="bg-blue-600 text-white rounded-full hover:bg-blue-700 transition shadow-sm">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </div>
                <!-- 流式输出状态显示 -->
                <div id="streamingStatus" class="hidden text-xs mt-1 flex items-center gap-2" style="color: var(--text-secondary);">
                    <span class="flex items-center gap-1">
                        <span class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
                        <span id="streamingStatusText">流式输出中...</span>
                    </span>
                    <span id="streamingProgress" class="text-xs"></span>
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
        let isStreamingEnabled = false;  // 流式输出开关
        let streamingAbortController = null;  // 用于取消流式请求
        let currentStreamingMessageId = null;  // 当前流式消息ID

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
                'platform_whatsapp': 'WhatsApp',
                'drag_upload_title': '拖拽图片到此处，或点击上传',
                'drag_upload_sub': '支持 JPG、PNG 等常见图片格式',
                'streaming_status': '流式输出中...',
                'streaming_progress': '进度'
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
                'platform_whatsapp': 'WhatsApp',
                'drag_upload_title': 'Drag image here or click to upload',
                'drag_upload_sub': 'Supports JPG, PNG and other common formats',
                'streaming_status': 'Streaming...',
                'streaming_progress': 'Progress'
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

        // Model Configuration
        let currentModel = 'qwen-plus';
        let availableModels = {};
        
        // Model display names for different languages
        const MODEL_NAMES = {
            'Chinese': {
                'qwen-plus': '通义千问',
                'claude-3.5-sonnet': 'Claude',
                'model_select_title': '选择模型'
            },
            'English': {
                'qwen-plus': 'Qwen',
                'claude-3.5-sonnet': 'Claude',
                'model_select_title': 'Select Model'
            }
        };

        // Load available models on startup
        async function loadAvailableModels() {
            try {
                const response = await fetch('/api/models');
                const data = await response.json();
                if (data.status === 'success') {
                    availableModels = data.models;
                    // Update UI with model info
                    updateModelSelector();
                }
            } catch (error) {
                console.error('Failed to load models:', error);
            }
        }

        function updateModelSelector() {
            const selector = document.getElementById('modelSelector');
            if (!selector) return;
            
            // Set default value to qwen-plus
            selector.value = currentModel;
        }

        let isModelDropdownOpen = false;
        
        function toggleModelDropdown() {
            const menu = document.getElementById('modelDropdownMenu');
            const arrow = document.getElementById('modelDropdownArrow');
            
            if (isModelDropdownOpen) {
                closeModelDropdown();
            } else {
                openModelDropdown();
            }
        }
        
        function openModelDropdown() {
            const menu = document.getElementById('modelDropdownMenu');
            const arrow = document.getElementById('modelDropdownArrow');
            
            menu.classList.remove('hidden');
            // Small delay to allow display:block to apply before opacity transition
            setTimeout(() => {
                menu.classList.remove('scale-95', 'opacity-0');
                menu.classList.add('scale-100', 'opacity-100');
            }, 10);
            
            arrow.style.transform = 'rotate(180deg)';
            isModelDropdownOpen = true;
            
            // Close when clicking outside
            document.addEventListener('click', closeModelDropdownOutside);
        }
        
        function closeModelDropdown() {
            const menu = document.getElementById('modelDropdownMenu');
            const arrow = document.getElementById('modelDropdownArrow');
            
            menu.classList.remove('scale-100', 'opacity-100');
            menu.classList.add('scale-95', 'opacity-0');
            arrow.style.transform = 'rotate(0deg)';
            
            setTimeout(() => {
                menu.classList.add('hidden');
            }, 200);
            
            isModelDropdownOpen = false;
            document.removeEventListener('click', closeModelDropdownOutside);
        }
        
        function closeModelDropdownOutside(event) {
            const container = document.getElementById('modelSelectorContainer');
            if (container && !container.contains(event.target)) {
                closeModelDropdown();
            }
        }
        
        function selectModel(modelName) {
            if (!modelName) return;
            
            currentModel = modelName;
            
            // Update displayed label
            const modelNames = MODEL_NAMES[currentLang] || MODEL_NAMES['English'];
            document.getElementById('currentModelLabel').textContent = modelNames[modelName] || modelName;
            
            // Highlight selected option
            updateModelDropdownHighlight();
            
            closeModelDropdown();
            console.log('Model switched to:', modelName);
            
            // Show notification
            const displayName = modelNames[modelName] || modelName;
            const notificationMsg = currentLang === 'Chinese' ? `已切换到 ${displayName}` : `Switched to ${displayName}`;
            showNotification(notificationMsg);
        }
        
        function updateModelDropdownHighlight() {
            const qwenBtn = document.getElementById('modelBtnQwen');
            const claudeBtn = document.getElementById('modelBtnClaude');
            
            if (qwenBtn && claudeBtn) {
                if (currentModel === 'qwen-plus') {
                    qwenBtn.style.background = 'rgba(59, 130, 246, 0.1)';
                    qwenBtn.style.color = '#3b82f6';
                    claudeBtn.style.background = '';
                    claudeBtn.style.color = 'var(--text-color)';
                } else {
                    claudeBtn.style.background = 'rgba(249, 115, 22, 0.1)';
                    claudeBtn.style.color = '#f97316';
                    qwenBtn.style.background = '';
                    qwenBtn.style.color = 'var(--text-color)';
                }
            }
        }
        
        function handleModelChange(modelName) {
            // Legacy function - now handled by selectModel
            selectModel(modelName);
        }

        function showNotification(message) {
            // Create a simple notification toast
            const toast = document.createElement('div');
            toast.className = 'fixed top-4 left-1/2 -translate-x-1/2 bg-gray-800 text-white px-4 py-2 rounded-lg text-sm z-50 animate-fade-in';
            toast.textContent = message;
            toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.8);color:white;padding:8px 16px;border-radius:8px;font-size:14px;z-index:9999;';
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.remove();
            }, 2000);
        }

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

        // Initialize Model Selection
        loadAvailableModels();
        
        // Initialize model selector label
        const initialModelNames = MODEL_NAMES['Chinese'];
        document.getElementById('currentModelLabel').textContent = initialModelNames['qwen-plus'];
        updateModelDropdownHighlight();

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

            // Update streaming status text
            const streamingStatusText = document.getElementById('streamingStatusText');
            if (streamingStatusText && res.streaming_status) {
                streamingStatusText.textContent = res.streaming_status;
            }
            
            // Update model selector language
            updateModelSelectorLanguage(lang);
        }
        
        function updateModelSelectorLanguage(lang) {
            const modelNames = MODEL_NAMES[lang] || MODEL_NAMES['English'];
            
            // Update current model label
            const currentLabel = document.getElementById('currentModelLabel');
            if (currentLabel) {
                currentLabel.textContent = modelNames[currentModel] || currentModel;
            }
            
            // Update dropdown options
            const qwenOption = document.getElementById('modelOptionQwen');
            const claudeOption = document.getElementById('modelOptionClaude');
            if (qwenOption) qwenOption.textContent = modelNames['qwen-plus'];
            if (claudeOption) claudeOption.textContent = modelNames['claude-3.5-sonnet'];
            
            // Update button title
            const selectorBtn = document.getElementById('modelSelectorBtn');
            if (selectorBtn) {
                selectorBtn.title = modelNames['model_select_title'];
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

        function setImageFromFile(file) {
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {
                currentImageBase64 = e.target.result;
                document.getElementById('previewImg').src = currentImageBase64;
                document.getElementById('imagePreview').classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        }

        function handleFileSelect(input) {
            if (input.files && input.files[0]) {
                setImageFromFile(input.files[0]);
            }
        }

        function handleDragOver(e) {
            e.preventDefault();
            if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
            const dropZone = document.getElementById('imageDropZone');
            if (dropZone) dropZone.classList.add('ring-2', 'ring-blue-400', 'bg-blue-50');
        }

        function handleDragLeave(e) {
            e.preventDefault();
            const dropZone = document.getElementById('imageDropZone');
            if (dropZone) dropZone.classList.remove('ring-2', 'ring-blue-400', 'bg-blue-50');
        }

        function handleDrop(e) {
            e.preventDefault();
            const dropZone = document.getElementById('imageDropZone');
            if (dropZone) dropZone.classList.remove('ring-2', 'ring-blue-400', 'bg-blue-50');
            const files = e.dataTransfer && e.dataTransfer.files;
            if (files && files[0]) {
                setImageFromFile(files[0]);
            }
        }

        function triggerImageUpload() {
            const input = document.getElementById('fileInput');
            if (input) input.click();
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

        // 流式输出切换函数
        function toggleStreaming() {
            isStreamingEnabled = !isStreamingEnabled;
            const iconOff = document.getElementById('streamingIconOff');
            const iconOn = document.getElementById('streamingIconOn');
            const badge = document.getElementById('streamingBadge');
            
            if (isStreamingEnabled) {
                iconOff.classList.add('hidden');
                iconOn.classList.remove('hidden');
                badge.classList.remove('hidden');
            } else {
                iconOff.classList.remove('hidden');
                iconOn.classList.add('hidden');
                badge.classList.add('hidden');
            }
        }

        // 提交反馈
        async function submitFeedback(formId, patientId) {
            const inputEl = document.getElementById(`${formId}-input`);
            const submitBtn = document.getElementById(`${formId}-submit`);
            const statusEl = document.getElementById(`${formId}-status`);
            const statusContent = statusEl.querySelector('div');
            const formArea = document.getElementById(`${formId}-form-area`);
            const successArea = document.getElementById(`${formId}-success-area`);
            
            const feedbackContent = inputEl.value.trim();
            if (!feedbackContent) {
                statusEl.classList.remove('hidden');
                statusContent.innerHTML = `<span class="text-amber-600">⚠️ 请输入反馈内容</span>`;
                return;
            }
            
            // 禁用按钮和输入框
            submitBtn.disabled = true;
            submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
            inputEl.disabled = true;
            
            try {
                const response = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        patient_id: patientId,
                        feedback_content: feedbackContent
                    })
                });
                
                const result = await response.json();
                
                if (result.status === 'success') {
                    // 隐藏表单，显示成功消息
                    formArea.classList.add('hidden');
                    successArea.classList.remove('hidden');
                } else {
                    statusEl.classList.remove('hidden');
                    statusContent.innerHTML = `<span class="text-red-600">✗ 提交失败，请稍后重试</span>`;
                    // 恢复按钮和输入框
                    submitBtn.disabled = false;
                    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                    inputEl.disabled = false;
                }
            } catch (error) {
                console.error('提交反馈失败:', error);
                statusEl.classList.remove('hidden');
                statusContent.innerHTML = `<span class="text-red-600">✗ 网络错误，请稍后重试</span>`;
                // 恢复按钮和输入框
                submitBtn.disabled = false;
                submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                inputEl.disabled = false;
            }
        }

        // 显示流式状态
        function showStreamingStatus(show, progress = '') {
            const statusEl = document.getElementById('streamingStatus');
            const progressEl = document.getElementById('streamingProgress');
            const statusTextEl = document.getElementById('streamingStatusText');
            if (show) {
                statusEl.classList.remove('hidden');
                progressEl.textContent = progress;
                // 更新状态文本为当前语言
                const res = LANG_RESOURCES[currentLang] || LANG_RESOURCES['English'];
                if (statusTextEl && res.streaming_status) {
                    statusTextEl.textContent = res.streaming_status;
                }
            } else {
                statusEl.classList.add('hidden');
            }
        }

        // 更新流式消息内容
        function updateStreamingMessage(messageId, content, type = 'text') {
            const msgIndex = chatState.findIndex(m => m.id === messageId);
            if (msgIndex === -1) return;
            
            const msg = chatState[msgIndex];
            if (type === 'node_output') {
                // 显示节点输出信息
                msg.streamingInfo = content;
            } else if (type === 'ui_delta') {
                // 显示UI增量信息
                msg.uiPreview = content;
            } else if (type === 'text') {
                // 累积文本内容
                msg.streamingContent = (msg.streamingContent || '') + content;
            }
            
            renderChatHistory();
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const text = input.value.trim();
            
            // 如果正在流式输出，先取消
            if (streamingAbortController) {
                streamingAbortController.abort();
                streamingAbortController = null;
            }
            
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
                payload = { message: [{ "type": "image_url", "image_url": {"url": currentImageBase64} }], language: currentLang, device_info: deviceInfo, platform: currentPlatform, llm_model: currentModel };
                if (text) payload.message.unshift({"type": "text", "text": text});
            } else {
                payload = { message: text, language: currentLang, device_info: deviceInfo, platform: currentPlatform, llm_model: currentModel };
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
                    if (msg.isLoading || msg.isStreaming) {
                         // Dynamic Progress Bar with Streaming Info
                         let streamingInfoHtml = '';
                         if (msg.streamingInfo) {
                             streamingInfoHtml += `<div class="text-xs text-blue-600 mt-2 font-mono">${msg.streamingInfo}</div>`;
                         }
                         if (msg.uiPreview) {
                             streamingInfoHtml += `<div class="text-xs text-green-600 mt-1 font-mono">${msg.uiPreview}</div>`;
                         }
                         
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
                               ${streamingInfoHtml}
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
            currentStreamingMessageId = loadingId;
            
            // 创建 AbortController 用于取消请求
            streamingAbortController = new AbortController();
            
            try {
                // 根据是否启用流式选择端点
                const endpoint = isStreamingEnabled ? '/api/ui/stream' : '/api/ui';
                
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload),
                    signal: streamingAbortController.signal
                });
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                
                // 流式输出时显示状态
                if (isStreamingEnabled) {
                    showStreamingStatus(true, '0%');
                }

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
                                
                                // 更新流式状态显示
                                if (isStreamingEnabled) {
                                    showStreamingStatus(true, msg.progress + '%');
                                }
                            } else if (msg.type === 'node_output' && isStreamingEnabled) {
                                // 流式模式：显示节点输出
                                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                                if (aiMsgIndex !== -1) {
                                    const info = [];
                                    if (msg.data.intent) info.push(`意图: ${msg.data.intent}`);
                                    if (msg.data.data_source) info.push(`数据源: ${msg.data.data_source}`);
                                    if (msg.data.agent_response) info.push(msg.data.agent_response.substring(0, 50));
                                    
                                    chatState[aiMsgIndex].streamingInfo = info.join(' | ');
                                    chatState[aiMsgIndex].isStreaming = true;
                                    renderChatHistory();
                                }
                            } else if (msg.type === 'ui_delta' && isStreamingEnabled) {
                                // 流式模式：显示UI预览
                                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                                if (aiMsgIndex !== -1) {
                                    const preview = [];
                                    if (msg.mode) preview.push(`模式: ${msg.mode}`);
                                    if (msg.sections_count) preview.push(`${msg.sections_count} 个组件`);
                                    if (msg.section_types) preview.push(`组件: ${msg.section_types.join(', ')}`);
                                    
                                    chatState[aiMsgIndex].uiPreview = preview.join(' | ');
                                    chatState[aiMsgIndex].isStreaming = true;
                                    renderChatHistory();
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
                                    chatState[aiMsgIndex] = { 
                                        id: loadingId, 
                                        role: 'ai', 
                                        isLoading: false, 
                                        isStreaming: false,
                                        plan: plan 
                                    };
                                    renderChatHistory();
                                }
                                
                                // 隐藏流式状态
                                showStreamingStatus(false);
                            } else if (msg.type === 'error') {
                                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                                if (aiMsgIndex !== -1) {
                                    chatState[aiMsgIndex] = { 
                                        id: loadingId, 
                                        role: 'ai', 
                                        isLoading: false, 
                                        isStreaming: false,
                                        error: msg.error 
                                    };
                                    renderChatHistory();
                                }
                                showStreamingStatus(false);
                            }
                        } catch (e) {
                            console.error('Error parsing stream:', e);
                        }
                    }
                }
            } catch (error) {
                if (error.name === 'AbortError') {
                    console.log('Stream aborted');
                    const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                    if (aiMsgIndex !== -1) {
                        chatState[aiMsgIndex] = { 
                            id: loadingId, 
                            role: 'ai', 
                            isLoading: false, 
                            isStreaming: false,
                            error: "已取消" 
                        };
                        renderChatHistory();
                    }
                } else {
                    console.error(error);
                    const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                    if (aiMsgIndex !== -1) {
                        chatState[aiMsgIndex] = { 
                            id: loadingId, 
                            role: 'ai', 
                            isLoading: false, 
                            isStreaming: false,
                            error: "Network Error" 
                        };
                        renderChatHistory();
                    }
                }
            } finally {
                setLoadingState(false);
                streamingAbortController = null;
                currentStreamingMessageId = null;
                showStreamingStatus(false);
            }
        }

        function renderWebComponents(container, plan) {
            const wrapper = document.createElement('div');
            wrapper.className = 'space-y-4';

            const planLang = plan.language || currentLang;

            // 对于 correction_feedback 或 image_upload_request 模式，如果 sections 已包含内容，不重复显示 summary
            const hasTextSection = plan.sections && plan.sections.some(s => s.type === 'text');
            const shouldSkipSummary = (plan.mode === 'correction_feedback' || plan.mode === 'image_upload_request') && hasTextSection;
            
            if (plan.summary && !shouldSkipSummary) wrapper.innerHTML += `<div class="text-base mb-3" style="color: var(--text-color);">${plan.summary}</div>`;

            // 只在 Web 平台显示图片上传区域，微信/WhatsApp 使用对话形式
            if (plan.mode === 'image_upload_request' && currentPlatform === 'web') {
                const dropHtml = `
                    <div id="imageDropZone"
                        class="mt-3 border-2 border-dashed border-blue-300 rounded-xl p-4 text-center cursor-pointer bg-white hover:bg-blue-50 transition flex flex-col items-center justify-center gap-2"
                        ondragover="handleDragOver(event)"
                        ondragleave="handleDragLeave(event)"
                        ondrop="handleDrop(event)"
                        onclick="triggerImageUpload()">
                        <div class="flex flex-col items-center gap-2">
                            <div class="w-10 h-10 rounded-full flex items-center justify-center bg-blue-50 text-blue-600 mb-1">
                                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path>
                                    <polyline points="16 6 12 2 8 6"></polyline>
                                    <line x1="12" y1="2" x2="12" y2="16"></line>
                                </svg>
                            </div>
                            <div class="text-sm" style="color: var(--text-color);">${LANG_RESOURCES[planLang]['drag_upload_title']}</div>
                            <div class="text-xs" style="color: var(--text-secondary);">${LANG_RESOURCES[planLang]['drag_upload_sub']}</div>
                        </div>
                    </div>
                `;
                wrapper.innerHTML += dropHtml;
            }

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
                    const actionButtons = customDiv.querySelectorAll('[data-wabi-action]');
                    actionButtons.forEach(btn => {
                        btn.addEventListener('click', () => {
                            const value = btn.getAttribute('data-wabi-action') || '';
                            const inputEl = document.getElementById('userInput');
                            if (!value || !inputEl) return;
                            inputEl.value = value;
                            sendMessage();
                        });
                    });
                    
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
                } else if (section.type === 'button_group') {
                    const title = section.title || '';
                    const buttons = Array.isArray(section.buttons) ? section.buttons : [];
                    const btnsHtml = buttons.map(b => {
                        const variantClass = b.variant === 'secondary' ? 'bg-gray-100 text-gray-700 hover:bg-gray-200' : 
                                             b.variant === 'outline' ? 'border-2 border-blue-600 text-blue-600 hover:bg-blue-50' : 
                                             'bg-blue-600 text-white hover:bg-blue-700 shadow-md transform hover:-translate-y-0.5';
                        return `<button onclick="document.getElementById('userInput').value='${b.value}'; sendMessage()" class="px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${variantClass}">${b.label}</button>`;
                    }).join('');
                    
                    wrapper.innerHTML += `
                        <div class="p-5 mt-4 border rounded-2xl shadow-sm bg-gradient-to-br from-white to-blue-50/50" style="border-color: var(--border-color);">
                            ${title ? `<h3 class="text-sm font-bold mb-4 text-gray-800 flex items-center gap-2"><span class="w-1 h-4 bg-blue-500 rounded-full"></span>${title}</h3>` : ''}
                            <div class="flex flex-wrap gap-3">
                                ${btnsHtml}
                            </div>
                        </div>`;
                } else if (section.type === 'feedback_form') {
                    // 反馈表单组件
                    const placeholder = section.placeholder || '请输入您的反馈...';
                    const submitLabel = section.submit_label || '提交反馈';
                    const patientId = section.patient_id || 'unknown';
                    const formId = 'feedback-form-' + Math.random().toString(36).substr(2, 9);
                    
                    const formHtml = `
                        <div id="${formId}-container" class="mt-4 p-5 border rounded-xl bg-white shadow-sm" style="border-color: var(--border-color);">
                            <!-- 表单区域 -->
                            <div id="${formId}-form-area">
                                <div class="mb-3">
                                    <textarea 
                                        id="${formId}-input"
                                        class="w-full p-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        style="border-color: var(--border-color); min-height: 80px;"
                                        placeholder="${placeholder}"
                                        rows="3"
                                    ></textarea>
                                </div>
                                <div class="flex justify-end">
                                    <button 
                                        id="${formId}-submit"
                                        onclick="submitFeedback('${formId}', '${patientId}')"
                                        class="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition shadow-sm font-medium text-sm flex items-center gap-2"
                                    >
                                        <span>${submitLabel}</span>
                                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                                    </button>
                                </div>
                                <div id="${formId}-status" class="mt-3 hidden">
                                    <div class="flex items-center gap-2 text-sm"></div>
                                </div>
                            </div>
                            <!-- 成功消息区域（初始隐藏） -->
                            <div id="${formId}-success-area" class="hidden">
                                <div class="flex items-center gap-2 mb-3">
                                    <span class="text-xl">📝</span>
                                    <span class="font-semibold text-blue-800">${planLang === 'English' ? 'Feedback Recorded' : '反馈已记录'}</span>
                                </div>
                                <div class="text-sm text-blue-600 mb-4">
                                    ${planLang === 'English' 
                                        ? 'Thank you for your feedback! We have recorded this issue and will use it to improve our service.' 
                                        : '感谢您的反馈！我们已记录此问题，将用于改进服务质量。'}
                                </div>
                                <div class="flex items-center gap-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
                                    <span class="text-green-500 text-lg">✓</span>
                                    <span class="text-sm text-gray-700">
                                        ${planLang === 'English' 
                                            ? 'Please try asking your question again with more details.' 
                                            : '请用更详细的方式重新描述您的问题，我会更好地为您服务。'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    `;
                    wrapper.innerHTML += formHtml;
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
                        const maxH = 160;
                        const bars = items.map((i, idx) => {
                            const v = Number(i.value || 0);
                            const h = Math.max(2, Math.min(maxH, (v / maxVal) * maxH));
                            const color = palette[idx % palette.length];
                            return `<div class="flex flex-col items-center flex-1 min-w-[28px] max-w-[72px]"><div class="w-full rounded-t-md" style="height:${h}px; max-width:72px; background: linear-gradient(180deg, ${color} 0%, ${color}99 100%); box-shadow: 0 2px 6px rgba(0,0,0,0.12)"></div><div class="text-[10px] mt-2" style="color: var(--text-secondary);">${i.label || ''}</div><div class="text-[10px]" style="color: var(--text-secondary);">${v}${unit ? ' ' + unit : ''}</div></div>`;
                        }).join('');
                        wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">📊 ${title}</h3><div class="flex items-end justify-center gap-3" style="height:${maxH+40}px">${bars}</div></div>`;
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
                    wrapper.innerHTML += `<div class="border rounded-xl p-5 mt-3 shadow-sm" style="background: var(--card-bg); border-color: var(--border-color);"><h3 class="text-sm font-bold mb-3" style="color: var(--text-color);">🟠 ${title}</h3><div class="flex flex-col md:flex-row items-center gap-6">${chart}<div class="space-y-1">${legend}</div></div></div>`;
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
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
