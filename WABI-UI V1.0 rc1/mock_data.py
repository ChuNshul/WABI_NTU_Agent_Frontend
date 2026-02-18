# -*- coding: utf-8 -*-
"""
Mock Data for UI Agent Development
Independent of backend logic, focused on UI/UX demonstration.
Refactored to match Orchestrator output schema.
"""

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

MOCK_GUARDRAIL_RESULT = {
    "intent": "guardrail",
    "safety_passed": False,
    "agent_response": "I want to be sensitive to how youâ€™re feeling. Here are some resources that can help.",
    "ui_plan": {
        "mode": "guardrail",
        "summary": "I want to be sensitive to how youâ€™re feeling. Here are some resources that can help.",
        "sections": [
            {
                "type": "highlight_box",
                "content": "It sounds like you may be going through a difficult time. You are not alone.",
                "variant": "warning"
            },
            {
                "type": "text",
                "content": "Iâ€™m not equipped to provide professional support, but there are people who can help you right now. Please consider reaching out to one of these 24-hour helplines:"
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

MOCK_USER_HISTORY = {
    "days": [
        {
            "date": "2026-02-03",
            "meals": [
                {"name": "æ—©é¤", "items": ["ç‡•éº¦ç‰›å¥¶", "é¦™è•‰"], "calories": 420, "protein_g": 18, "carbs_g": 62, "fat_g": 12, "sodium_mg": 260, "tags": ["home"]},
                {"name": "åˆé¤", "items": ["é¸¡é¥­", "é’èœ"], "calories": 760, "protein_g": 34, "carbs_g": 92, "fat_g": 26, "sodium_mg": 980, "tags": ["hawker", "high_sodium"]},
                {"name": "æ™šé¤", "items": ["ä¸‰æ–‡é±¼æ²™æ‹‰", "é…¸å¥¶"], "calories": 610, "protein_g": 38, "carbs_g": 28, "fat_g": 34, "sodium_mg": 540, "tags": ["healthy"]}
            ]
        },
        {
            "date": "2026-02-04",
            "meals": [
                {"name": "æ—©é¤", "items": ["å’–å•¡", "åå¸èŠ±ç”Ÿé…±"], "calories": 380, "protein_g": 12, "carbs_g": 44, "fat_g": 18, "sodium_mg": 420, "tags": ["quick"]},
                {"name": "åˆé¤", "items": ["é±¼ä¸¸é¢", "æ²¹æ¡"], "calories": 890, "protein_g": 28, "carbs_g": 118, "fat_g": 30, "sodium_mg": 1380, "tags": ["hawker", "high_sodium"]},
                {"name": "æ™šé¤", "items": ["é¸¡èƒ¸è‚‰", "ç³™ç±³", "è¥¿å…°èŠ±"], "calories": 680, "protein_g": 46, "carbs_g": 74, "fat_g": 16, "sodium_mg": 520, "tags": ["high_protein", "healthy"]}
            ]
        },
        {
            "date": "2026-02-05",
            "meals": [
                {"name": "æ—©é¤", "items": ["è±†æµ†", "æ°´ç…®è›‹"], "calories": 310, "protein_g": 19, "carbs_g": 18, "fat_g": 16, "sodium_mg": 280, "tags": ["home"]},
                {"name": "åˆé¤", "items": ["éº»è¾£é¦™é”…"], "calories": 1050, "protein_g": 42, "carbs_g": 88, "fat_g": 56, "sodium_mg": 2100, "tags": ["spicy", "high_sodium"]},
                {"name": "æ™šé¤", "items": ["è”¬èœæ±¤", "å…¨éº¦é¢åŒ…"], "calories": 520, "protein_g": 16, "carbs_g": 70, "fat_g": 18, "sodium_mg": 740, "tags": ["light"]}
            ]
        },
        {
            "date": "2026-02-06",
            "meals": [
                {"name": "æ—©é¤", "items": ["é…¸å¥¶éº¦ç‰‡"], "calories": 360, "protein_g": 16, "carbs_g": 48, "fat_g": 12, "sodium_mg": 220, "tags": ["home"]},
                {"name": "åˆé¤", "items": ["å¯¿å¸", "å‘³å¢žæ±¤"], "calories": 740, "protein_g": 32, "carbs_g": 98, "fat_g": 22, "sodium_mg": 1280, "tags": ["high_sodium"]},
                {"name": "æ™šé¤", "items": ["ç‰›è‚‰ç‚’é¥­"], "calories": 860, "protein_g": 34, "carbs_g": 110, "fat_g": 28, "sodium_mg": 1160, "tags": ["takeaway"]}
            ]
        },
        {
            "date": "2026-02-07",
            "meals": [
                {"name": "æ—©é¤", "items": ["æ°´æžœ", "åšæžœ"], "calories": 330, "protein_g": 10, "carbs_g": 34, "fat_g": 18, "sodium_mg": 90, "tags": ["healthy"]},
                {"name": "åˆé¤", "items": ["æ²™æ‹‰", "æ±¤"], "calories": 520, "protein_g": 26, "carbs_g": 46, "fat_g": 22, "sodium_mg": 620, "tags": ["healthy"]},
                {"name": "æ™šé¤", "items": ["ç«é”…"], "calories": 1120, "protein_g": 52, "carbs_g": 84, "fat_g": 66, "sodium_mg": 2400, "tags": ["social", "high_sodium"]}
            ]
        },
        {
            "date": "2026-02-08",
            "meals": [
                {"name": "æ—©é¤", "items": ["è±†è…è„‘"], "calories": 280, "protein_g": 14, "carbs_g": 24, "fat_g": 12, "sodium_mg": 520, "tags": ["hawker"]},
                {"name": "åˆé¤", "items": ["æ„å¤§åˆ©é¢", "å¯ä¹"], "calories": 980, "protein_g": 24, "carbs_g": 138, "fat_g": 34, "sodium_mg": 1480, "tags": ["sweet_drink"]},
                {"name": "æ™šé¤", "items": ["é¸¡æ±¤é¢", "é’èœ"], "calories": 720, "protein_g": 30, "carbs_g": 98, "fat_g": 18, "sodium_mg": 1320, "tags": ["high_sodium"]}
            ]
        },
        {
            "date": "2026-02-09",
            "meals": [
                {"name": "æ—©é¤", "items": ["ç‰›å¥¶", "å…¨éº¦ä¸‰æ˜Žæ²»"], "calories": 450, "protein_g": 22, "carbs_g": 52, "fat_g": 16, "sodium_mg": 520, "tags": ["home"]},
                {"name": "åˆé¤", "items": ["æ¸…æ±¤é¢", "å¤è›‹"], "calories": 660, "protein_g": 26, "carbs_g": 96, "fat_g": 18, "sodium_mg": 1120, "tags": ["high_sodium"]},
                {"name": "æ™šé¤", "items": ["çƒ¤é¸¡", "çƒ¤è”¬èœ"], "calories": 640, "protein_g": 44, "carbs_g": 36, "fat_g": 30, "sodium_mg": 620, "tags": ["healthy"]}
            ]
        }
    ]
}