"""
GraphState dataclass for the LangGraph nutrition-orchestrator.

Milestone 1: core state schema with multi-turn conversation support.
Updated: Added patient_id field to support new architecture
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional
from langchain_core.messages import BaseMessage




@dataclass
class GraphState:
    """
    Central state object passed between LangGraph nodes.

    Attributes
    ----------
    patient_id:
        Patient ID passed from orchestrator agent (required for database operations).
    chat_history:
        Rolling list of the last N chat messages.
    user_input:
        Raw user payload: text or image bytes/URL.
    safety_passed:
        Result from guardrail (None until evaluated).
    intent:
        Router-selected branch (None until evaluated).
    nutrition_facts:
        Nutrition data produced by tools or agents.
    db_record_id:
        Identifier returned by persistence layer.
    agent_response:
        Final string returned to the user.
    """

    # 核心患者标识 - 从编排代理传递
    patient_id: Optional[str] = None
    
    chat_history: List[BaseMessage] = field(default_factory=list)
    # user_input: Any = None
    safety_passed: Optional[bool] = None
    intent: Optional[Literal["recognition", "recommendation", "exit"]] = None
    nutrition_facts: Optional[Dict[str, Any]] = None
    db_record_id: Optional[str] = None
    # agent_response: Optional[str] = None
    # 放宽类型，允许 dict
    agent_response: Optional[Any] = None

    # 与新 agent.py 对齐的输出字段
    location: Optional[Dict[str, Any]] = None
    recommended_restaurants: Optional[List[Dict[str, Any]]] = None

    # 错误透传（run_with_graph_state 失败时便于 Studio/日志显示）
    error: Optional[str] = None

    user_input: Optional[Any] = None
    # chat_history: List[BaseMessage] = field(default_factory=list)
    # agent_response: Optional[str] = None
    # nutrition_facts: Optional[Dict[str, Any]] = None
    # intent: Optional[str] = None
    # db_record_id: Optional[str] = None
    processed_message_count: int = 0  # 这个字段很重要
    # safety_passed: Optional[bool] = None
    
    # 调试和跟踪字段
    session_id: Optional[str] = None
    input_source_debug: Optional[str] = None
    is_new_studio_input: Optional[bool] = None
    reset_timestamp: Optional[str] = None
    
    # 食物检测相关数据（来自 food_storage_tools.py）
    food_detection_json: Optional[Any] = None
    food_vis_path: Optional[str] = None

    has_image: bool = False  # 新增字段，标记是否包含图片

    # UI Agent Output
    ui_plan: Optional[Dict[str, Any]] = None
