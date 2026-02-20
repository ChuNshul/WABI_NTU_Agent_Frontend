# -*- coding: utf-8 -*-
"""
IntentDetector Node (LLM-based)
-------------------------------
使用LLM分析用户的输入（结合上下文）来识别意图。

支持七种意图：
  food_recognition  —— 食物识别   (image upload or food-id keywords)
  recommendation    —— 餐厅推荐   (restaurant / food suggestion)
  correction        —— 纠错       (user corrects a previous answer)
  clarification     —— 澄清       (ambiguous / unclear request)
  guardrail         —— 安全护栏   (mental-health / self-harm signals)
  goal_planning     —— 计划/目标  (nutrition goals, weekly plans)
  generic           —— 通用聊天   (general conversation)

通用意图跟随机制：
  当上一轮有特定意图的数据时，用户的跟进问题（如"用雷达图展示"、"详细点"等）
  应该继承上一轮的意图，而不是重新判定或要求重新提供数据。
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Any, Optional

from UI.state import GraphState, Intent
from UI.llm_config import call_llm, get_model_config, DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Model Configuration
# ---------------------------------------------------------------------------
# 默认使用配置中的默认模型，可通过state中的llm_model字段覆盖


# ---------------------------------------------------------------------------
# Context Analysis Helpers
# ---------------------------------------------------------------------------

# 意图与数据字段的映射关系
INTENT_DATA_FIELDS = {
    Intent.FOOD_RECOGNITION: ["nutrition_facts", "food_detection_json"],
    Intent.RECOMMENDATION: ["recommended_restaurants"],
    Intent.GOAL_PLANNING: ["user_history"],
    Intent.GUARDRAIL: [],  # 安全护栏通常不依赖历史数据
    Intent.CORRECTION: [],
    Intent.CLARIFICATION: [],
    Intent.GENERIC: [],
}


def _get_previous_intent(state: GraphState) -> Optional[str]:
    """从上下文中获取上一轮意图"""
    relevant_history = state.get("relevant_history", [])
    if relevant_history:
        last_turn = relevant_history[-1]
        return last_turn.get("ui_mode")
    return None


def _has_intent_data(state: GraphState, intent: str) -> bool:
    """检查状态中是否已有指定意图的数据"""
    data_fields = INTENT_DATA_FIELDS.get(intent, [])
    for field in data_fields:
        if state.get(field) is not None:
            return True
    return False


def _is_follow_up_question(user_input: str) -> bool:
    """
    检测用户输入是否是跟进问题
    
    跟进问题的特征：
    - 包含展示/查看类词汇
    - 包含图表类型词汇
    - 包含详细/更多类词汇
    - 短句，缺少明确意图
    """
    follow_up_keywords = [
        # 展示/查看相关
        "展示", "显示", "查看", "看", "用", "换成", "改为", "切换",
        "show", "display", "view", "use", "change to", "switch to",
        # 图表类型
        "雷达图", "饼图", "柱状图", "折线图", "图表", "图",
        "radar chart", "pie chart", "bar chart", "line chart", "chart", "graph",
        # 详细/更多
        "详细", "更多", "具体", "深入", "展开",
        "details", "more", "specific", "elaborate",
        # 比较/分析
        "对比", "比较", "分析", "怎么样",
        "compare", "comparison", "analyze", "how about",
        # 列表/排序
        "列表", "排序", "排名", "第一个", "第二个",
        "list", "sort", "rank", "first", "second",
    ]
    
    user_lower = user_input.lower().strip()
    
    # 如果输入很短（少于10个字符），可能是跟进问题
    if len(user_lower) < 10:
        return True
    
    # 检查是否包含跟进关键词
    return any(kw in user_lower for kw in follow_up_keywords)


def _should_inherit_intent(state: GraphState, user_input: str) -> Optional[str]:
    """
    判断是否应该继承上一轮意图
    
    条件：
    1. 上一轮有意图数据
    2. 当前输入是跟进问题
    3. 当前输入没有明确的新意图
    
    Returns:
        应该继承的意图，或None表示不继承
    """
    previous_intent = _get_previous_intent(state)
    
    if not previous_intent:
        return None
    
    # 检查上一轮是否有数据
    has_data = _has_intent_data(state, previous_intent)
    
    if not has_data:
        return None
    
    # 检查是否是跟进问题
    is_follow_up = _is_follow_up_question(user_input)
    
    if not is_follow_up:
        return None
    
    print(f"[IntentDetector] 意图跟随: 继承上一轮意图 '{previous_intent}'")
    return previous_intent


# ---------------------------------------------------------------------------
# Intent detection prompt
# ---------------------------------------------------------------------------
INTENT_DETECTION_PROMPT = """You are an intent detection system for a health and nutrition assistant called "Wabi".

