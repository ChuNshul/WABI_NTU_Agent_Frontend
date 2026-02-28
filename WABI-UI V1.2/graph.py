# -*- coding: utf-8 -*-
"""
graph.py — LangGraph graph definition for the Wabi UI Agent

Graph topology (enhanced pipeline with context memory):

    [START]
       │
       ▼
  context_manager      ← builds context_input from history + current input
       │
       ▼
  intent_detector      ← uses LLM to analyze intent with context
       │
       ▼
  data_provider        ← calls registered data function based on intent
       │
       ▼
  ui_generator         ← uses LLM to plan UI with context and data
       │
       ▼
  renderer             ← validates, sanitises, enriches the plan
       │
       ▼
    [END]

Usage:
    from UI.graph import graph

    result = graph.invoke({
        "user_input":  "附近有什么健康餐厅？",
        "language":    "Chinese",
        "has_image":   False,
        "patient_id":  "user_001",
        "chat_history": [],
    })

    print(result["rendered_output"])
"""

from langgraph.graph import StateGraph, END

from UI.state import GraphState
from UI.nodes.context_manager import manage_context
from UI.nodes.intent_detector import detect_intent
from UI.nodes.data_provider import get_data
from UI.nodes.ui_generator import generate_ui_plan
from UI.nodes.renderer import render_output


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Construct and compile the Wabi UI Agent graph."""

    workflow = StateGraph(GraphState)

    # Register nodes
    workflow.add_node("context_manager", manage_context)   # NEW: 上下文记忆管理
    workflow.add_node("intent_detector", detect_intent)    # UPDATED: LLM-based intent detection
    workflow.add_node("data_provider",   get_data)         # UPDATED: Function-call based data retrieval
    workflow.add_node("ui_generator",    generate_ui_plan) # UPDATED: LLM-based UI planning with context
    workflow.add_node("renderer",        render_output)

    # Define edges (enhanced pipeline)
    workflow.set_entry_point("context_manager")
    workflow.add_edge("context_manager", "intent_detector")
    workflow.add_edge("intent_detector", "data_provider")
    workflow.add_edge("data_provider",   "ui_generator")
    workflow.add_edge("ui_generator",    "renderer")
    workflow.add_edge("renderer",        END)

    return workflow.compile()


# Compiled graph — import this in web_demo.py
graph = build_graph()
