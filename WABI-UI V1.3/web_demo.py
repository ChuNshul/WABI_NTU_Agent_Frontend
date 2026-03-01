# -*- coding: utf-8 -*-
"""
  POST /api/ui     → 主聊天接口（返回 JSON）
  POST /api/reset  → 清空服务端聊天记录
  GET  /           → 返回单页 HTML 聊天界面
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Union

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel
from fastapi import Query

load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from UI.graph import graph
from UI.state import GraphState
from UI.llm_config import get_available_models, validate_model_name
from UI.mock_data import (
    MOCK_RECOGNITION_RESULT,
    MOCK_RECOMMENDATION_TABLE_RESULT,
    MOCK_GUARDRAIL_RESULT,
    MOCK_USER_HISTORY,
)
_SESSION: Dict[str, Any] = {
    "chat_history": [],
}

# 请求体
class ChatRequest(BaseModel):
    message:     Union[str, List[Dict[str, Any]]]
    patient_id:  Optional[str] = "demo_user"
    language:    Optional[str] = None
    device_info: Optional[str] = None    # mobile | tablet | desktop
    llm_model:   Optional[str] = None    # claude-3.5-sonnet | qwen-plus

# 静态文件、图片处理
from fastapi.staticfiles import StaticFiles
import base64, uuid

# FastAPI实例
app = FastAPI(title="Wabi UI Agent (LangGraph)")

BASE_DIR = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=ASSETS_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _parse_message(message: Union[str, List]) -> tuple[str, bool]:
    """
    从原始消息载荷中提取（文本内容，是否含图片）。
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

def _extract_intent_from_text(text: str, has_image: bool) -> Optional[str]:
    """
    从组合文本中提取 INTENT: 值；若不存在则根据是否有图片给出合理默认。
    仅返回五种合法意图之一。
    """
    try:
        m = re.search(r"\bINTENT:\s*([a-zA-Z_]+)", text)
        if m:
            val = m.group(1).strip().lower()
            allowed = {
                "food_recognition",
                "recommendation",
                "clarification",
                "guardrail",
                "goal_planning",
            }
            if val in allowed:
                return val
        # 默认策略：有图片则食物识别，否则澄清
        return "food_recognition" if has_image else "clarification"
    except Exception:
        return "food_recognition" if has_image else "clarification"

def _extract_uploaded_image_data(message: Union[str, List]) -> Optional[str]:
    """
    从请求消息中提取数据URI格式的图片（data:image/...;base64,XXXX）。
    """
    if isinstance(message, list):
        for item in message:
            if isinstance(item, dict):
                if item.get("type") == "image_url":
                    url = (item.get("image_url") or {}).get("url")
                    if isinstance(url, str) and url.startswith("data:image/"):
                        return url
                elif item.get("type") == "image":
                    # 允许直接在 'data' 或 'url' 字段中传递
                    data = item.get("data") or item.get("url")
                    if isinstance(data, str) and data.startswith("data:image/"):
                        return data
    return None

def _save_uploaded_image(data_uri: str) -> Optional[str]:
    """
    将 data URI 图片保存到 ASSETS_DIR 并返回可通过 /static 访问的URL。
    """
    try:
        # data:image/png;base64,XXXX
        header, b64 = data_uri.split(",", 1)
        mime = header.split(";")[0].split(":")[1]  # image/png
        ext = "png"
        if "/" in mime:
            ext = mime.split("/")[1]
            if ext == "jpeg":
                ext = "jpg"
        filename = f"upload_{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(ASSETS_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(b64))
        return f"/static/{filename}"
    except Exception as e:
        print(f"[web_demo] Failed to save uploaded image: {e}")
        return None

# 模拟数据 API（供前端选择使用）
@app.get("/api/mockdata/categories")
async def mockdata_categories():
    cats = [
        "MOCK_RECOGNITION_RESULT",
        "MOCK_RECOMMENDATION_TABLE_RESULT",
        "MOCK_GUARDRAIL_RESULT",
        "MOCK_USER_HISTORY",
    ]
    return JSONResponse({"categories": cats})