Your task is to analyze the user's input and determine their intent from the following categories:

1. **food_recognition** - User wants to identify/analyze food from an image or description
   - Examples: "这是什么菜", "帮我识别这个食物", "分析这张图片", "uploaded a food image"
   - Keywords: 识别, 食物, 菜, 图片, image, food, identify, recognize, scan

2. **recommendation** - User wants restaurant or food recommendations
   - Examples: "附近有什么好吃的", "推荐健康餐厅", "我饿了", "what should I eat"
   - Keywords: 推荐, 餐厅, 附近, 吃什么, hungry, recommend, restaurant, nearby, eat

3. **goal_planning** - User wants to set nutrition/health goals or create meal plans
   - Examples: "我想减肥", "设定卡路里目标", "制定饮食计划", "set a goal"
   - Keywords: 目标, 计划, 减肥, 卡路里, goal, plan, target, diet plan

4. **correction** - User is correcting a previous response
   - Examples: "不对", "你说错了", "那是错的", "that's wrong", "incorrect"
   - Keywords: 错, 不对, 有误, 纠正, wrong, incorrect, mistake, error, not right

5. **guardrail** - User input contains self-harm, suicide, or mental health crisis signals
   - Examples: "我不想活了", "想自杀", "kill myself", "suicide", "自残"
   - ⚠️ SAFETY PRIORITY: If ANY self-harm signals detected, MUST classify as guardrail

6. **clarification** - User request is unclear or ambiguous
   - Examples: "我不知道", "不清楚", "什么意思", "unclear", "confused", "don't understand"
   - Use when the intent cannot be determined from the input

7. **generic** - General conversation or chat that doesn't fit above categories
   - Examples: "你好", "谢谢", "how are you", "what can you do"

## Context Information:
{context}

## User Input:
{user_input}

## Instructions:
1. Analyze the user's input considering the context
2. Determine the most appropriate intent
3. Provide your reasoning
4. Assign a confidence score (0.0-1.0)

## Output Format (JSON):
{{
    "intent": "one_of_the_7_intents_above",
    "confidence": 0.95,
    "reasoning": "Brief explanation of why this intent was chosen",
    "extracted_entities": {{
        "food_items": ["list of food items mentioned"],
        "location_keywords": ["location-related words"],
        "time_references": ["time-related words"],
        "health_goals": ["goal-related words"]
    }}
}}

Respond ONLY with the JSON object, no other text."""


# ---------------------------------------------------------------------------
# LLM call function
# ---------------------------------------------------------------------------
def _call_llm_for_intent(prompt: str, model_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    调用LLM进行意图识别
    
    Args:
        prompt: 提示词
        model_name: 模型名称，如果为None则使用默认模型
        
    Returns:
        解析后的JSON响应字典
    """
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    
    # 调用统一的LLM接口
    result = call_llm(
        model_name=model_name or DEFAULT_MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.1,  # 低温度以获得更确定的结果
    )
    
    if not result:
        print("[IntentDetector] LLM call failed, using fallback")
        return None
    
    output_text = result["text"]
    print(f"[IntentDetector] LLM raw output:\n{output_text[:500]}...")
    
    # 解析JSON响应
    match = re.search(r"\{[\s\S]*\}", output_text)
    if not match:
        print("[IntentDetector] No JSON found in LLM response")
        return None
    
    try:
        parsed = json.loads(match.group(0))
        return parsed
    except json.JSONDecodeError as e:
        print(f"[IntentDetector] JSON parse error: {e}")
        return None


