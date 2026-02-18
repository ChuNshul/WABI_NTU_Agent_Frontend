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
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Any, Optional

from UI.state import GraphState, Intent


# ---------------------------------------------------------------------------
# Bedrock client helpers
# ---------------------------------------------------------------------------
MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"


def _get_bedrock_client():
    """获取Bedrock客户端"""
    try:
        import boto3
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-southeast-1"
        return boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        )
    except Exception as e:
        print(f"[IntentDetector] Bedrock init failed: {e}")
        return None


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
def _call_llm_for_intent(prompt: str) -> Optional[Dict[str, Any]]:
    """调用LLM进行意图识别"""
    client = _get_bedrock_client()
    if not client:
        print("[IntentDetector] LLM client not available, using fallback")
        return None

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0.1,  # 低温度以获得更确定的结果
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    }

    try:
        response = client.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )

        result = json.loads(response["body"].read())
        output_text = result["content"][0]["text"]
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

    except Exception as e:
        print(f"[IntentDetector] LLM call failed: {e}")
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

    Reads:  state["context_input"], state["user_input"], state["has_image"]
    Writes: state["intent"], state["intent_confidence"], state["intent_reasoning"]
    
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
    
    # 构建LLM提示
    prompt = INTENT_DETECTION_PROMPT.format(
        context=context_input if context_input else "No previous context",
        user_input=user_input
    )
    
    # 调用LLM进行意图识别
    llm_result = _call_llm_for_intent(prompt)
    
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
