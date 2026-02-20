# -*- coding: utf-8 -*-
"""
GraphState — Single shared state object that flows through every LangGraph node.

Fields are grouped by the node that populates them so the dataflow is easy
to follow at a glance.
"""

from typing import Any, Dict, List, Optional, Callable
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage


# ---------------------------------------------------------------------------
# Intent constants  (六种意图 / 6 intents)
# ---------------------------------------------------------------------------
class Intent:
    FOOD_RECOGNITION = "food_recognition"   # 食物识别
    RECOMMENDATION   = "recommendation"      # 餐厅推荐
    CORRECTION       = "correction"          # 纠错
    CLARIFICATION    = "clarification"       # 澄清
    GUARDRAIL        = "guardrail"           # 安全护栏
    GOAL_PLANNING    = "goal_planning"       # 计划 / 目标
    GENERIC          = "generic"             # 通用聊天（不匹配任何以上意图时）


# ---------------------------------------------------------------------------
# GraphState
# ---------------------------------------------------------------------------
class GraphState(TypedDict, total=False):
    # ── Input (set before the graph runs) ────────────────────────────────
    user_input:  str                        # raw text from the user
    patient_id:  str                        # session / user identifier
    language:    str                        # "Chinese" | "English"
    platform:    str                        # "web" | "wechat" | "whatsapp"
    has_image:   bool                       # whether an image was uploaded
    chat_history: List[BaseMessage]         # last N turns of conversation
    llm_model:   str                        # LLM模型选择 "claude-3.5-sonnet" | "qwen-3.5"
    
    # ── Context Memory (拼接后的总输入) ───────────────────────────────────
    context_input: str                      # 历史数据 + 当前输入的拼接结果
    relevant_history: List[Dict[str, Any]]  # 从历史中提取的相关上下文

    # ── IntentDetector output ─────────────────────────────────────────────
    intent:      str                        # one of Intent.*
    intent_confidence: float                # 意图识别置信度
    intent_reasoning: str                   # LLM分析意图的思考过程
    inherited_intent: bool                  # 是否继承自上一轮意图（意图跟随）

    # ── DataProvider output ───────────────────────────────────────────────
    agent_response:         Optional[str]
    nutrition_facts:        Optional[Dict[str, Any]]
    recommended_restaurants: Optional[List[Dict[str, Any]]]
    food_detection_json:    Optional[Dict[str, Any]]
    food_vis_path:          Optional[str]
    user_history:           Optional[Dict[str, Any]]
    data_source:            Optional[str]   # 数据来源标识

    # ── UIGenerator output ────────────────────────────────────────────────
    ui_plan:     Optional[Dict[str, Any]]

    # ── Renderer output ───────────────────────────────────────────────────
    rendered_output: Optional[Dict[str, Any]]
    
    # ── Function Registry (for data retrieval) ────────────────────────────
    data_functions: Dict[str, Callable]     # 意图 -> 数据获取函数的映射
