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

MOCK_USER_HISTORY = {
    "days": [
        {
            "date": "2026-02-03",
            "meals": [
                {"name": "早餐", "items": ["燕麦牛奶", "香蕉"], "calories": 420, "protein_g": 18, "carbs_g": 62, "fat_g": 12, "sodium_mg": 260, "tags": ["home"]},
                {"name": "午餐", "items": ["鸡饭", "青菜"], "calories": 760, "protein_g": 34, "carbs_g": 92, "fat_g": 26, "sodium_mg": 980, "tags": ["hawker", "high_sodium"]},
                {"name": "晚餐", "items": ["三文鱼沙拉", "酸奶"], "calories": 610, "protein_g": 38, "carbs_g": 28, "fat_g": 34, "sodium_mg": 540, "tags": ["healthy"]}
            ]
        },
        {
            "date": "2026-02-04",
            "meals": [
                {"name": "早餐", "items": ["咖啡", "吐司花生酱"], "calories": 380, "protein_g": 12, "carbs_g": 44, "fat_g": 18, "sodium_mg": 420, "tags": ["quick"]},
                {"name": "午餐", "items": ["鱼丸面", "油条"], "calories": 890, "protein_g": 28, "carbs_g": 118, "fat_g": 30, "sodium_mg": 1380, "tags": ["hawker", "high_sodium"]},
                {"name": "晚餐", "items": ["鸡胸肉", "糙米", "西兰花"], "calories": 680, "protein_g": 46, "carbs_g": 74, "fat_g": 16, "sodium_mg": 520, "tags": ["high_protein", "healthy"]}
            ]
        },
        {
            "date": "2026-02-05",
            "meals": [
                {"name": "早餐", "items": ["豆浆", "水煮蛋"], "calories": 310, "protein_g": 19, "carbs_g": 18, "fat_g": 16, "sodium_mg": 280, "tags": ["home"]},
                {"name": "午餐", "items": ["麻辣香锅"], "calories": 1050, "protein_g": 42, "carbs_g": 88, "fat_g": 56, "sodium_mg": 2100, "tags": ["spicy", "high_sodium"]},
                {"name": "晚餐", "items": ["蔬菜汤", "全麦面包"], "calories": 520, "protein_g": 16, "carbs_g": 70, "fat_g": 18, "sodium_mg": 740, "tags": ["light"]}
            ]
        },
        {
            "date": "2026-02-06",
            "meals": [
                {"name": "早餐", "items": ["酸奶麦片"], "calories": 360, "protein_g": 16, "carbs_g": 48, "fat_g": 12, "sodium_mg": 220, "tags": ["home"]},
                {"name": "午餐", "items": ["寿司", "味增汤"], "calories": 740, "protein_g": 32, "carbs_g": 98, "fat_g": 22, "sodium_mg": 1280, "tags": ["high_sodium"]},
                {"name": "晚餐", "items": ["牛肉炒饭"], "calories": 860, "protein_g": 34, "carbs_g": 110, "fat_g": 28, "sodium_mg": 1160, "tags": ["takeaway"]}
            ]
        },
        {
            "date": "2026-02-07",
            "meals": [
                {"name": "早餐", "items": ["水果", "坚果"], "calories": 330, "protein_g": 10, "carbs_g": 34, "fat_g": 18, "sodium_mg": 90, "tags": ["healthy"]},
                {"name": "午餐", "items": ["沙拉", "汤"], "calories": 520, "protein_g": 26, "carbs_g": 46, "fat_g": 22, "sodium_mg": 620, "tags": ["healthy"]},
                {"name": "晚餐", "items": ["火锅"], "calories": 1120, "protein_g": 52, "carbs_g": 84, "fat_g": 66, "sodium_mg": 2400, "tags": ["social", "high_sodium"]}
            ]
        },
        {
            "date": "2026-02-08",
            "meals": [
                {"name": "早餐", "items": ["豆腐脑"], "calories": 280, "protein_g": 14, "carbs_g": 24, "fat_g": 12, "sodium_mg": 520, "tags": ["hawker"]},
                {"name": "午餐", "items": ["意大利面", "可乐"], "calories": 980, "protein_g": 24, "carbs_g": 138, "fat_g": 34, "sodium_mg": 1480, "tags": ["sweet_drink"]},
                {"name": "晚餐", "items": ["鸡汤面", "青菜"], "calories": 720, "protein_g": 30, "carbs_g": 98, "fat_g": 18, "sodium_mg": 1320, "tags": ["high_sodium"]}
            ]
        },
        {
            "date": "2026-02-09",
            "meals": [
                {"name": "早餐", "items": ["牛奶", "全麦三明治"], "calories": 450, "protein_g": 22, "carbs_g": 52, "fat_g": 16, "sodium_mg": 520, "tags": ["home"]},
                {"name": "午餐", "items": ["清汤面", "卤蛋"], "calories": 660, "protein_g": 26, "carbs_g": 96, "fat_g": 18, "sodium_mg": 1120, "tags": ["high_sodium"]},
                {"name": "晚餐", "items": ["烤鸡", "烤蔬菜"], "calories": 640, "protein_g": 44, "carbs_g": 36, "fat_g": 30, "sodium_mg": 620, "tags": ["healthy"]}
            ]
        }
    ]
}
