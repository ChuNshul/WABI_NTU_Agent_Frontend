# -*- coding: utf-8 -*-
"""
GraphState — 用于 LLM 驱动 UI 生成的简化状态对象。
LLM 负责意图识别与数据提取，本状态仅聚焦核心输入/输出字段，而非节点专属处理步骤。
"""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


# 意图常量（LLM内部识别）
class Intent:
    FOOD_RECOGNITION = "food_recognition"
    RECOMMENDATION   = "recommendation"
    CLARIFICATION    = "clarification"
    GUARDRAIL        = "guardrail"
    GOAL_PLANNING    = "goal_planning"


# 图状态
class GraphState(TypedDict, total=False):
    # 输入（图运行前设置）
    user_input:  str                        # 用户原始文本
    patient_id:  str                        # 会话/用户标识
    language:    str                        # "Chinese" | "English"
    has_image:   bool                       # 是否上传图片
    llm_model:   str                        # LLM模型 "claude-3.5-sonnet" | "qwen-3.5"
    base_url:    str                        # 服务根地址，如 "http://127.0.0.1:8000"
    
    # LLM输出（LLM提取）
    intent:      Optional[str]               # 识别意图
    agent_response: Optional[str]             # LLM回复
    nutrition_facts: Optional[Dict[str, Any]] # 营养信息
    recommended_restaurants: Optional[List[Dict[str, Any]]] # 推荐餐厅
    food_detection_json: Optional[Dict[str, Any]] # 食物检测结果
    user_history: Optional[Dict[str, Any]]  # 用户历史
    data_source: Optional[str]               # 数据来源标识
    uploaded_image_url: Optional[str]         # 上传图片URL

    # UI生成器输出
    ui_plan:     Optional[Dict[str, Any]]
    html_content: Optional[str]
    rendered_image_url: Optional[str]
    logs: Optional[List[Dict[str, Any]]]

    # 检查器输出
    checked_output: Optional[Dict[str, Any]]
