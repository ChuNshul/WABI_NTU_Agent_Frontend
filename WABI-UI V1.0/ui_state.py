# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Literal, Optional, TypedDict


class UIAgentState(TypedDict):
    # ── Inputs ────────────────────────────────────────────────────────────────
    intent: str
    user_input: Optional[str]
    agent_response: Optional[str]
    nutrition_facts: Optional[Dict[str, Any]]
    recommended_restaurants: Optional[List[Dict[str, Any]]]
    has_image: bool
    food_vis_path: Optional[str]
    food_detection_json: Optional[Dict[str, Any]]
    chat_history: Optional[List[Any]]
    user_history: Optional[Dict[str, Any]]
    platform: Literal["web", "wechat", "whatsapp"]
    language: Literal["Chinese", "English"]

    # ── Internal routing ──────────────────────────────────────────────────────
    route: Optional[str]

    # ── LLM token counters (set by llm_generator, read by platform_enforcer) ─
    input_tokens: int
    output_tokens: int

    # ── Output ────────────────────────────────────────────────────────────────
    ui_plan: Optional[Dict[str, Any]]
    error: Optional[str]
