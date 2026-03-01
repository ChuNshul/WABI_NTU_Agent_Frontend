# -*- coding: utf-8 -*-
"""
    [START]
       │
       ▼
  ui_generator         ← LLM 读取用户输入与上游意图/数据生成 ui_plan
       │
       ▼
    checker              ← 校验 ui_plan 并输出最终 checked_output
       │
       ▼
    [END]
"""

from langgraph.graph import StateGraph, END

from UI.state import GraphState
from UI.nodes.ui_generator import generate_ui_plan
from UI.nodes.checker import check_output


def build_graph() -> StateGraph:
    """构建并编译 Wabi UI Agent 图。"""

    workflow = StateGraph(GraphState)
    workflow.add_node("ui_generator", generate_ui_plan)
    workflow.add_node("checker",     check_output)

    workflow.set_entry_point("ui_generator")
    workflow.add_edge("ui_generator", "checker")
    workflow.add_edge("checker",     END)

    return workflow.compile()


graph = build_graph()