# ---------------------------------------------------------------------------
# Safety check (rule-based guardrail for critical safety issues)
# ---------------------------------------------------------------------------
SAFETY_KEYWORDS = [
    "die", "kill", "suicide", "自杀", "死", "不想活", "轻生", 
    "结束生命", "自残", "自伤", "结束一切", "不想活了",
    "kill myself", "end my life", "want to die"
]


def _safety_check(text: str) -> bool:
    """安全检查：检测是否存在自残/自杀信号"""
    lower_text = text.lower()
    return any(kw.lower() in lower_text for kw in SAFETY_KEYWORDS)


# ---------------------------------------------------------------------------
# Intent validation
# ---------------------------------------------------------------------------
VALID_INTENTS = {
    Intent.FOOD_RECOGNITION,
    Intent.RECOMMENDATION,
    Intent.CORRECTION,
    Intent.CLARIFICATION,
    Intent.GUARDRAIL,
    Intent.GOAL_PLANNING,
    Intent.GENERIC,
}


def _validate_intent(intent: str) -> str:
    """验证意图是否有效"""
    if intent in VALID_INTENTS:
        return intent
    # 尝试匹配
    intent_map = {
        "food": Intent.FOOD_RECOGNITION,
        "recognition": Intent.FOOD_RECOGNITION,
        "recommend": Intent.RECOMMENDATION,
        "restaurant": Intent.RECOMMENDATION,
        "correct": Intent.CORRECTION,
        "clarify": Intent.CLARIFICATION,
        "ambiguous": Intent.CLARIFICATION,
        "safety": Intent.GUARDRAIL,
        "crisis": Intent.GUARDRAIL,
        "goal": Intent.GOAL_PLANNING,
        "plan": Intent.GOAL_PLANNING,
        "general": Intent.GENERIC,
        "chat": Intent.GENERIC,
    }
    for key, value in intent_map.items():
        if key in intent.lower():
            return value
    return Intent.GENERIC


