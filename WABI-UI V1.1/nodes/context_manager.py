# -*- coding: utf-8 -*-
"""
ContextManager Node
-------------------
负责管理上下文记忆功能：
1. 从历史对话中提取相关信息
2. 将历史数据与当前输入拼接成总输入
3. 为后续的意图分析和UI生成提供完整的上下文
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from UI.state import GraphState


# ---------------------------------------------------------------------------
# 上下文提取配置
# ---------------------------------------------------------------------------
MAX_HISTORY_TURNS = 10  # 最大保留的历史轮数
MAX_CONTEXT_LENGTH = 4000  # 最大上下文长度（字符）


def _extract_relevant_history(
    chat_history: List[BaseMessage],
    current_input: str,
    max_turns: int = MAX_HISTORY_TURNS
) -> List[Dict[str, Any]]:
    """
    从历史对话中提取相关信息
    
    Args:
        chat_history: 历史对话消息列表
        current_input: 当前用户输入
        max_turns: 最大保留轮数
        
    Returns:
        提取的相关历史记录列表
    """
    if not chat_history:
        return []
    
    # 只保留最近的几轮对话
    recent_history = chat_history[-max_turns * 2:]  # *2 because each turn has user + assistant
    
    relevant_history = []
    current_turn = {}
    
    for msg in recent_history:
        if isinstance(msg, HumanMessage):
            # 保存之前的轮次（如果存在）
            if current_turn:
                relevant_history.append(current_turn.copy())
            current_turn = {"user": str(msg.content)[:500], "assistant": None}
        elif isinstance(msg, AIMessage):
            if current_turn:
                # 提取AI回复的关键信息（截断以避免过长）
                content = str(msg.content)
                current_turn["assistant"] = content[:500]
                # 如果有UI计划，提取模式信息
                if hasattr(msg, 'additional_kwargs'):
                    if 'ui_plan' in msg.additional_kwargs:
                        ui_plan = msg.additional_kwargs['ui_plan']
                        if isinstance(ui_plan, dict):
                            current_turn["ui_mode"] = ui_plan.get('mode', 'unknown')
                            print(f"[ContextManager] 提取到 ui_mode: {current_turn['ui_mode']}")
                        else:
                            print(f"[ContextManager] ui_plan 不是字典: {type(ui_plan)}")
                    else:
                        print(f"[ContextManager] AIMessage 没有 ui_plan, keys: {list(msg.additional_kwargs.keys())}")
                else:
                    print(f"[ContextManager] AIMessage 没有 additional_kwargs")
    
    # 添加最后一轮（如果存在）
    if current_turn and current_turn.get("user"):
        relevant_history.append(current_turn)
    
    return relevant_history[-max_turns:]


def _build_context_input(
    user_input: str,
    relevant_history: List[Dict[str, Any]],
    has_image: bool = False,
    max_length: int = MAX_CONTEXT_LENGTH
) -> str:
    """
    构建上下文输入：将历史数据与当前输入拼接
    
    Args:
        user_input: 当前用户输入
        relevant_history: 相关历史记录
        has_image: 是否有图片上传
        max_length: 最大长度限制
        
    Returns:
        拼接后的上下文输入字符串
    """
    context_parts = []
    
    # 添加历史上下文
    if relevant_history:
        context_parts.append("=== 历史对话上下文 ===")
        for i, turn in enumerate(relevant_history, 1):
            context_parts.append(f"\n[轮次 {i}]")
            context_parts.append(f"用户: {turn.get('user', '')}")
            if turn.get('assistant'):
                assistant_msg = turn['assistant']
                if len(assistant_msg) > 200:
                    assistant_msg = assistant_msg[:200] + "..."
                context_parts.append(f"助手: {assistant_msg}")
            if turn.get('ui_mode'):
                context_parts.append(f"(UI模式: {turn['ui_mode']})")
        context_parts.append("\n=== 当前输入 ===")
    
    # 添加当前输入
    current = f"用户当前输入: {user_input}"
    if has_image:
        current += " [包含图片上传]"
    context_parts.append(current)
    
    # 拼接并截断
    context_input = "\n".join(context_parts)
    if len(context_input) > max_length:
        # 如果太长，保留当前输入，截断历史
        current_only = context_parts[-1]
        available_length = max_length - len(current_only) - 100
        truncated_history = context_input[:available_length]
        context_input = truncated_history + "\n... [历史记录截断]\n\n" + current_only
    
    return context_input


def _extract_context_summary(relevant_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    从历史中提取上下文摘要信息
    
    Returns:
        包含上下文摘要的字典
    """
    summary = {
        "total_turns": len(relevant_history),
        "has_previous_food_recognition": False,
        "has_previous_recommendation": False,
        "has_previous_goal_planning": False,
        "last_ui_mode": None,
        "user_preferences": [],
    }
    
    for turn in relevant_history:
        ui_mode = turn.get('ui_mode')
        if ui_mode:
            summary["last_ui_mode"] = ui_mode
            if ui_mode == "food_recognition":
                summary["has_previous_food_recognition"] = True
            elif ui_mode == "recommendation":
                summary["has_previous_recommendation"] = True
            elif ui_mode == "goal_planning":
                summary["has_previous_goal_planning"] = True
        
        # 尝试提取用户偏好（简单的关键词匹配）
        user_msg = turn.get('user', '').lower()
        if any(word in user_msg for word in ['喜欢', '爱', '偏好', 'prefer', 'like', 'favorite']):
            summary["user_preferences"].append(turn.get('user', '')[:100])
    
    # 只保留最近的3个偏好
    summary["user_preferences"] = summary["user_preferences"][-3:]
    
    return summary


# ---------------------------------------------------------------------------
# Node entry point
# ---------------------------------------------------------------------------
def manage_context(state: GraphState) -> Dict:
    """
    LangGraph node function.

    Reads:  state["user_input"], state["chat_history"], state["has_image"]
    Writes: state["context_input"], state["relevant_history"]
    
    Args:
        state: 当前图状态
        
    Returns:
        包含上下文输入和相关历史的字典
    """
    user_input: str = state.get("user_input", "")
    chat_history: List[BaseMessage] = state.get("chat_history", [])
    has_image: bool = state.get("has_image", False)
    
    print(f"[ContextManager] 开始处理上下文记忆...")
    print(f"[ContextManager] 用户输入: {user_input[:100]}...")
    print(f"[ContextManager] 历史轮数: {len(chat_history) // 2}")
    
    # 1. 提取相关历史
    relevant_history = _extract_relevant_history(chat_history, user_input)
    print(f"[ContextManager] 提取相关历史: {len(relevant_history)} 轮")
    
    # 2. 构建上下文输入（历史 + 当前输入）
    context_input = _build_context_input(user_input, relevant_history, has_image)
    print(f"[ContextManager] 上下文输入长度: {len(context_input)} 字符")
    
    # 3. 提取上下文摘要（用于调试）
    context_summary = _extract_context_summary(relevant_history)
    print(f"[ContextManager] 上下文摘要: {context_summary}")
    
    return {
        "context_input": context_input,
        "relevant_history": relevant_history,
    }