@app.get("/api/mockdata")
async def mockdata(category: str = Query(..., description="Mock data category")):
    try:
        if category == "MOCK_RECOGNITION_RESULT":
            return JSONResponse({"MOCK_RECOGNITION_RESULT": MOCK_RECOGNITION_RESULT})
        elif category == "MOCK_RECOMMENDATION_TABLE_RESULT":
            return JSONResponse({"MOCK_RECOMMENDATION_TABLE_RESULT": MOCK_RECOMMENDATION_TABLE_RESULT})
        elif category == "MOCK_GUARDRAIL_RESULT":
            return JSONResponse({"MOCK_GUARDRAIL_RESULT": MOCK_GUARDRAIL_RESULT})
        elif category == "MOCK_USER_HISTORY":
            return JSONResponse({"MOCK_USER_HISTORY": MOCK_USER_HISTORY})
        else:
            return JSONResponse({"message": "none"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# API 端点
@app.post("/api/ui")
async def get_ui_response(chat_request: ChatRequest, request: Request):
    base_url = str(request.base_url).rstrip('/')
    text_content, has_image = _parse_message(chat_request.message)
    language = chat_request.language or "Chinese"
    uploaded_image_url = None
    if has_image:
        data_uri = _extract_uploaded_image_data(chat_request.message)
        if data_uri:
            uploaded_image_url = _save_uploaded_image(data_uri)
    _SESSION["chat_history"].append(HumanMessage(content=text_content))
    from UI.llm_config import DEFAULT_MODEL
    llm_model = chat_request.llm_model or DEFAULT_MODEL
    parsed_intent = _extract_intent_from_text(text_content, has_image)
    initial_state: GraphState = {
        "user_input":   text_content,
        "patient_id":   chat_request.patient_id or "demo_user",
        "language":     language,
        "has_image":    has_image,
        "chat_history": _SESSION["chat_history"][-10:],   # last 10 turns
        "llm_model":    llm_model,                        # LLM模型选择
        "uploaded_image_url": uploaded_image_url,
        "base_url":     base_url,
        "intent":       parsed_intent,
    }
    try:
        final_state: GraphState = await asyncio.to_thread(graph.invoke, initial_state)
        rendered = final_state.get("checked_output")
        if rendered:
            _SESSION["chat_history"].append(
                AIMessage(content="", additional_kwargs={"ui_plan": rendered})
            )
            return JSONResponse({"web_ui_plan": rendered})
        else:
            return JSONResponse({"error": "No rendered output"}, status_code=500)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)

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
    return JSONResponse({"status": "success", "message": "Session reset"})

# 静态 HTML 外壳
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
                v1.2 (Adaptive)<br>Project Wabi-C
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
                        <p class="text-sm opacity-70">Version: 1.2 (Adaptive UI)</p>
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
                    
                    <!-- 意图选择 -->
                    <div class="relative whitespace-nowrap" id="intentSelectorContainer" style="z-index: 100;">
                        <select id="intentSelect" class="hidden">
                            <option value="food_recognition">Food Recognition</option>
                            <option value="recommendation">Recommendation</option>
                            <option value="clarification">Clarification</option>
                            <option value="guardrail">Guardrail</option>
                            <option value="goal_planning">Goal Planning</option>
                        </select>
                        <button type="button"
                            onclick="event.stopPropagation(); toggleIntentDropdown();"
                            class="flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border"
                            style="color: var(--text-secondary); background: var(--bg-color); border-color: var(--border-color); white-space: nowrap;"
                            id="intentSelectorBtn">
                            <span id="currentIntentLabel" style="white-space: nowrap;"></span>
                            <svg id="intentDropdownArrow" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="transition-transform duration-200 opacity-60 flex-shrink-0">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </button>
                        <div id="intentDropdownMenu" 
                            class="hidden absolute bottom-full left-0 mb-2 w-44 rounded-lg shadow-lg border py-1 transform origin-bottom-left transition-all duration-200 scale-95 opacity-0"
                            style="background: var(--card-bg); border-color: var(--border-color); box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
                            <button type="button" 
                                onclick="event.stopPropagation(); selectIntent('food_recognition');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="intentBtnFoodRecognition">
                                <span id="intentLabelFoodRecognition"></span>
                                <span id="intentMarkFoodRecognition" class="text-xs opacity-70">✓</span>
                            </button>
                            <button type="button" 
                                onclick="event.stopPropagation(); selectIntent('recommendation');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="intentBtnRecommendation">
                                <span id="intentLabelRecommendation"></span>
                                <span id="intentMarkRecommendation" class="text-xs opacity-70">✓</span>
                            </button>
                            <button type="button" 
                                onclick="event.stopPropagation(); selectIntent('clarification');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="intentBtnClarification">
                                <span id="intentLabelClarification"></span>
                                <span id="intentMarkClarification" class="text-xs opacity-70">✓</span>
                            </button>
                            <button type="button" 
                                onclick="event.stopPropagation(); selectIntent('guardrail');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="intentBtnGuardrail">
                                <span id="intentLabelGuardrail"></span>
                                <span id="intentMarkGuardrail" class="text-xs opacity-70">✓</span>
                            </button>
                            <button type="button" 
                                onclick="event.stopPropagation(); selectIntent('goal_planning');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="intentBtnGoalPlanning">
                                <span id="intentLabelGoalPlanning"></span>
                                <span id="intentMarkGoalPlanning" class="text-xs opacity-70">✓</span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- 上游数据选择（多选） -->
                    <div class="relative whitespace-nowrap" id="upstreamSelectorContainer" style="z-index: 100;">
                        <select id="upstreamSelect" multiple class="hidden">
                            <option value="MOCK_RECOGNITION_RESULT">MOCK_RECOGNITION_RESULT</option>
                            <option value="MOCK_RECOMMENDATION_TABLE_RESULT">MOCK_RECOMMENDATION_TABLE_RESULT</option>
                            <option value="MOCK_GUARDRAIL_RESULT">MOCK_GUARDRAIL_RESULT</option>
                            <option value="MOCK_USER_HISTORY">MOCK_USER_HISTORY</option>
                        </select>
                        <button type="button"
                            onclick="event.stopPropagation(); toggleUpstreamDropdown();"
                            class="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border"
                            style="color: var(--text-secondary); background: var(--bg-color); border-color: var(--border-color); white-space: nowrap;"
                            id="upstreamSelectorBtn">
                            <span id="currentUpstreamLabel" style="white-space: nowrap;"></span>
                            <span id="upstreamCountBadge" class="hidden px-1.5 py-0.5 rounded-full text-[11px]" style="background: rgba(59, 130, 246, 0.12); color: #3b82f6;"></span>
                            <svg id="upstreamDropdownArrow" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="transition-transform duration-200 opacity-60 flex-shrink-0">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </button>
                        <div id="upstreamDropdownMenu" 
                            class="hidden absolute bottom-full left-0 mb-2 w-56 rounded-lg shadow-lg border py-1 transform origin-bottom-left transition-all duration-200 scale-95 opacity-0"
                            style="background: var(--card-bg); border-color: var(--border-color); box-shadow: 0 4px 20px rgba(0,0,0,0.15);">
                            <button type="button" 
                                onclick="event.stopPropagation(); toggleUpstreamOption('MOCK_RECOGNITION_RESULT');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="upstreamBtnMOCK_RECOGNITION_RESULT">
                                <span id="upstreamLabelMOCK_RECOGNITION_RESULT"></span>
                                <span id="upstreamMarkMOCK_RECOGNITION_RESULT" class="text-xs opacity-70">✓</span>
                            </button>
                            <button type="button" 
                                onclick="event.stopPropagation(); toggleUpstreamOption('MOCK_RECOMMENDATION_TABLE_RESULT');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="upstreamBtnMOCK_RECOMMENDATION_TABLE_RESULT">
                                <span id="upstreamLabelMOCK_RECOMMENDATION_TABLE_RESULT"></span>
                                <span id="upstreamMarkMOCK_RECOMMENDATION_TABLE_RESULT" class="text-xs opacity-70">✓</span>
                            </button>
                            <button type="button" 
                                onclick="event.stopPropagation(); toggleUpstreamOption('MOCK_GUARDRAIL_RESULT');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="upstreamBtnMOCK_GUARDRAIL_RESULT">
                                <span id="upstreamLabelMOCK_GUARDRAIL_RESULT"></span>
                                <span id="upstreamMarkMOCK_GUARDRAIL_RESULT" class="text-xs opacity-70">✓</span>
                            </button>
                            <button type="button" 
                                onclick="event.stopPropagation(); toggleUpstreamOption('MOCK_USER_HISTORY');" 
                                class="w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center justify-between hover:opacity-80"
                                style="color: var(--text-color);"
                                id="upstreamBtnMOCK_USER_HISTORY">
                                <span id="upstreamLabelMOCK_USER_HISTORY"></span>
                                <span id="upstreamMarkMOCK_USER_HISTORY" class="text-xs opacity-70">✓</span>
                            </button>
                            <div class="px-4 py-2 text-xs opacity-70" style="color: var(--text-secondary);">
                                <span id="upstreamHint"></span>
                            </div>
                            <div class="px-4 pb-2 flex items-center justify-between gap-2">
                                <button type="button"
                                    onclick="event.stopPropagation(); clearUpstreamSelection();"
                                    class="px-2 py-1 rounded-lg text-xs border hover:opacity-80"
                                    style="color: var(--text-secondary); background: var(--card-bg); border-color: var(--border-color);"
                                    id="upstreamClearBtn"></button>
                                <button type="button"
                                    onclick="event.stopPropagation(); closeUpstreamDropdown();"
                                    class="px-2 py-1 rounded-lg text-xs border hover:opacity-80"
                                    style="color: var(--text-secondary); background: var(--card-bg); border-color: var(--border-color);"
                                    id="upstreamDoneBtn"></button>
                            </div>
                        </div>
                    </div>
                    
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
                'drag_upload_title': '拖拽图片到此处，或点击上传',
                'drag_upload_sub': '支持 JPG、PNG 等常见图片格式'
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
                'drag_upload_title': 'Drag image here or click to upload',
                'drag_upload_sub': 'Supports JPG, PNG and other common formats'
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
        
        let currentIntent = 'food_recognition';
        
        const INTENT_NAMES = {
            'Chinese': {
                'food_recognition': '食物识别',
                'recommendation': '餐厅推荐',
                'clarification': '澄清追问',
                'guardrail': '安全护栏',
                'goal_planning': '目标规划'
            },
            'English': {
                'food_recognition': 'Food Recognition',
                'recommendation': 'Recommendation',
                'clarification': 'Clarification',
                'guardrail': 'Guardrail',
                'goal_planning': 'Goal Planning'
            }
        };
        
        const UPSTREAM_NAMES = {
            'Chinese': {
                'title': '上游数据',
                'hint': '可多选或不选',
                'clear': '清空',
                'done': '完成',
                'MOCK_RECOGNITION_RESULT': '食物识别结果',
                'MOCK_RECOMMENDATION_TABLE_RESULT': '推荐餐厅',
                'MOCK_GUARDRAIL_RESULT': '安全护栏',
                'MOCK_USER_HISTORY': '用户历史'
            },
            'English': {
                'title': 'Upstream',
                'hint': 'Multi-select or none',
                'clear': 'Clear',
                'done': 'Done',
                'MOCK_RECOGNITION_RESULT': 'Recognition Result',
                'MOCK_RECOMMENDATION_TABLE_RESULT': 'Recommendation Table',
                'MOCK_GUARDRAIL_RESULT': 'Guardrail Result',
                'MOCK_USER_HISTORY': 'User History'
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

        let isIntentDropdownOpen = false;
        
        function toggleIntentDropdown() {
            if (isIntentDropdownOpen) {
                closeIntentDropdown();
            } else {
                openIntentDropdown();
            }
        }
        
        function openIntentDropdown() {
            if (typeof closeModelDropdown === 'function') closeModelDropdown();
            if (typeof closeUpstreamDropdown === 'function') closeUpstreamDropdown();
            
            const menu = document.getElementById('intentDropdownMenu');
            const arrow = document.getElementById('intentDropdownArrow');
            if (!menu || !arrow) return;
            
            menu.classList.remove('hidden');
            setTimeout(() => {
                menu.classList.remove('scale-95', 'opacity-0');
                menu.classList.add('scale-100', 'opacity-100');
            }, 10);
            
            arrow.style.transform = 'rotate(180deg)';
            isIntentDropdownOpen = true;
            document.addEventListener('click', closeIntentDropdownOutside);
        }
        
        function closeIntentDropdown() {
            const menu = document.getElementById('intentDropdownMenu');
            const arrow = document.getElementById('intentDropdownArrow');
            if (!menu || !arrow) return;
            
            menu.classList.remove('scale-100', 'opacity-100');
            menu.classList.add('scale-95', 'opacity-0');
            arrow.style.transform = 'rotate(0deg)';
            
            setTimeout(() => {
                menu.classList.add('hidden');
            }, 200);
            
            isIntentDropdownOpen = false;
            document.removeEventListener('click', closeIntentDropdownOutside);
        }
        
        function closeIntentDropdownOutside(event) {
            const container = document.getElementById('intentSelectorContainer');
            if (container && !container.contains(event.target)) {
                closeIntentDropdown();
            }
        }
        
        function selectIntent(intentVal) {
            if (!intentVal) return;
            currentIntent = intentVal;
            const sel = document.getElementById('intentSelect');
            if (sel) sel.value = intentVal;
            updateIntentUI();
            closeIntentDropdown();
        }
        
        function updateIntentUI() {
            const names = INTENT_NAMES[currentLang] || INTENT_NAMES['English'];
            const currentLabel = document.getElementById('currentIntentLabel');
            if (currentLabel) currentLabel.textContent = names[currentIntent] || currentIntent;
            
            const sel = document.getElementById('intentSelect');
            if (sel) sel.value = currentIntent;
            
            const map = [
                ['food_recognition', 'FoodRecognition'],
                ['recommendation', 'Recommendation'],
                ['clarification', 'Clarification'],
                ['guardrail', 'Guardrail'],
                ['goal_planning', 'GoalPlanning']
            ];
            
            for (const [key, suffix] of map) {
                const labelEl = document.getElementById(`intentLabel${suffix}`);
                if (labelEl) labelEl.textContent = names[key] || key;
                
                const btn = document.getElementById(`intentBtn${suffix}`);
                const mark = document.getElementById(`intentMark${suffix}`);
                const selected = currentIntent === key;
                if (mark) mark.style.visibility = selected ? 'visible' : 'hidden';
                if (btn) {
                    if (selected) {
                        btn.style.background = 'rgba(59, 130, 246, 0.1)';
                        btn.style.color = '#3b82f6';
                    } else {
                        btn.style.background = '';
                        btn.style.color = 'var(--text-color)';
                    }
                }
            }
        }
        
        let isUpstreamDropdownOpen = false;
        
        function toggleUpstreamDropdown() {
            if (isUpstreamDropdownOpen) {
                closeUpstreamDropdown();
            } else {
                openUpstreamDropdown();
            }
        }
        
        function openUpstreamDropdown() {
            if (typeof closeModelDropdown === 'function') closeModelDropdown();
            if (typeof closeIntentDropdown === 'function') closeIntentDropdown();
            
            const menu = document.getElementById('upstreamDropdownMenu');
            const arrow = document.getElementById('upstreamDropdownArrow');
            if (!menu || !arrow) return;
            
            menu.classList.remove('hidden');
            setTimeout(() => {
                menu.classList.remove('scale-95', 'opacity-0');
                menu.classList.add('scale-100', 'opacity-100');
            }, 10);
            
            arrow.style.transform = 'rotate(180deg)';
            isUpstreamDropdownOpen = true;
            document.addEventListener('click', closeUpstreamDropdownOutside);
        }
        
        function closeUpstreamDropdown() {
            const menu = document.getElementById('upstreamDropdownMenu');
            const arrow = document.getElementById('upstreamDropdownArrow');
            if (!menu || !arrow) return;
            
            menu.classList.remove('scale-100', 'opacity-100');
            menu.classList.add('scale-95', 'opacity-0');
            arrow.style.transform = 'rotate(0deg)';
            
            setTimeout(() => {
                menu.classList.add('hidden');
            }, 200);
            
            isUpstreamDropdownOpen = false;
            document.removeEventListener('click', closeUpstreamDropdownOutside);
        }
        
        function closeUpstreamDropdownOutside(event) {
            const container = document.getElementById('upstreamSelectorContainer');
            if (container && !container.contains(event.target)) {
                closeUpstreamDropdown();
            }
        }
        
        function toggleUpstreamOption(category) {
            const sel = document.getElementById('upstreamSelect');
            if (!sel || !category) return;
            const opt = Array.from(sel.options).find(o => o.value === category);
            if (!opt) return;
            opt.selected = !opt.selected;
            updateUpstreamUI();
        }
        
        function clearUpstreamSelection() {
            const sel = document.getElementById('upstreamSelect');
            if (!sel) return;
            Array.from(sel.options).forEach(o => { o.selected = false; });
            updateUpstreamUI();
        }
        
        function updateUpstreamUI() {
            const names = UPSTREAM_NAMES[currentLang] || UPSTREAM_NAMES['English'];
            const labelEl = document.getElementById('currentUpstreamLabel');
            const badgeEl = document.getElementById('upstreamCountBadge');
            const hintEl = document.getElementById('upstreamHint');
            const clearBtn = document.getElementById('upstreamClearBtn');
            const doneBtn = document.getElementById('upstreamDoneBtn');
            
            if (hintEl) hintEl.textContent = names.hint || '';
            if (clearBtn) clearBtn.textContent = names.clear || 'Clear';
            if (doneBtn) doneBtn.textContent = names.done || 'Done';
            
            const sel = document.getElementById('upstreamSelect');
            const selected = sel ? Array.from(sel.selectedOptions).map(o => o.value) : [];
            
            if (labelEl) labelEl.textContent = names.title || 'Upstream';
            if (badgeEl) {
                if (selected.length > 0) {
                    badgeEl.textContent = String(selected.length);
                    badgeEl.classList.remove('hidden');
                } else {
                    badgeEl.classList.add('hidden');
                }
            }
            
            const options = [
                'MOCK_RECOGNITION_RESULT',
                'MOCK_RECOMMENDATION_TABLE_RESULT',
                'MOCK_GUARDRAIL_RESULT',
                'MOCK_USER_HISTORY'
            ];
            
            for (const key of options) {
                const label = document.getElementById(`upstreamLabel${key}`);
                if (label) label.textContent = names[key] || key;
                
                const btn = document.getElementById(`upstreamBtn${key}`);
                const mark = document.getElementById(`upstreamMark${key}`);
                const isSelected = selected.includes(key);
                
                if (mark) mark.style.visibility = isSelected ? 'visible' : 'hidden';
                if (btn) {
                    if (isSelected) {
                        btn.style.background = 'rgba(59, 130, 246, 0.1)';
                        btn.style.color = '#3b82f6';
                    } else {
                        btn.style.background = '';
                        btn.style.color = 'var(--text-color)';
                    }
                }
            }
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

            // Update model selector language
            updateModelSelectorLanguage(lang);
            updateIntentUI();
            updateUpstreamUI();
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

        async function regenerateMessage(userMsgId, aiMsgId) {
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
            const originalText = userMsg.text || '';
            const userOnlyText = (() => {
                const marker = 'USER:\\n';
                const idx = originalText.lastIndexOf(marker);
                if (idx === -1) return originalText;
                return originalText.slice(idx + marker.length);
            })();
            const intentSel = document.getElementById('intentSelect');
            const intentVal = intentSel ? intentSel.value : 'food_recognition';
            const upstreamJson = await getCombinedUpstreamJson();
            const text = buildCombinedText(userOnlyText, intentVal, upstreamJson);
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
                payload = { message: [{ "type": "image_url", "image_url": {"url": currentImageBase64} }], language: currentLang, device_info: deviceInfo, llm_model: currentModel };
                if (text) payload.message.unshift({"type": "text", "text": text});
            } else {
                payload = { message: text, language: currentLang, device_info: deviceInfo, llm_model: currentModel };
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
                    const msg = await response.json();
                    const aiMsgIndex = chatState.findIndex(m => m.id === newLoadingId);
                    if (aiMsgIndex !== -1) {
                        if (msg.web_ui_plan) {
                            let plan = msg.web_ui_plan;
                            if (plan && plan.adapted) {
                                const textContent = plan.items.map(item => {
                                    if(item.type === 'text') return item.content;
                                    if(item.type === 'image') return '<img src="' + item.url + '" style="max-width:100%; border-radius:4px; margin-top:5px;">';
                                    return '';
                                }).join('\\n\\n');
                                plan = { sections: [{ type: 'text', content: textContent }] };
                            }
                            chatState[aiMsgIndex] = { id: newLoadingId, role: 'ai', isLoading: false, isStreaming: false, plan: plan };
                        } else {
                            chatState[aiMsgIndex] = { id: newLoadingId, role: 'ai', isLoading: false, isStreaming: false, error: msg.error || 'Server Error' };
                        }
                        renderChatHistory();
                    }
                } catch (error) {
                    const aiMsgIndex = chatState.findIndex(m => m.id === newLoadingId);
                    if (aiMsgIndex !== -1) {
                        chatState[aiMsgIndex] = { id: newLoadingId, role: 'ai', isLoading: false, isStreaming: false, error: "Network Error" };
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
                        const sections = (msg.plan.sections || []);
                        const imgSec = sections.find(s => s.type === 'image_display' && s.url);
                        if (imgSec) {
                            const alt = imgSec.alt || 'Generated Image';
                            contentHtml = `<div class="message-bubble w-full"><div class="mt-3 border rounded-xl overflow-hidden shadow-sm"><a href="${imgSec.url}" target="_blank" rel="noopener noreferrer"><img src="${imgSec.url}" alt="${alt}" class="w-full h-auto object-cover"/></a></div></div>`;
                        } else {
                            const summary = msg.plan.summary || '';
                            contentHtml = `<div class="message-bubble">${summary}</div>`;
                        }
                    } else if (msg.content) {
                         contentHtml = `<div class="message-bubble">${msg.content}</div>`;
                    } else if (msg.error) {
                        contentHtml = `<div class="message-bubble text-red-600">Error: ${msg.error}</div>`;
                    }
                    
                    // Removed actions from AI side
                    aiContainer.innerHTML = `<div class="avatar ai">AI</div>${contentHtml}`;
                    history.appendChild(aiContainer);
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

        function buildCombinedText(userText, intentVal, upstreamJson) {
            let combined = "";
            if (intentVal) combined += `INTENT: ${intentVal}\n`;
            if (upstreamJson) combined += `DATA_JSON:\n${upstreamJson}\n`;
            if (userText) combined += `USER:\n${userText}`;
            return combined || userText || "";
        }
        
        async function getCombinedUpstreamJson() {
            try {
                const sel = document.getElementById('upstreamSelect');
                if (!sel) return '';
                const selected = Array.from(sel.selectedOptions).map(o => o.value).filter(v => v);
                if (!selected.length) return '';
                const combined = {};
                await Promise.all(selected.map(async (cat) => {
                    const res = await fetch(`/api/mockdata?category=${encodeURIComponent(cat)}`);
                    const data = await res.json();
                    Object.assign(combined, data);
                }));
                return JSON.stringify(combined, null, 2);
            } catch (e) {
                console.error(e);
                return '';
            }
        }
        
        async function processMessage(text, intentVal = null, upstreamJson = '') {
            if (!text && !currentImageBase64) return;
            const uniqueId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
            const userMsgId = 'msg-' + uniqueId;
            const loadingId = 'loading-' + uniqueId;
            
            // 如果未传入，则从DOM读取
            if (!intentVal) {
                const intentSel = document.getElementById('intentSelect');
                intentVal = intentSel ? intentSel.value : 'food_recognition';
            }
            if (!upstreamJson) {
                upstreamJson = await getCombinedUpstreamJson();
            }
            const combinedText = buildCombinedText(text, intentVal, upstreamJson);
            
            chatState.push({ id: userMsgId, role: 'user', text: combinedText, image: currentImageBase64, aiPairId: loadingId });
            chatState.push({ id: loadingId, role: 'ai', isLoading: true, step: 0 });
            renderChatHistory();

            let payload;
            const deviceInfo = getDeviceInfo();
            if (currentImageBase64) {
                payload = { message: [{ "type": "image_url", "image_url": {"url": currentImageBase64} }], language: currentLang, device_info: deviceInfo };
                if (combinedText) payload.message.unshift({"type": "text", "text": combinedText});
            } else {
                payload = { message: combinedText || text, language: currentLang, device_info: deviceInfo };
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
                const msg = await response.json();
                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                if (aiMsgIndex !== -1) {
                    if (msg.web_ui_plan) {
                        let plan = msg.web_ui_plan;
                        if (plan && plan.adapted) {
                            const textContent = plan.items.map(item => {
                                if(item.type === 'text') return item.content;
                                if(item.type === 'image') return '<img src=\"' + item.url + '\" style=\"max-width:100%; border-radius:4px; margin-top:5px;\">';
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
                    } else {
                        chatState[aiMsgIndex] = { 
                            id: loadingId, 
                            role: 'ai', 
                            isLoading: false, 
                            isStreaming: false,
                            error: msg.error || 'Server Error' 
                        };
                    }
                    renderChatHistory();
                }
            } catch (error) {
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
            } finally {
                setLoadingState(false);
            }
        }

    </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