# ---------------------------------------------------------------------------
# Fallback intent detection (rule-based, for when LLM fails)
# ---------------------------------------------------------------------------
def _fallback_intent_detection(user_input: str, has_image: bool) -> Dict[str, Any]:
    """基于规则的意图识别（LLM失败时的备用方案）"""
    
    # 安全检查（最高优先级）
    if _safety_check(user_input):
        return {
            "intent": Intent.GUARDRAIL,
            "confidence": 0.95,
            "reasoning": "Safety keywords detected in fallback mode",
            "extracted_entities": {}
        }
    
    # 图片上传
    if has_image:
        return {
            "intent": Intent.FOOD_RECOGNITION,
            "confidence": 0.9,
            "reasoning": "Image upload detected in fallback mode",
            "extracted_entities": {}
        }
    
    # 简单的关键词匹配
    text_lower = user_input.lower()
    
    if any(kw in text_lower for kw in ["推荐", "餐厅", "吃什么", "附近", "recommend", "restaurant", "hungry", "eat"]):
        return {
            "intent": Intent.RECOMMENDATION,
            "confidence": 0.8,
            "reasoning": "Recommendation keywords detected in fallback mode",
            "extracted_entities": {}
        }
    
    if any(kw in text_lower for kw in ["识别", "食物", "菜", "图片", "identify", "recognize", "food", "what is this"]):
        return {
            "intent": Intent.FOOD_RECOGNITION,
            "confidence": 0.8,
            "reasoning": "Food recognition keywords detected in fallback mode",
            "extracted_entities": {}
        }
    
    if any(kw in text_lower for kw in ["目标", "计划", "减肥", "goal", "plan", "target", "diet"]):
        return {
            "intent": Intent.GOAL_PLANNING,
            "confidence": 0.8,
            "reasoning": "Goal planning keywords detected in fallback mode",
            "extracted_entities": {}
        }
    
    if any(kw in text_lower for kw in ["错", "不对", "wrong", "incorrect", "mistake", "error"]):
        return {
            "intent": Intent.CORRECTION,
            "confidence": 0.8,
            "reasoning": "Correction keywords detected in fallback mode",
            "extracted_entities": {}
        }
    
    if any(kw in text_lower for kw in ["不清楚", "不明白", "unclear", "confused", "don't understand"]):
        return {
            "intent": Intent.CLARIFICATION,
            "confidence": 0.7,
            "reasoning": "Clarification keywords detected in fallback mode",
            "extracted_entities": {}
        }
    
    # 默认通用聊天
    return {
        "intent": Intent.GENERIC,
        "confidence": 0.6,
        "reasoning": "No specific intent detected in fallback mode",
        "extracted_entities": {}
    }


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------
def detect_intent(state: GraphState) -> Dict:
    """
    LangGraph node function.

    支持通用意图跟随机制：
    - 如果上一轮有数据且当前是跟进问题，继承上一轮意图
    
    Reads:  state["context_input"], state["user_input"], state["has_image"]
    Writes: state["intent"], state["intent_confidence"], state["intent_reasoning"],
            state["inherited_intent"] (如果继承了上一轮意图)
    
    Args:
        state: 当前图状态
        
    Returns:
        包含意图、置信度和推理过程的字典
    """
    context_input: str = state.get("context_input", "")
    user_input: str = state.get("user_input", "")
    has_image: bool = state.get("has_image", False)
    
    print(f"[IntentDetector] 开始意图分析...")
    print(f"[IntentDetector] 用户输入: {user_input[:100]}...")
    
    # 首先进行安全检查（最高优先级）
    if _safety_check(user_input):
        print(f"[IntentDetector] 安全警告：检测到自残/自杀信号")
        return {
            "intent": Intent.GUARDRAIL,
            "intent_confidence": 1.0,
            "intent_reasoning": "Safety check: self-harm keywords detected",
        }
    
    # 图片上传直接判定为食物识别
    if has_image and not user_input.strip():
        print(f"[IntentDetector] 图片上传 -> food_recognition")
        return {
            "intent": Intent.FOOD_RECOGNITION,
            "intent_confidence": 0.95,
            "intent_reasoning": "Image upload detected without text input",
        }
    
    # ========== 通用意图跟随机制 ==========
    # 检查是否应该继承上一轮意图
    inherited_intent = _should_inherit_intent(state, user_input)
    
    if inherited_intent:
        print(f"[IntentDetector] 意图跟随: 继承上一轮意图 '{inherited_intent}'")
        return {
            "intent": inherited_intent,
            "intent_confidence": 0.9,
            "intent_reasoning": f"Intent following: user is asking follow-up about previous {inherited_intent}",
            "inherited_intent": True,  # 标记为继承的意图
        }
    
    # 构建LLM提示
    prompt = INTENT_DETECTION_PROMPT.format(
        context=context_input if context_input else "No previous context",
        user_input=user_input
    )
    
    # 获取模型配置（从state中读取或使用默认）
    llm_model = state.get("llm_model", DEFAULT_MODEL)
    print(f"[IntentDetector] 使用模型: {llm_model}")
    
    # 调用LLM进行意图识别
    llm_result = _call_llm_for_intent(prompt, model_name=llm_model)
    
    if llm_result:
        # 验证和规范化意图
        detected_intent = _validate_intent(llm_result.get("intent", Intent.GENERIC))
        confidence = float(llm_result.get("confidence", 0.5))
        reasoning = llm_result.get("reasoning", "No reasoning provided")
        
        print(f"[IntentDetector] LLM分析结果: intent={detected_intent}, confidence={confidence}")
        print(f"[IntentDetector] 推理: {reasoning}")
        
        return {
            "intent": detected_intent,
            "intent_confidence": confidence,
            "intent_reasoning": reasoning,
        }
    else:
        # LLM失败，使用备用方案
        print(f"[IntentDetector] LLM分析失败，使用备用规则...")
        fallback_result = _fallback_intent_detection(user_input, has_image)
        
        return {
            "intent": fallback_result["intent"],
            "intent_confidence": fallback_result["confidence"],
            "intent_reasoning": fallback_result["reasoning"],
        }
