# -*- coding: utf-8 -*-
"""
UI Agent entry point — public interface: generate_ui_plan(state: GraphState) -> GraphState
All logic lives in ui_config / ui_llm / ui_nodes / ui_graph.
"""

from __future__ import annotations

import os
import pathlib


def _load_env() -> None:
    """Load .env from known project paths without requiring python-dotenv."""
    try:
        from dotenv import load_dotenv  # type: ignore
        dotenv_fn = load_dotenv
    except ImportError:
        dotenv_fn = None

    for p in (pathlib.Path("/home/songlh/WABI_NTU_Agent_Backend/.env"), pathlib.Path(".env")):
        if not p.is_file():
            continue
        if dotenv_fn:
            dotenv_fn(str(p), override=False)
        else:
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k, v)
        break


_load_env()

from langgraph_app.orchestrator.state import GraphState
from .ui_graph import get_ui_graph


def generate_ui_plan(state: GraphState) -> GraphState:
    """Run the UI LangGraph and write the resulting plan back onto state."""
    result = get_ui_graph().invoke({
        "intent":                  str(state.intent or ""),
        "user_input":              str(state.user_input)[:1000] if state.user_input else None,
        "agent_response":          str(state.agent_response)[:1000] if state.agent_response else None,
        "nutrition_facts":         state.nutrition_facts,
        "recommended_restaurants": state.recommended_restaurants,
        "has_image":               getattr(state, "has_image", False),
        "food_vis_path":           state.food_vis_path,
        "food_detection_json":     getattr(state, "food_detection_json", None),
        "chat_history":            state.chat_history,
        "user_history":            getattr(state, "user_history", None),
        "platform":                getattr(state, "platform", "web"),
        "language":                getattr(state, "language", "Chinese"),
        # graph-internal fields
        "route": None, "input_tokens": 0, "output_tokens": 0, "ui_plan": None, "error": None,
    })
    state.ui_plan = result.get("ui_plan")
    return state
