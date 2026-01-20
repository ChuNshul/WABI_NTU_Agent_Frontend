# -*- coding: utf-8 -*-
"""
Mock Data for UI Agent Development
Independent of backend logic, focused on UI/UX demonstration.
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
    "ui_plan": {
        "mode": "recognition",
        "summary": "I identified: Braised Chicken, Potatoes, Bok Choy, Noodles, and Red Chili Oil Sauce.",
        "sections": [
            {
                "type": "image_display",
                "caption": "Analyzed Food Image"
            },
            {
                "type": "key_value_list",
                "title": "Nutrition Breakdown",
                "items": [
                    {"label": "Braised Chicken", "value": "350 kcal", "highlight": True},
                    {"label": "Potatoes", "value": "150 kcal", "highlight": True},
                    {"label": "Bok Choy", "value": "20 kcal", "highlight": True},
                    {"label": "Noodles", "value": "200 kcal", "highlight": False},
                    {"label": "Red Chili Oil Sauce", "value": "120 kcal", "highlight": False}
                ]
            },
            {
                "type": "highlight_box",
                "content": "Total Calories: 840 kcal (High)",
                "variant": "warning"
            }
        ],
        "suggestions": ["Is this healthy?", "Get recipe", "Confirm is wrong"]
    }
}

# 2. 模拟餐厅推荐结果 (Recommendation Scenario - Dynamic Table)
MOCK_RECOMMENDATION_TABLE_RESULT = {
    "intent": "recommendation",
    "ui_plan": {
        "mode": "recommendation",
        "summary": "Found 5 healthy options nearby.",
        "sections": [
            {
                "type": "dynamic_place_table",
                "title": "Nearby Options",
                "items": [
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
        ],
        "suggestions": []
    }
}

# 2.1 模拟按价格排序 (Sort by Price)
MOCK_RECOMMENDATION_SORT_PRICE = {
    "intent": "recommendation",
    "ui_plan": {
        "mode": "recommendation",
        "summary": "Sorted by Price (Low to High)",
        "sections": [
            {
                "type": "place_list",
                "items": [
                    {
                        "name": "Hawker Chan",
                        "description": "Soya Sauce Chicken Rice",
                        "rating": 4.2,
                        "meta": "$ • 600m"
                    },
                    {
                        "name": "Encik Tan",
                        "description": "Wanton Noodles",
                        "rating": 4.0,
                        "meta": "$ • 550m"
                    },
                    {
                        "name": "SaladStop! @ Tangs",
                        "description": "Caesar Salad",
                        "rating": 4.5,
                        "meta": "$$ • 300m"
                    }
                ]
            }
        ],
        "suggestions": ["Sort by Distance 📍", "Filter: Veg 🥦", "Clear Filters 🔄"]
    }
}

# 2.2 模拟按距离排序 (Sort by Distance)
MOCK_RECOMMENDATION_SORT_DISTANCE = {
    "intent": "recommendation",
    "ui_plan": {
        "mode": "recommendation",
        "summary": "Sorted by Distance (Nearest First)",
        "sections": [
            {
                "type": "place_list",
                "items": [
                    {
                        "name": "7-Eleven Ready Meals",
                        "description": "Quick Bites",
                        "rating": 3.5,
                        "meta": "$ • 50m"
                    },
                    {
                        "name": "Starbucks Coffee",
                        "description": "Sandwiches & Wraps",
                        "rating": 4.4,
                        "meta": "$$ • 150m"
                    },
                    {
                        "name": "SaladStop! @ Tangs",
                        "description": "Caesar Salad",
                        "rating": 4.5,
                        "meta": "$$ • 300m"
                    }
                ]
            }
        ],
        "suggestions": ["Sort by Price ⬇️", "Filter: Veg 🥦", "Clear Filters 🔄"]
    }
}

# 2.3 模拟素食过滤 (Filter: Veg)
MOCK_RECOMMENDATION_FILTER_VEG = {
    "intent": "recommendation",
    "ui_plan": {
        "mode": "recommendation",
        "summary": "Filtered: Vegetarian Options",
        "sections": [
            {
                "type": "place_list",
                "items": [
                    {
                        "name": "Greendot",
                        "description": "Bento Sets, Laksa (Vegetarian)",
                        "rating": 4.6,
                        "meta": "$$ • 350m"
                    },
                    {
                        "name": "Real Food",
                        "description": "Organic, Vegan options available",
                        "rating": 4.7,
                        "meta": "$$$ • 600m"
                    }
                ]
            }
        ],
        "suggestions": ["Sort by Price ⬇️", "Sort by Distance 📍", "Clear Filters 🔄"]
    }
}

# 3. 模拟错误处理/纠正 (Error Correction Scenario)
MOCK_CORRECTION_RESULT = {
    "intent": "correction",
    "ui_plan": {
        "mode": "form",
        "summary": "I apologize for the mistake. Please help me identify the correct food.",
        "sections": [
            {
                "type": "text",
                "content": "I see I made a mistake. What is the correct name of the food?"
            },
            {
                "type": "input_prompt",
                "placeholder": "e.g., Nasi Lemak, Laksa...",
                "action_label": "Update Correction"
            }
        ],
        "suggestions": ["Back"]
    }
}

# 4. 模拟食谱获取 (Recipe Scenario)
MOCK_RECIPE_RESULT = {
    "intent": "recipe",
    "ui_plan": {
        "mode": "recipe",
        "summary": "Here is a healthy recipe for Braised Chicken with Potatoes.",
        "sections": [
            {
                "type": "text",
                "content": "This home-style dish is lower in sodium and uses lean chicken breast."
            },
            {
                "type": "key_value_list",
                "title": "Ingredients",
                "items": [
                    {"label": "Chicken Breast", "value": "300g", "highlight": True},
                    {"label": "Potatoes", "value": "2 medium", "highlight": True},
                    {"label": "Light Soy Sauce", "value": "1 tbsp", "highlight": True},
                    {"label": "Ginger & Garlic", "value": "To taste", "highlight": True}
                ]
            },
            {
                "type": "text",
                "content": "**Instructions:**\n1. Marinate chicken with soy sauce and ginger for 15 mins.\n2. Stir-fry garlic until fragrant, add chicken and brown.\n3. Add potatoes and water, simmer for 20 mins until tender.\n4. Garnish with green onions and serve."
            }
        ],
        "suggestions": ["Save to favorites", "Back"]
    }
}

# 5. 模拟健康分析结果 (Analysis Scenario)
MOCK_ANALYSIS_RESULT = {
    "intent": "analysis",
    "ui_plan": {
        "mode": "analysis",
        "summary": "This meal is high in calories and sodium.",
        "sections": [
            {
                "type": "highlight_box",
                "content": "Health Score: 6/10",
                "variant": "info"
            },
            {
                "type": "text",
                "content": "**Analysis:**\n- **Pros:** Good source of protein (Chicken) and vegetables (Bok Choy).\n- **Cons:** High sodium content in the sauce and refined carbs in noodles.\n\n**Suggestion:** Drink more water and try to eat more vegetables."
            }
        ],
        "suggestions": ["Get healthier alternative", "Back"]
    }
}

# 6. 模拟纠错后的结果 (Corrected Result Scenario)
MOCK_CORRECTED_RESULT = {
    "intent": "recognition",
    "agent_response": "Updated to: KFC Fried Chicken",
    "ui_plan": {
        "mode": "recognition",
        "summary": "I identified: KFC Fried Chicken (Updated)",
        "sections": [
            {
                "type": "image_display",
                "caption": "Updated Food Image"
            },
            {
                "type": "key_value_list",
                "title": "Nutrition Breakdown",
                "items": [
                    {"label": "Fried Chicken", "value": "320 kcal", "highlight": False},
                    {"label": "French Fries", "value": "280 kcal", "highlight": False},
                    {"label": "Cole Slaw", "value": "150 kcal", "highlight": True}
                ]
            },
            {
                "type": "highlight_box",
                "content": "Total Calories: 750 kcal (High)",
                "variant": "warning"
            },
            {
                "type": "text",
                "content": "✅ **Success:** Food name updated to **KFC Fried Chicken**."
            }
        ],
        "suggestions": ["Is this healthy?", "Get recipe", "Confirm is wrong"]
    }
}

# 6.1 模拟纠错后的食谱 (Corrected Recipe Scenario - KFC)
MOCK_CORRECTED_RECIPE_RESULT = {
    "intent": "recipe",
    "ui_plan": {
        "mode": "recipe",
        "summary": "Here is a recipe for homemade Fried Chicken (KFC Style).",
        "sections": [
            {
                "type": "text",
                "content": "This recipe recreates the classic crispy fried chicken taste at home."
            },
            {
                "type": "key_value_list",
                "title": "Ingredients",
                "items": [
                    {"label": "Chicken Parts", "value": "8 pieces", "highlight": True},
                    {"label": "Flour", "value": "2 cups", "highlight": False},
                    {"label": "Spices (Secret Mix)", "value": "11 herbs", "highlight": True},
                    {"label": "Buttermilk", "value": "1 cup", "highlight": False}
                ]
            },
            {
                "type": "text",
                "content": "**Instructions:**\n1. Soak chicken in buttermilk for 1 hour.\n2. Mix flour with 11 secret herbs and spices.\n3. Dredge chicken in flour mixture.\n4. Deep fry at 350°F (175°C) until golden brown and cooked through."
            }
        ],
        "suggestions": ["Save to favorites", "Back"]
    }
}

# 6.2 模拟纠错后的分析 (Corrected Analysis Scenario - KFC)
MOCK_CORRECTED_ANALYSIS_RESULT = {
    "intent": "analysis",
    "ui_plan": {
        "mode": "analysis",
        "summary": "This meal is very high in calories, fats, and sodium.",
        "sections": [
            {
                "type": "highlight_box",
                "content": "Health Score: 2/10",
                "variant": "warning"
            },
            {
                "type": "text",
                "content": "**Analysis:**\n- **Pros:** High protein content.\n- **Cons:** Deep fried, high saturated fat, very high sodium, and low fiber.\n\n**Suggestion:** Limit consumption. Remove skin to reduce fat. Add a side salad."
            }
        ],
        "suggestions": ["Get healthier alternative", "Back"]
    }
}

# 7. 模拟Guardrail触发 (Guardrail Scenario)
MOCK_GUARDRAIL_RESULT = {
    "intent": "guardrail",
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
