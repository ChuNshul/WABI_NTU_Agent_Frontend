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
import re
import threading
import time
from typing import Any, Dict, List, Optional, Union

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

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
    MOCK_USER_HISTORY,
)

_RUN_LOGS: Dict[str, Any] = {}
_RUN_LOGS_LOCK = threading.Lock()
_DEBUG_LOCK = threading.Lock()

def start_run_log(run_id: str) -> None:
    now = time.time()
    with _RUN_LOGS_LOCK:
        _RUN_LOGS[run_id] = {
            "start_time": now,
            "logs": [],
            "status": "running",
        }

def append_run_log(run_id: str, message: str, level: str = "info") -> None:
    now = time.time()
    entry = {
        "t": now,
        "level": level,
        "message": str(message),
    }
    with _RUN_LOGS_LOCK:
        run = _RUN_LOGS.get(run_id)
        if not run:
            run = {
                "start_time": now,
                "logs": [],
                "status": "running",
            }
            _RUN_LOGS[run_id] = run
        run_logs = run.setdefault("logs", [])
        run_logs.append(entry)
        if len(run_logs) > 200:
            run["logs"] = run_logs[-200:]

def finish_run_log(run_id: str, status: str) -> None:
    now = time.time()
    with _RUN_LOGS_LOCK:
        run = _RUN_LOGS.get(run_id)
        if not run:
            return
        run["status"] = status
        run["end_time"] = now

def get_run_log_snapshot(run_id: str) -> Dict[str, Any]:
    now = time.time()
    with _RUN_LOGS_LOCK:
        run = _RUN_LOGS.get(run_id)
        if not run:
            return {"status": "not_found"}
        start_time = float(run.get("start_time", now) or now)
        elapsed = max(0.0, now - start_time)
        logs = list(run.get("logs", []))
        if len(logs) > 50:
            logs = logs[-50:]
        status = run.get("status") or "running"
    return {
        "status": status,
        "elapsed_ms": int(elapsed * 1000),
        "logs": logs,
    }

def _get_debug_enabled() -> bool:
    return os.getenv("UI_DEBUG") == "1"

def _set_debug_enabled(enable: bool) -> None:
    with _DEBUG_LOCK:
        os.environ["UI_DEBUG"] = "1" if enable else "0"

# 请求体
class ChatRequest(BaseModel):
    message:     Union[str, List[Dict[str, Any]]]
    patient_id:  Optional[str] = "demo_user"
    language:    Optional[str] = None
    device_info: Optional[str] = None    # mobile | tablet | desktop
    llm_model:   Optional[str] = None    # claude-3.5-sonnet | qwen-plus
    run_id:      Optional[str] = None

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
    从组合文本中提取 INTENT: 值。
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
    except Exception as e:
        print(f"[web_demo] Intent extraction error: {e}")
        return None

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
    run_id = chat_request.run_id or f"run_{uuid.uuid4().hex}"
    start_run_log(run_id)
    append_run_log(run_id, "Received request and starting graph invocation")
    text_content, has_image = _parse_message(chat_request.message)
    language = chat_request.language or "Chinese"
    uploaded_image_url = None
    if has_image:
        data_uri = _extract_uploaded_image_data(chat_request.message)
        if data_uri:
            uploaded_image_url = _save_uploaded_image(data_uri)
    from UI.llm_config import DEFAULT_MODEL
    llm_model = chat_request.llm_model or DEFAULT_MODEL
    parsed_intent = _extract_intent_from_text(text_content, has_image)
    initial_state: GraphState = {
        "user_input":   text_content,
        "patient_id":   chat_request.patient_id or "demo_user",
        "language":     language,
        "has_image":    has_image,
        "llm_model":    llm_model,
        "uploaded_image_url": uploaded_image_url,
        "base_url":     base_url,
        "intent":       parsed_intent,
        "run_id":       run_id,
    }
    try:
        append_run_log(run_id, "Invoking LangGraph pipeline")
        final_state: GraphState = await asyncio.to_thread(graph.invoke, initial_state)
        append_run_log(run_id, "LangGraph pipeline finished")
        rendered = final_state.get("checked_output")
        if rendered:
            finish_run_log(run_id, "completed")
            append_run_log(run_id, "Response ready")
            return JSONResponse({"web_ui_plan": rendered, "run_id": run_id})
        else:
            finish_run_log(run_id, "error")
            append_run_log(run_id, "No rendered output", level="error")
            return JSONResponse({"error": "No rendered output", "run_id": run_id}, status_code=500)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        finish_run_log(run_id, "error")
        append_run_log(run_id, f"Exception: {exc}", level="error")
        return JSONResponse({"error": str(exc), "run_id": run_id}, status_code=500)


@app.get("/api/run_log/{run_id}")
async def get_run_log(run_id: str):
    snapshot = get_run_log_snapshot(run_id)
    return JSONResponse(snapshot)

@app.get("/api/debug")
async def get_debug():
    return JSONResponse({"debug": _get_debug_enabled()})

class DebugSwitch(BaseModel):
    enable: bool

@app.post("/api/debug")
async def set_debug(switch: DebugSwitch):
    _set_debug_enabled(bool(switch.enable))
    return JSONResponse({"debug": _get_debug_enabled()})

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
    return JSONResponse({"status": "success", "message": "Session reset"})

# 静态 HTML 外壳
@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Read HTML content from external file
    html_file_path = os.path.join(os.path.dirname(__file__), "web.html")
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>Wabi UI Agent</title>
        </head>
        <body>
            <h1>web.html 未找到</h1>
            <p>请将 <code>web.html</code> 放置于当前脚本同级目录。</p>
        </body>
        </html>
        """
        

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True, access_log=False, log_level="warning")
