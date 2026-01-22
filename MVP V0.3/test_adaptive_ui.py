import sys
import os
import json
from langchain_core.messages import HumanMessage, AIMessage
from langgraph_app.orchestrator.state import GraphState
from langgraph_app.agents.ui_agent.agent import generate_ui_plan

# 1. Test Recognition
print("\n=== Test 1: Recognition ===")
mock_nutrition_data = {
    "Braised Chicken": {"calories": 350, "is_healthy": True},
    "Potatoes": {"calories": 150, "is_healthy": True},
    "total": {"calories": 520}
}
state_rec = GraphState(
    intent="recognition",
    agent_response="I identified Braised Chicken and Potatoes.",
    nutrition_facts=mock_nutrition_data,
    has_image=True,
    user_input="What did I just eat?"
)
state_rec = generate_ui_plan(state_rec)
print(json.dumps(state_rec.ui_plan, indent=2))


# 2. Test Recommendation (Rich Data)
print("\n=== Test 2: Recommendation ===")
mock_restaurants = [
    {
        "id": 1, 
        "name": "SaladStop! @ Tangs", 
        "desc": "Caesar Salad", 
        "rating": 4.5, 
        "price": 2, 
        "dist": 300, 
        "is_veg": True, 
        "price_str": "$$", 
        "dist_str": "300m"
    },
    {
        "id": 2, 
        "name": "Grain Traders", 
        "desc": "Brown Rice Bowl", 
        "rating": 4.5, 
        "price": 3, 
        "dist": 500, 
        "is_veg": False, 
        "price_str": "$$$", 
        "dist_str": "500m"
    }
]

state_rec_food = GraphState(
    intent="recommendation",
    agent_response="Here are some healthy options.",
    recommended_restaurants=mock_restaurants,
    user_input="Recommend some healthy food nearby."
)

state_rec_food = generate_ui_plan(state_rec_food)
print(json.dumps(state_rec_food.ui_plan, indent=2))

# 3. Test Contextual Follow-up
print("\n=== Test 3: Contextual Follow-up ===")
chat_history = [
    HumanMessage(content="Is this healthy?"),
    AIMessage(content="It has 520 calories."),
    HumanMessage(content="What about sodium?")
]

state_context = GraphState(
    intent="generic",
    agent_response="The sodium content depends on the sauce.",
    chat_history=chat_history,
    user_input="What about sodium?",
    nutrition_facts=mock_nutrition_data # Context carried over
)

state_context = generate_ui_plan(state_context)
print(json.dumps(state_context.ui_plan, indent=2))

# Verification
plan = state_rec_food.ui_plan
has_table = any(s["type"] == "dynamic_place_table" for s in plan.get("sections", []))
has_sort_suggestion = any("Sort" in s for s in plan.get("suggestions", []))

if has_table and has_sort_suggestion:
    print("\n[PASS] Recommendation UI uses dynamic_place_table and has sort suggestions.")
else:
    print(f"\n[FAIL] Table: {has_table}, Suggestions: {has_sort_suggestion}")
