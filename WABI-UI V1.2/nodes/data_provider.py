# -*- coding: utf-8 -*-
"""为不同意图准备结构化数据，供后续 UI 生成使用。"""

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


@register_data_function(Intent.FOOD_RECOGNITION)
def get_food_recognition_data(state: GraphState) -> Dict[str, Any]:
    """
    获取食物识别相关数据
    
    逻辑：
    1. 如果已有食物数据（跟进问题），直接使用现有数据
    2. 如果有图片上传，进行新的食物识别
    3. 否则，提示上传图片
    
    Args:
        state: 当前图状态
        
    Returns:
        包含食物识别数据的字典
    """
    has_image = state.get("has_image", False)
    is_inherited = state.get("inherited_intent", False)
    has_existing_data = state.get("nutrition_facts") is not None
    
    print(f"[DataProvider] 调用 get_food_recognition_data (has_image={has_image}, is_inherited={is_inherited}, has_data={has_existing_data})")
    
    # 情况1：意图跟随（继承的意图）或已有数据
    if is_inherited or has_existing_data:
        print(f"[DataProvider] 意图跟随：使用已有食物数据")
        
        # 从状态获取数据，如果没有则使用mock
        nutrition_facts = state.get("nutrition_facts") or MOCK_RECOGNITION_RESULT["nutrition_facts"]
        food_detection_json = state.get("food_detection_json") or MOCK_RECOGNITION_RESULT.get("food_detection_json")
        
        # 根据用户输入构建针对性回复
        user_input = state.get("user_input", "").lower()
        if any(kw in user_input for kw in ["雷达图", "radar"]):
            agent_response = "为您使用雷达图展示食物营养成分对比。"
        elif any(kw in user_input for kw in ["饼图", "pie"]):
            agent_response = "为您使用饼图展示食物热量分布。"
        elif any(kw in user_input for kw in ["柱状图", "bar", "柱"]):
            agent_response = "为您使用柱状图展示各营养成分含量。"
        elif any(kw in user_input for kw in ["详细", "更多", "details", "more"]):
            agent_response = "为您展示更详细的食物营养信息。"
        else:
            agent_response = "为您展示食物的营养信息。"
        
        return {
            "agent_response": agent_response,
            "nutrition_facts": nutrition_facts,
            "food_detection_json": food_detection_json,
            "data_source": "existing_food_data",
            "is_follow_up": True,
        }
    
    # 情况2：有新图片上传
    if has_image:
        print(f"[DataProvider] 处理新上传的食物图片")
        result = MOCK_RECOGNITION_RESULT
        return {
            "agent_response": result["agent_response"],
            "nutrition_facts": result["nutrition_facts"],
            "food_detection_json": result.get("food_detection_json"),
            "data_source": "mock_food_recognition",
        }
    
    # 情况3：没有图片也没有数据，提示上传
    print(f"[DataProvider] 没有图片也没有数据，提示上传")
    
    language = state.get("language", "Chinese")
    
    # 检查上一条是否是等待图片上传的消息
    chat_history = state.get("chat_history", [])
    is_follow_up_image = False
    if chat_history:
        last_ai_msg = None
        for msg in reversed(chat_history):
            if hasattr(msg, 'additional_kwargs') and 'ui_plan' in msg.additional_kwargs:
                last_ai_msg = msg.additional_kwargs['ui_plan']
                break
        
        # 如果上一条是等待图片的消息，当前输入视为新的请求（可能是文字描述）
        if last_ai_msg and last_ai_msg.get('mode') == 'image_upload_request' and last_ai_msg.get('awaiting_image'):
            is_follow_up_image = True
            print(f"[DataProvider] 用户在上传图片提示后输入: {state.get('user_input', '')}")
    
    # 如果是跟进消息且用户输入了文字（不是图片），提示需要图片
    if is_follow_up_image:
        if language == "English":
            agent_response = (
                "I need a photo to identify the food.\n\n"
                "Please upload a clear picture of your food, and I'll analyze the nutritional content for you."
            )
        else:
            agent_response = (
                "我需要照片才能识别食物。\n\n"
                "请上传一张清晰的食物照片，我会为您分析营养成分。"
            )
    else:
        # 首次提示上传图片
        if language == "English":
            agent_response = (
                "Please upload a food photo, and I'll analyze the nutritional content for you.\n\n"
                "You can take a photo directly or select one from your album."
            )
        else:
            agent_response = (
                "请上传一张食物照片，我来帮您分析营养成分。\n\n"
                "您可以直接拍照或从相册选择。"
            )
    
    return {
        "agent_response": agent_response,
        "nutrition_facts": None,
        "food_detection_json": None,
        "data_source": "food_recognition_prompt",
        "awaiting_image": True,  # 标记等待图片上传
    }


