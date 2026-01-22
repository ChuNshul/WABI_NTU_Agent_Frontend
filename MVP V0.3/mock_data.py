# -*- coding: utf-8 -*-
"""
Mock Data for UI Agent Development
Independent of backend logic, focused on UI/UX demonstration.
Refactored to match Orchestrator output schema.
"""

# 1. 模拟食物识别结果 (Recognition Scenario)
MOCK_RECOGNITION_RESULT = {
    "intent": "recognition",
    "agent_response": "I identified: Braised Chicken, Potatoes, Bok Choy, Noodles, and Red Chili Oil Sauce.",
    "nutrition_facts": {
        "Braised Chicken": {"calories": 350, "is_healthy": True},
        "Potatoes": {"calories": 150, "is_healthy": True},
        "Bok Choy": {"calories": 20, "is_healthy": True},
        "Noodles": {"calories": 200, "is_healthy": False},
        "Red Chili Oil Sauce": {"calories": 120, "is_healthy": False},
        "total": {"calories": 840}
    },
    "has_image": True,
    "food_detection_json": {
        "detected_items": ["Braised Chicken", "Potatoes", "Bok Choy", "Noodles", "Red Chili Oil Sauce"]
    }
}

# 2. 模拟餐厅推荐结果 (Recommendation Scenario)
MOCK_RECOMMENDATION_TABLE_RESULT = {
    "intent": "recommendation",
    "agent_response": "Here are some healthy options nearby.",
    "recommended_restaurants": [
        {
            "id": 1, 
            "name": "SaladStop! @ Tangs", 
            "desc": "Caesar Salad, Pumpkin Soup", 
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
            "desc": "Brown Rice Bowl, Grilled Chicken", 
            "rating": 4.5, 
            "price": 3, 
            "dist": 500, 
            "is_veg": False, 
            "price_str": "$$$", 
            "dist_str": "500m"
        },
        {
            "id": 3, 
            "name": "Hawker Chan", 
            "desc": "Soya Sauce Chicken Rice", 
            "rating": 4.2, 
            "price": 1, 
            "dist": 600, 
            "is_veg": False, 
            "price_str": "$", 
            "dist_str": "600m"
        },
        {
            "id": 4, 
            "name": "Greendot", 
            "desc": "Bento Sets, Laksa (Vegetarian)", 
            "rating": 4.6, 
            "price": 2, 
            "dist": 350, 
            "is_veg": True, 
            "price_str": "$$", 
            "dist_str": "350m"
        },
        {
            "id": 5, 
            "name": "7-Eleven Ready Meals", 
            "desc": "Quick Bites", 
            "rating": 3.5, 
            "price": 1, 
            "dist": 50, 
            "is_veg": True, 
            "price_str": "$", 
            "dist_str": "50m"
        }
    ]
}

# 3. 模拟Guardrail触发 (Guardrail Scenario)
MOCK_GUARDRAIL_RESULT = {
    "intent": "guardrail",
    "safety_passed": False,
    "agent_response": "I want to be sensitive to how you’re feeling. Here are some resources that can help.",
    "ui_plan": {
        "mode": "guardrail",
        "summary": "I want to be sensitive to how you’re feeling. Here are some resources that can help.",
        "sections": [
            {
                "type": "highlight_box",
                "content": "It sounds like you may be going through a difficult time. You are not alone.",
                "variant": "warning"
            },
            {
                "type": "text",
                "content": "I’m not equipped to provide professional support, but there are people who can help you right now. Please consider reaching out to one of these 24-hour helplines:"
            },
            {
                "type": "key_value_list",
                "title": "Support Resources (Singapore)",
                "items": [
                    {"label": "SOS 24-hour Hotline", "value": "1-767", "highlight": True},
                    {"label": "National Mindline", "value": "1771", "highlight": True},
                    {"label": "SAMH Helpline", "value": "1800-283-7019", "highlight": True},
                    {"label": "Emergency", "value": "995", "highlight": False}
                ]
            },
            {
                "type": "text",
                "content": "If you are in immediate danger, please call **995** immediately."
            }
        ],
        "suggestions": []
    }
}
