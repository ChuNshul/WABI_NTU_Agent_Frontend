# -*- coding: utf-8 -*-

from langgraph.graph import StateGraph, END

from UI.state import GraphState
from UI.nodes.planner import planner
from UI.nodes.builder import builder
from UI.nodes.renderer import renderer
from UI.nodes.checker import check_output


def build_graph() -> StateGraph:
    """构建并编译 Wabi UI Agent 图。"""

    workflow = StateGraph(GraphState)
    workflow.add_node("planner",  planner)
    workflow.add_node("builder",  builder)
    workflow.add_node("renderer", renderer)
    workflow.add_node("checker",  check_output)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner",  "builder")
    workflow.add_edge("builder",  "renderer")
    workflow.add_edge("renderer", "checker")
    workflow.add_edge("checker",  END)

    return workflow.compile()


graph = build_graph()