@register_data_function(Intent.RECOMMENDATION)
def get_recommendation_data(state: GraphState) -> Dict[str, Any]:
    """
    获取餐厅推荐数据
    
    支持意图跟随：如果已有推荐数据，直接返回用于展示（如"用列表展示"、"排序"等）
    
    Args:
        state: 当前图状态
        
    Returns:
        包含餐厅推荐数据的字典
    """
    is_inherited = state.get("inherited_intent", False)
    has_existing_data = state.get("recommended_restaurants") is not None
    
    print(f"[DataProvider] 调用 get_recommendation_data (is_inherited={is_inherited}, has_data={has_existing_data})")
    
    # 意图跟随：使用已有推荐数据
    if is_inherited or has_existing_data:
        print(f"[DataProvider] 意图跟随：使用已有推荐数据")
        
        restaurants = state.get("recommended_restaurants") or MOCK_RECOMMENDATION_TABLE_RESULT["recommended_restaurants"]
        
        # 根据用户输入构建针对性回复
        user_input = state.get("user_input", "").lower()
        if any(kw in user_input for kw in ["列表", "list"]):
            agent_response = "为您以列表形式展示推荐餐厅。"
        elif any(kw in user_input for kw in ["排序", "排名", "sort", "rank"]):
            agent_response = "为您按评分排序展示推荐餐厅。"
        elif any(kw in user_input for kw in ["第一个", "第一家", "first"]):
            agent_response = "为您详细介绍第一家餐厅。"
        elif any(kw in user_input for kw in ["地图", "位置", "map", "location"]):
            agent_response = "为您在地图上展示餐厅位置。"
        else:
            agent_response = "为您展示推荐餐厅信息。"
        
        return {
            "agent_response": agent_response,
            "recommended_restaurants": restaurants,
            "data_source": "existing_recommendation_data",
            "is_follow_up": True,
        }
    
    # 新的推荐请求
    print(f"[DataProvider] 获取新的餐厅推荐")
    
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
    获取纠错响应数据 - 一步完成版本
    
    当用户触发纠错意图时，直接记录用户的输入并返回感谢信息，
    不再要求用户输入详细反馈。
    
    Args:
        state: 当前图状态
        
    Returns:
        包含纠错响应的字典
    """
    print(f"[DataProvider] 调用 get_correction_data")
    
    # 导入反馈记录模块
    from UI.feedback_logger import log_correction_feedback
    
    language = state.get("language", "Chinese")
    patient_id = state.get("patient_id", "unknown")
    user_input = state.get("user_input", "")
    
    # 获取上一轮的信息
    chat_history = state.get("chat_history", [])
    previous_intent = None
    previous_response = None
    
    if chat_history and len(chat_history) >= 2:
        # 找到最近一轮的 AI 回复
        for msg in reversed(chat_history):
            if hasattr(msg, 'additional_kwargs') and 'ui_plan' in msg.additional_kwargs:
                ui_plan = msg.additional_kwargs['ui_plan']
                previous_response = ui_plan.get('summary', '')[:200]
                previous_intent = ui_plan.get('mode', '')
                break
    
    # 一步完成：直接记录用户的纠错输入并返回感谢
    log_correction_feedback(
        patient_id=patient_id,
        correction_input=user_input,  # 记录用户的完整输入作为纠错内容
        previous_intent=previous_intent,
        previous_response=previous_response,
        feedback_type="correction",
        feedback_content=user_input,  # 将用户输入作为反馈内容
        chat_history=str([{"role": "user" if hasattr(m, 'content') else "ai", "content": str(m.content)[:100] if hasattr(m, 'content') else ""} for m in chat_history[-4:]]),
        session_id=state.get("session_id", ""),
    )
    
    # 生成感谢响应
    if language == "English":
        response = (
            "Thank you for your feedback! I have recorded your correction.\n\n"
            "Please try asking your question again, and I will do my best to provide a more accurate answer."
        )
    else:
        response = (
            "感谢您的反馈！我已记录您的纠错信息。\n\n"
            "请重新描述您的问题，我会尽力提供更准确的回答。"
        )
    
    return {
        "agent_response": response,
        "data_source": "correction_recorded",
        "feedback_recorded": True,
        "feedback_content": user_input,
        "awaiting_feedback": False,  # 不再等待用户反馈
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
    
    支持意图跟随：如果已有历史数据，直接返回用于展示不同视图（如图表、详细分析等）
    
    Args:
        state: 当前图状态
        
    Returns:
        包含用户历史数据和目标规划响应的字典
    """
    is_inherited = state.get("inherited_intent", False)
    has_existing_data = state.get("user_history") is not None
    
    print(f"[DataProvider] 调用 get_goal_planning_data (is_inherited={is_inherited}, has_data={has_existing_data})")
    
    language = state.get("language", "Chinese")
    user_history = state.get("user_history") or MOCK_USER_HISTORY
    has_history = bool(user_history.get("days"))
    
    # 意图跟随：使用已有历史数据展示不同视图
    if (is_inherited or has_existing_data) and has_history:
        print(f"[DataProvider] 意图跟随：使用已有历史数据")
        
        # 根据用户输入构建针对性回复
        user_input = state.get("user_input", "").lower()
        if any(kw in user_input for kw in ["图表", "折线图", "趋势", "chart", "trend"]):
            agent_response = "为您展示饮食趋势图表。"
        elif any(kw in user_input for kw in ["统计", "数据", "statistics", "data"]):
            agent_response = "为您展示详细的饮食统计数据。"
        elif any(kw in user_input for kw in ["分析", "建议", "analysis", "suggestion"]):
            agent_response = "为您分析饮食历史并提供建议。"
        elif any(kw in user_input for kw in ["目标", "goal", "target"]):
            agent_response = "根据您的历史数据制定下周目标。"
        else:
            agent_response = "为您展示历史饮食数据。"
        
        return {
            "agent_response": agent_response,
            "user_history": user_history,
            "data_source": "existing_goal_data",
            "has_history": True,
            "is_follow_up": True,
        }
    
    # 新的目标规划请求
    print(f"[DataProvider] 获取新的目标规划数据")
    
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
