# -*- coding: utf-8 -*-
"""
DataProvider Node (Function Call Based)
---------------------------------------
根据意图调用对应的数据获取函数，以函数调用的形式获取数据。

支持的数据获取函数：
  - get_food_recognition_data: 获取食物识别相关数据
  - get_recommendation_data: 获取餐厅推荐数据
  - get_guardrail_data: 获取安全护栏数据
  - get_correction_data: 获取纠错响应数据
  - get_clarification_data: 获取澄清响应数据
  - get_goal_planning_data: 获取目标规划数据
  - get_generic_data: 获取通用聊天数据
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Callable
from functools import wraps

from UI.state import GraphState, Intent
from UI.mock_data import (
    MOCK_RECOGNITION_RESULT,
    MOCK_RECOMMENDATION_TABLE_RESULT,
    MOCK_GUARDRAIL_RESULT,
    MOCK_USER_HISTORY,
)


# ---------------------------------------------------------------------------
# Data Retrieval Functions Registry
# ---------------------------------------------------------------------------

# 用于存储数据获取函数的注册表
_data_function_registry: Dict[str, Callable] = {}


def register_data_function(intent: str):
    """装饰器：注册数据获取函数到指定意图"""
    def decorator(func: Callable) -> Callable:
        _data_function_registry[intent] = func
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_data_function(intent: str) -> Optional[Callable]:
    """获取指定意图对应的数据获取函数"""
    return _data_function_registry.get(intent)


def list_available_functions() -> list:
    """列出所有可用的数据获取函数"""
    return list(_data_function_registry.keys())


# ---------------------------------------------------------------------------
# Data Retrieval Functions
# ---------------------------------------------------------------------------

@register_data_function(Intent.FOOD_RECOGNITION)
def get_food_recognition_data(state: GraphState) -> Dict[str, Any]:
    """
    获取食物识别相关数据
    
    Args:
        state: 当前图状态
        
    Returns:
        包含食物识别数据的字典
    """
    has_image = state.get("has_image", False)
    
    print(f"[DataProvider] 调用 get_food_recognition_data (has_image={has_image})")
    
    if not has_image:
        # 没有图片，返回提示信息
        return {
            "agent_response": "请上传一张食物图片，我将为您分析其中的营养成分。",
            "nutrition_facts": None,
            "food_detection_json": None,
            "data_source": "food_recognition_prompt",
        }
    
    # 使用模拟数据（实际生产环境应调用真实API）
    result = MOCK_RECOGNITION_RESULT
    return {
        "agent_response": result["agent_response"],
        "nutrition_facts": result["nutrition_facts"],
        "food_detection_json": result.get("food_detection_json"),
        "data_source": "mock_food_recognition",
    }


@register_data_function(Intent.RECOMMENDATION)
def get_recommendation_data(state: GraphState) -> Dict[str, Any]:
    """
    获取餐厅推荐数据
    
    Args:
        state: 当前图状态
        
    Returns:
        包含餐厅推荐数据的字典
    """
    print(f"[DataProvider] 调用 get_recommendation_data")
    
    # 从上下文中提取位置信息（如果有）
    context_input = state.get("context_input", "")
    location_hint = None
    if "附近" in context_input or "nearby" in context_input.lower():
        location_hint = "nearby"
    
    # 使用模拟数据（实际生产环境应调用真实API，如Google Places API）
    result = MOCK_RECOMMENDATION_TABLE_RESULT
    return {
        "agent_response": result["agent_response"],
        "recommended_restaurants": result["recommended_restaurants"],
        "data_source": "mock_recommendation",
        "location_hint": location_hint,
    }


@register_data_function(Intent.GUARDRAIL)
def get_guardrail_data(state: GraphState) -> Dict[str, Any]:
    """
    获取安全护栏数据（心理健康支持资源）
    
    Args:
        state: 当前图状态
        
    Returns:
        包含安全资源数据的字典
    """
    print(f"[DataProvider] 调用 get_guardrail_data")
    
    result = MOCK_GUARDRAIL_RESULT
    
    # 构建包含资源详情的回复
    sections = result.get("ui_plan", {}).get("sections", [])
    extra = ""
    for sec in sections:
        if sec["type"] == "key_value_list":
            items = sec.get("items", [])
            extra = "\n\n可用资源:\n" + "\n".join(
                f"- {i['label']}: {i['value']}" for i in items
            )
            break
    
    return {
        "agent_response": result["agent_response"] + extra,
        "data_source": "guardrail_resources",
    }


@register_data_function(Intent.CORRECTION)
def get_correction_data(state: GraphState) -> Dict[str, Any]:
    """
    获取纠错响应数据
    
    Args:
        state: 当前图状态
        
    Returns:
        包含纠错响应的字典
    """
    print(f"[DataProvider] 调用 get_correction_data")
    
    language = state.get("language", "Chinese")
    
    if language == "English":
        response = (
            "I apologize for the error. "
            "Please let me know what was incorrect so I can provide a better answer."
        )
    else:
        response = (
            "抱歉，我之前的回答有误。"
            "请告诉我哪里不对，我会为您提供更准确的答案。"
        )
    
    return {
        "agent_response": response,
        "data_source": "correction_response",
    }


@register_data_function(Intent.CLARIFICATION)
def get_clarification_data(state: GraphState) -> Dict[str, Any]:
    """
    获取澄清响应数据
    
    Args:
        state: 当前图状态
        
    Returns:
        包含澄清响应的字典
    """
    print(f"[DataProvider] 调用 get_clarification_data")
    
    language = state.get("language", "Chinese")
    platform = state.get("platform", "web")
    
    if platform == "wechat":
        # 微信简洁回复
        if language == "English":
            response = (
                "I can help you with:\n"
                "1) Restaurant recommendations\n"
                "2) Food recognition\n\n"
                "Please reply with your choice."
            )
        else:
            response = (
                "我可以帮助您：\n"
                "1) 推荐附近的健康餐厅\n"
                "2) 识别食物并提供营养信息\n\n"
                "请回复数字选择。"
            )
    else:
        # Web/其他平台详细回复
        if language == "English":
            response = (
                "I can help you with two things:\n"
                "1) Recommend nearby healthy restaurants\n"
                "2) Identify food and provide nutrition info\n\n"
                "Please choose the function you need."
            )
        else:
            response = (
                "我可以帮助你进行两类操作：\n"
                "1) 推荐附近更健康的餐饮选择\n"
                "2) 识别食物并给出营养信息\n\n"
                "请选择你需要的功能。"
            )
    
    return {
        "agent_response": response,
        "data_source": "clarification_response",
    }


@register_data_function(Intent.GOAL_PLANNING)
def get_goal_planning_data(state: GraphState) -> Dict[str, Any]:
    """
    获取目标规划数据
    
    Args:
        state: 当前图状态
        
    Returns:
        包含用户历史数据和目标规划响应的字典
    """
    print(f"[DataProvider] 调用 get_goal_planning_data")
    
    language = state.get("language", "Chinese")
    user_history = MOCK_USER_HISTORY
    
    # 检查是否有历史数据
    has_history = bool(user_history.get("days"))
    
    if language == "English":
        if has_history:
            response = (
                "Based on your recent diet history, I'll help you set goals for next week "
                "and provide actionable recommendations."
            )
        else:
            response = (
                "I don't have your diet history yet. Let's start tracking this week "
                "so I can provide personalized goal recommendations."
            )
    else:
        if has_history:
            response = (
                "我会根据你最近的饮食历史，帮你设定下周的饮食目标并给出可执行的建议。"
            )
        else:
            response = (
                "我还没有你的历史饮食数据，先从本周开始记录吧。"
            )
    
    return {
        "agent_response": response,
        "user_history": user_history if has_history else None,
        "data_source": "goal_planning_data",
        "has_history": has_history,
    }


@register_data_function(Intent.GENERIC)
def get_generic_data(state: GraphState) -> Dict[str, Any]:
    """
    获取通用聊天数据
    
    Args:
        state: 当前图状态
        
    Returns:
        包含通用聊天响应的字典
    """
    print(f"[DataProvider] 调用 get_generic_data")
    
    user_input = state.get("user_input", "")
    # 清理输入（去除web_demo添加的提示）
    clean = user_input.split(" (Please generate the UI plan")[0].strip()
    
    result: Dict[str, Any] = {
        "agent_response": clean or "How can I help you?",
        "data_source": "generic_input",
    }
    
    # 保留之前轮次的数据（用于跟进问题）
    if state.get("nutrition_facts"):
        result["nutrition_facts"] = state["nutrition_facts"]
    if state.get("recommended_restaurants"):
        result["recommended_restaurants"] = state["recommended_restaurants"]
    if state.get("user_history"):
        result["user_history"] = state["user_history"]
    
    return result


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------
def get_data(state: GraphState) -> Dict[str, Any]:
    """
    LangGraph node function.

    根据意图调用对应的数据获取函数。
    
    Reads:  state["intent"], state["context_input"], state["user_input"], etc.
    Writes: agent_response, nutrition_facts, recommended_restaurants,
            food_detection_json, user_history, data_source (whichever are relevant)
            
    Args:
        state: 当前图状态
        
    Returns:
        包含获取数据的字典
    """
    intent = state.get("intent", Intent.CLARIFICATION)
    
    print(f"[DataProvider] 开始获取数据，意图: {intent}")
    print(f"[DataProvider] 可用函数: {list_available_functions()}")
    
    # 获取对应的数据获取函数
    data_function = get_data_function(intent)
    
    if data_function is None:
        print(f"[DataProvider] 警告: 未找到意图 '{intent}' 对应的数据函数，使用默认处理")
        # 使用通用数据函数作为回退
        data_function = get_generic_data
    
    # 调用数据获取函数
    try:
        updates = data_function(state)
        print(f"[DataProvider] 数据获取成功，填充的字段: {list(updates.keys())}")
        return updates
    except Exception as e:
        print(f"[DataProvider] 数据获取失败: {e}")
        # 返回错误响应
        language = state.get("language", "Chinese")
        error_msg = (
            "抱歉，获取数据时出现问题。请稍后重试。"
            if language == "Chinese"
            else "Sorry, there was an issue retrieving data. Please try again later."
        )
        return {
            "agent_response": error_msg,
            "data_source": "error_fallback",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Utility function for external use
# ---------------------------------------------------------------------------
def call_data_function(intent: str, state: GraphState) -> Dict[str, Any]:
    """
    外部调用接口：根据意图直接调用数据获取函数
    
    Args:
        intent: 意图类型
        state: 当前图状态
        
    Returns:
        数据获取结果
    """
    func = get_data_function(intent)
    if func:
        return func(state)
    return get_generic_data(state)
