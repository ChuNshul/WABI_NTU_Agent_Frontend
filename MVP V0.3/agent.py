from typing import Any, Dict, List, Optional
import json
import os
import boto3
import re
from langgraph_app.orchestrator.state import GraphState
from langgraph_app.agents.ui_agent.ui_components import UI_COMPONENTS, SYSTEM_PROMPT_TEMPLATE

# --- Bedrock Setup ---
REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-southeast-1"
MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"

def _get_bedrock_client():
    try:
        return boto3.client(
            "bedrock-runtime",
            region_name=REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
    except Exception as e:
        print(f"Warning: Failed to initialize Bedrock client: {e}")
        return None

def generate_ui_plan(state: GraphState) -> GraphState:
    """
    Generates a UI Plan based on the current state intent and data.
    Uses LLM for adaptive generation.
    """
    # Try Adaptive Generation
    print("Attempting Adaptive UI Generation...")
    adaptive_plan = _generate_adaptive_ui_plan(state)
    if adaptive_plan:
        print("Using Adaptive UI Plan.")
        state.ui_plan = adaptive_plan
        return state

    # Basic Fallback if LLM fails (minimal valid response)
    print("Fallback to minimal UI generation.")
    state.ui_plan = {
        "mode": "error",
        "summary": "Sorry, I encountered an issue generating the display. Here is the raw response.",
        "sections": [
            {
                "type": "text",
                "content": state.agent_response or "Please try again later."
            }
        ],
        "suggestions": []
    }
    return state

def _generate_adaptive_ui_plan(state: GraphState) -> Optional[Dict[str, Any]]:
    """
    Uses LLM to generate an adaptive UI plan.
    Returns None if generation fails.
    """
    client = _get_bedrock_client()
    if not client:
        return None

    # Format Chat History
    history_str = ""
    if state.chat_history:
        for msg in state.chat_history:
            role = "User" if msg.type == "human" else "Assistant"
            content = str(msg.content)[:500] # Truncate long messages
            history_str += f"{role}: {content}\n"

    # Prepare Context for LLM
    context_data = {
        "intent": state.intent,
        "user_input": str(state.user_input)[:1000] if state.user_input else None, 
        "agent_response": str(state.agent_response)[:1000] if state.agent_response else None,
        "nutrition_facts": state.nutrition_facts,
        "recommended_restaurants": state.recommended_restaurants,
        "has_image": state.has_image,
        "image_path": state.food_vis_path,
        "chat_history_summary": history_str
    }

    # Combine System Prompt and User Data
    full_prompt = SYSTEM_PROMPT_TEMPLATE.format(components_json=json.dumps(UI_COMPONENTS, indent=2))
    full_prompt += f"\n\nCurrent State Data:\n{json.dumps(context_data, indent=2, default=str)}"

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0.5,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": full_prompt}]}
        ]
    }

    try:
        response = client.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body)
        )
        
        result = json.loads(response["body"].read())
        output_text = result["content"][0]["text"]
        
        # Extract JSON from output
        json_match = re.search(r"\{[\s\S]*\}", output_text)
        if json_match:
            plan = json.loads(json_match.group(0))
            # Basic validation
            if "sections" in plan and isinstance(plan["sections"], list):
                return plan
            else:
                print(f"Invalid UI Plan structure: {plan.keys()}")
    except Exception as e:
        print(f"Adaptive UI generation failed: {e}")
    
    return None
