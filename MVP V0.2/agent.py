from typing import Any, Dict, List, Optional
import json
from langgraph_app.orchestrator.state import GraphState

def generate_ui_plan(state: GraphState) -> GraphState:
    """
    Generates a generic UI Plan based on the current state intent and data.
    The UI Plan is a platform-agnostic representation of the interface.
    """
    intent = state.intent
    plan = {
        "mode": intent,
        "summary": state.agent_response or "Here is the information you requested.",
        "sections": [],
        "suggestions": [],
        "telemetry_tags": []
    }

    if intent == "recommendation":
        _build_recommendation_ui(state, plan)
    elif intent == "recognition":
        _build_recognition_ui(state, plan)
    else:
        # Generic/Fallback UI
        plan["mode"] = "generic"
        plan["sections"].append({
            "type": "text",
            "content": state.agent_response or "How can I help you today?"
        })

    state.ui_plan = plan
    return state

def _build_recommendation_ui(state: GraphState, plan: Dict[str, Any]):
    """Builds UI sections for food recommendations."""
    restaurants = state.recommended_restaurants or []
    
    if not restaurants:
        plan["sections"].append({
            "type": "text",
            "content": "No restaurants found nearby matching your criteria."
        })
        return

    # 1. Summary Text
    plan["sections"].append({
        "type": "text",
        "content": f"Found {len(restaurants)} healthy options near you."
    })

    # 2. Restaurant Carousel
    carousel_items = []
    for r in restaurants:
        name = r.get("restaurant_name") or r.get("name") or "Unknown Restaurant"
        
        # Try to find a photo (mock logic or real if available)
        # Real logic might use Google Place Photo references if available in the future
        image_url = "https://placehold.co/600x400?text=Restaurant" 
        
        # Extract top meals
        meals = r.get("completed_meal_list_grouped") or r.get("completed_meal_list") or []
        meal_desc = ""
        if meals:
            # simple summary of first meal
            first_meal = meals[0]
            if isinstance(first_meal, list):
                meal_desc = ", ".join([str(x) for x in first_meal])
            else:
                meal_desc = str(first_meal)
        
        carousel_items.append({
            "title": name,
            "subtitle": meal_desc[:60] + "..." if len(meal_desc) > 60 else meal_desc,
            "image_url": image_url,
            "details": r  # Pass full details for "Show More" interaction
        })

    plan["sections"].append({
        "type": "carousel",
        "title": "Recommended Places",
        "items": carousel_items
    })

    # 3. Suggestions
    plan["suggestions"] = ["Cheapest option", "Nearest one", "Vegetarian options"]

def _build_recognition_ui(state: GraphState, plan: Dict[str, Any]):
    """Builds UI sections for food recognition results."""
    nutrition = state.nutrition_facts or {}
    
    # 1. Detection Image (if we had the URL, we'd put it here)
    if state.has_image:
        plan["sections"].append({
            "type": "image_display",
            "caption": "Analyzed Food Image"
        })

    # 2. Nutrition Summary Table
    # Flatten the dictionary for display
    # Structure: {"Food Name": {"calories": 100, ...}}
    
    table_rows = []
    total_cal = 0
    
    for food_name, facts in nutrition.items():
        if food_name == "total": continue # Skip aggregate if present
        if not isinstance(facts, dict): continue
        
        cal = facts.get("calories", 0)
        total_cal += cal
        table_rows.append({
            "label": food_name,
            "value": f"{cal} kcal",
            "highlight": facts.get("is_healthy", True)
        })

    if table_rows:
        plan["sections"].append({
            "type": "key_value_list",
            "title": "Nutrition Breakdown",
            "items": table_rows
        })
        
        plan["sections"].append({
            "type": "highlight_box",
            "content": f"Total Calories: {total_cal} kcal",
            "variant": "success" if total_cal < 600 else "warning"
        })
    else:
        plan["sections"].append({
            "type": "text",
            "content": "Could not extract detailed nutrition info."
        })

    plan["suggestions"] = ["Is this healthy?", "Get recipe", "Log this meal"]
