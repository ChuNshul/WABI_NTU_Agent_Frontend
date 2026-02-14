# -*- coding: utf-8 -*-
"""
UI Agent Graph
Topology:
  router → clarification | food_rec_no_img | goal_no_data | llm_generator
  llm_generator → platform_enforcer (ok) | fallback (error)
  all terminal nodes → END
"""

from functools import lru_cache

from langgraph.graph import END, StateGraph

from .ui_nodes import (
    clarification_node,
    fallback_node,
    food_recognition_no_image_node,
    goal_planning_no_data_node,
    llm_ui_generator_node,
    platform_enforcer_node,
    router_node,
)
from .ui_state import UIAgentState


def build_ui_graph():
    g = StateGraph(UIAgentState)

    g.add_node("router",          router_node)
    g.add_node("clarification",   clarification_node)
    g.add_node("food_rec_no_img", food_recognition_no_image_node)
    g.add_node("goal_no_data",    goal_planning_no_data_node)
    g.add_node("llm_generator",   llm_ui_generator_node)
    g.add_node("platform_enforcer", platform_enforcer_node)
    g.add_node("fallback",        fallback_node)

    g.set_entry_point("router")

    g.add_conditional_edges("router", lambda s: s.get("route", "llm"), {
        "clarification":             "clarification",
        "food_recognition_no_image": "food_rec_no_img",
        "goal_planning_no_data":     "goal_no_data",
        "llm":                       "llm_generator",
    })

    g.add_conditional_edges("llm_generator", lambda s: "fallback" if s.get("error") else "platform_enforcer", {
        "platform_enforcer": "platform_enforcer",
        "fallback":          "fallback",
    })

    for node in ("clarification", "food_rec_no_img", "goal_no_data", "platform_enforcer", "fallback"):
        g.add_edge(node, END)

    return g.compile()


@lru_cache(maxsize=1)
def get_ui_graph():
    print("[UIAgent] Compiling UI graph…")
    return build_ui_graph()
