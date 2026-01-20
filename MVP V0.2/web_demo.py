import os
import sys
import uvicorn
import asyncio
from typing import List, Dict, Any, Optional, Union
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

# Mock Data Import
# Try relative import first, then fallback to package import
try:
    from .mock_data import (
        MOCK_RECOGNITION_RESULT, 
        MOCK_RECOMMENDATION_TABLE_RESULT, 
        MOCK_CORRECTION_RESULT, 
        MOCK_RECIPE_RESULT,
        MOCK_ANALYSIS_RESULT,
        MOCK_CORRECTED_RESULT,
        MOCK_CORRECTED_RECIPE_RESULT,
        MOCK_CORRECTED_ANALYSIS_RESULT,
        MOCK_GUARDRAIL_RESULT
    )
except ImportError:
    from langgraph_app.agents.ui_agent.mock_data import (
        MOCK_RECOGNITION_RESULT, 
        MOCK_RECOMMENDATION_TABLE_RESULT, 
        MOCK_CORRECTION_RESULT, 
        MOCK_RECIPE_RESULT,
        MOCK_ANALYSIS_RESULT,
        MOCK_CORRECTED_RESULT,
        MOCK_CORRECTED_RECIPE_RESULT,
        MOCK_CORRECTED_ANALYSIS_RESULT,
        MOCK_GUARDRAIL_RESULT
    )

# Set Mock Mode
MOCK_MODE = True  # Toggle this to False to use real backend
MOCK_STATE = {"is_corrected": False}

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: Union[str, List[Dict[str, Any]]]
    patient_id: Optional[str] = "demo_user"

def _truncate_log(data: Any, max_len: int = 100) -> Any:
    """Helper to truncate long strings/lists/dicts for logging"""
    if isinstance(data, str):
        if len(data) > max_len:
            return data[:max_len] + "..."
        return data
    elif isinstance(data, list):
        return [_truncate_log(x, max_len) for x in data]
    elif isinstance(data, dict):
        return {k: _truncate_log(v, max_len) for k, v in data.items()}
    return data

@app.post("/api/ui")
async def get_ui_response(request: ChatRequest):
    # Log truncated request to avoid flooding console with base64
    print(f"Received request: {_truncate_log(request.message)}")
    
    if MOCK_MODE:
        await asyncio.sleep(1.5) # Simulate processing delay
        
        # Simple heuristic to choose mock response
        msg_content = request.message
        is_image = False
        
        if isinstance(msg_content, list):
            for item in msg_content:
                if isinstance(item, dict) and (item.get("type") == "image_url" or "image" in item):
                    is_image = True
                    break
        
        text_content = ""
        if isinstance(msg_content, str):
            text_content = msg_content.lower()
        elif isinstance(msg_content, list):
             for item in msg_content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_content += item.get("text", "").lower()

        if is_image:
            print("[MOCK] Returning Recognition Result")
            MOCK_STATE["is_corrected"] = False # Reset state on new image
            return JSONResponse(content={"web_ui_plan": MOCK_RECOGNITION_RESULT["ui_plan"]})
        
        # Keyword matching for Mock Routing
        text_lower = text_content.lower()
        
        # 0. Handle Guardrails (Priority)
        if any(k in text_lower for k in ["die", "suicide", "kill", "depressed", "sad", "harm", "pain"]):
             print("[MOCK] Returning Guardrail Result")
             return JSONResponse(content={"web_ui_plan": MOCK_GUARDRAIL_RESULT["ui_plan"]})

        # 1. Handle Correction SUBMISSION (user actually corrected it)
        # Check for "correction:" prefix added by frontend JS or explicit "updated" intent
        if text_lower.startswith("correction:") or "it is" in text_lower or "actually" in text_lower:
             print("[MOCK] Returning Corrected Result")
             MOCK_STATE["is_corrected"] = True # Set corrected state
             return JSONResponse(content={"web_ui_plan": MOCK_CORRECTED_RESULT["ui_plan"]})

        # 2. Handle Correction REQUEST (user says it's wrong)
        if "wrong" in text_lower or "mistake" in text_lower:
            print("[MOCK] Returning Correction Form")
            return JSONResponse(content={"web_ui_plan": MOCK_CORRECTION_RESULT["ui_plan"]})
        
        # 3. Handle Recipe
        elif any(k in text_lower for k in ["recipe", "cook", "how to make"]):
            print("[MOCK] Returning Recipe Result")
            if MOCK_STATE["is_corrected"]:
                return JSONResponse(content={"web_ui_plan": MOCK_CORRECTED_RECIPE_RESULT["ui_plan"]})
            else:
                return JSONResponse(content={"web_ui_plan": MOCK_RECIPE_RESULT["ui_plan"]})
        
        # 4. Handle Analysis/Log
        elif any(k in text_lower for k in ["healthy", "nutrition", "log", "analysis"]):
             print("[MOCK] Returning Analysis Result")
             if MOCK_STATE["is_corrected"]:
                 return JSONResponse(content={"web_ui_plan": MOCK_CORRECTED_ANALYSIS_RESULT["ui_plan"]})
             else:
                 return JSONResponse(content={"web_ui_plan": MOCK_ANALYSIS_RESULT["ui_plan"]})
        
        # 5. Handle "Back" (Return to Recognition)
        elif "back" in text_lower:
             print("[MOCK] Returning Recognition Result (Back)")
             if MOCK_STATE["is_corrected"]:
                 return JSONResponse(content={"web_ui_plan": MOCK_CORRECTED_RESULT["ui_plan"]})
             else:
                 return JSONResponse(content={"web_ui_plan": MOCK_RECOGNITION_RESULT["ui_plan"]})
        
        # 6. Handle "Healthier Alternative" (Return Recommendation)
        elif "alternative" in text_lower:
             print("[MOCK] Returning Recommendation Result (Alternative)")
             return JSONResponse(content={"web_ui_plan": MOCK_RECOMMENDATION_TABLE_RESULT["ui_plan"]})
        
        # 7. Handle Filters/Sort (Client-side now, but keeping backend response for direct queries)
        elif any(k in text_lower for k in ["price", "cheap", "distance", "near", "veg", "plant", "clear", "reset"]):
             print("[MOCK] Returning Table Recommendation for Sorting/Filtering")
             return JSONResponse(content={"web_ui_plan": MOCK_RECOMMENDATION_TABLE_RESULT["ui_plan"]})

        else:
            print("[MOCK] Returning Recommendation Result")
            return JSONResponse(content={"web_ui_plan": MOCK_RECOMMENDATION_TABLE_RESULT["ui_plan"]})

    # Real Backend Logic (Commented out/Bypassed for now)
    # ... (Original Orchestrator Logic) ...
    return JSONResponse(content={"error": "Real backend disabled in this refactor step"})

@app.post("/api/reset")
async def reset_state():
    MOCK_STATE["is_corrected"] = False
    return JSONResponse(content={"status": "success", "message": "State reset"})

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wabi Agent - UI Demo (Mock)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        :root {
            --sidebar-width: 280px;
            --primary-color: #2563eb;
            --bg-color: #f3f4f6;
        }
        body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
        
        /* Layout */
        .app-container { display: flex; height: 100vh; background: var(--bg-color); }
        
        /* Sidebar */
        .sidebar {
            width: var(--sidebar-width);
            background: #1f2937;
            color: white;
            display: flex;
            flex-direction: column;
            padding: 20px;
            box-shadow: 2px 0 5px rgba(0,0,0,0.1);
        }
        .logo-area { font-size: 24px; font-weight: bold; margin-bottom: 30px; display: flex; items-center; gap: 10px; }
        .nav-item { padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 10px; }
        .nav-item:hover { background: rgba(255,255,255,0.1); }
        .nav-item.active { background: var(--primary-color); }
        .nav-icon { width: 20px; height: 20px; }
        
        /* Main Chat Area */
        .main-content { flex: 1; display: flex; flex-direction: column; position: relative; }
        
        /* Header */
        .header { background: white; padding: 15px 30px; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center; }
        .header-title { font-size: 18px; font-weight: 600; color: #1f2937; }
        .status-badge { font-size: 12px; padding: 4px 12px; border-radius: 12px; background: #e0f2fe; color: #0284c7; }

        .chat-history { flex: 1; overflow-y: auto; padding: 30px; display: flex; flex-direction: column; gap: 24px; scroll-behavior: smooth; }
        
        /* Message Styles */
        .message-group { position: relative; }
        .ai-message-container { display: flex; gap: 16px; max-width: 85%; animation: fadeIn 0.3s ease; }
        .user-message-container { display: flex; justify-content: flex-end; align-items: center; margin-bottom: 10px; animation: fadeIn 0.3s ease; }
        
        /* Delete Button */
        .delete-btn {
            opacity: 0;
            transition: all 0.2s;
            cursor: pointer;
            color: #9ca3af;
            padding: 6px;
            margin-right: 12px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .delete-btn:hover { color: #ef4444; background-color: #fee2e2; }
        .message-group:hover .delete-btn { opacity: 1; }
        
        .avatar {
            width: 36px; height: 36px; border-radius: 50%; 
            display: flex; align-items: center; justify-content: center;
            font-weight: bold; font-size: 14px; flex-shrink: 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .avatar.ai { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; }
        .avatar.user { background: #e5e7eb; color: #4b5563; }
        
        .message-bubble {
            padding: 16px 20px; border-radius: 16px; line-height: 1.6;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05); position: relative;
        }
        .ai-message .message-bubble { background: white; border-top-left-radius: 4px; color: #374151; }
        .user-message .message-bubble { background: var(--primary-color); color: white; border-top-right-radius: 4px; }

        /* Input Area */
        .input-wrapper { background: white; padding: 20px; border-top: 1px solid #e5e7eb; }
        .input-box { 
            max-width: 900px; margin: 0 auto; background: white; 
            border: 1px solid #e5e7eb; border-radius: 12px; 
            padding: 12px; display: flex; gap: 12px; align-items: flex-end;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            transition: box-shadow 0.2s;
        }
        .input-box:focus-within { box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-color: #bfdbfe; }
        
        textarea {
            width: 100%; border: none; resize: none; outline: none; max-height: 120px;
            padding: 8px 0; font-size: 15px; line-height: 1.5;
        }

        /* Animations */
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Process Steps */
        .process-steps { margin-top: 12px; padding-top: 12px; border-top: 1px solid #f3f4f6; }
        .step-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #6b7280; margin-bottom: 6px; }
        .step-icon { width: 14px; height: 14px; border-radius: 50%; border: 2px solid #e5e7eb; }
        .step-item.active .step-icon { border-color: #2563eb; border-top-color: transparent; animation: spin 1s linear infinite; }
        .step-item.done .step-icon { background: #10b981; border-color: #10b981; position: relative; }
        .step-item.done .step-icon::after { content: '✓'; color: white; font-size: 9px; position: absolute; top: -1px; left: 2px; }
        
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="logo-area">
                <div style="width:32px;height:32px;background:#3b82f6;border-radius:8px;"></div>
                WABI Agent
            </div>
            
            <div class="nav-item active" onclick="switchView('chat')">
                <span>💬</span> Chat Interface
            </div>
            <div class="nav-item" onclick="switchView('favorites')">
                <span>❤️</span> Favorites
            </div>
            <div class="nav-item">
                <span>⚙️</span> Settings
            </div>
            
            <div style="margin-top:auto; font-size:12px; color:#9ca3af;">
                v2.1.0 (MVP)<br>Project Wabi-C
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="header">
                <div class="header-title">Food Recognition & Recommendation</div>
                <div class="flex items-center gap-4">
                    <button onclick="resetChat()" class="text-sm text-red-500 hover:text-red-700 flex items-center gap-1 font-medium px-3 py-1 rounded-lg hover:bg-red-50 transition">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
                        Clear Chat
                    </button>
                    <div class="status-badge">● Online</div>
                </div>
            </div>

            <div class="chat-history" id="chatHistory">
                <!-- Welcome Message -->
                <div class="ai-message-container">
                    <div class="avatar ai">AI</div>
                    <div class="message-bubble">
                        Hello! I'm Wabi. I can help you identify food from photos or recommend healthy restaurants nearby.
                    </div>
                </div>
            </div>

            <!-- Favorites View (Hidden by default) -->
            <div id="favoritesView" class="hidden flex-1 overflow-y-auto p-8">
                <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
                    <span>❤️</span> Saved Favorites
                </h2>
                
                <div class="mb-8">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4 border-b pb-2">Recipes</h3>
                    <div id="fav-recipes" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <p class="text-gray-400 text-sm col-span-2">No saved recipes yet.</p>
                    </div>
                </div>

                <div>
                    <h3 class="text-lg font-semibold text-gray-700 mb-4 border-b pb-2">Restaurants</h3>
                    <div id="fav-restaurants" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <p class="text-gray-400 text-sm col-span-2">No saved restaurants yet.</p>
                    </div>
                </div>
            </div>

            <div class="input-wrapper" id="inputArea">
                <div id="imagePreview" class="hidden max-w-[900px] mx-auto mb-2 relative">
                    <img id="previewImg" src="" class="h-24 rounded-lg border border-gray-200">
                    <button onclick="clearImage()" class="absolute -top-2 left-20 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs shadow-sm">×</button>
                </div>
                
                <div class="input-box">
                    <button onclick="document.getElementById('fileInput').click()" class="p-2 text-gray-400 hover:text-blue-600 transition rounded-lg hover:bg-gray-50">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
                    </button>
                    <input type="file" id="fileInput" accept="image/*" class="hidden" onchange="handleFileSelect(this)">
                    
                    <textarea id="userInput" rows="1" placeholder="Type a message or upload a food photo..." onkeypress="handleKeyPress(event)"></textarea>
                    
                    <button onclick="sendMessage()" class="bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 transition shadow-sm">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </div>
                <div class="text-center text-xs text-gray-400 mt-2">Wabi AI can make mistakes. Please verify important information.</div>
            </div>
        </div>
    </div>

    <script>
        let currentImageBase64 = null;
        let placeTableData = []; // Store data for client-side sorting/filtering
        
        // Chat State Management
        let chatState = [
             {
                id: 'welcome-msg',
                role: 'ai',
                content: "Hello! I'm Wabi. I can help you identify food from photos or recommend healthy restaurants nearby."
            }
        ];

        // Favorites State
        let favorites = {
            recipes: [],
            restaurants: []
        };
        let currentRecipe = null; // Store current recipe being viewed

        function switchView(viewName) {
            const chatHistory = document.getElementById('chatHistory');
            const favView = document.getElementById('favoritesView');
            const inputArea = document.getElementById('inputArea');
            const navItems = document.querySelectorAll('.nav-item');
            
            navItems.forEach(el => el.classList.remove('active'));

            if (viewName === 'chat') {
                chatHistory.classList.remove('hidden');
                favView.classList.add('hidden');
                inputArea.classList.remove('hidden');
                navItems[0].classList.add('active');
                // Scroll to bottom when switching back
                setTimeout(() => chatHistory.scrollTop = chatHistory.scrollHeight, 0);
            } else if (viewName === 'favorites') {
                chatHistory.classList.add('hidden');
                favView.classList.remove('hidden');
                inputArea.classList.add('hidden');
                navItems[1].classList.add('active');
                renderFavorites();
            }
        }

        function addToFavorites(type, item) {
            if (type === 'recipe') {
                if (!item) return;
                // Check duplicate
                if (!favorites.recipes.find(r => r.title === item.title)) {
                    favorites.recipes.push(item);
                    alert('Recipe saved to favorites!');
                } else {
                    alert('Recipe already in favorites.');
                }
            } else if (type === 'restaurant') {
                if (!item) return;
                if (!favorites.restaurants.find(r => r.id === item.id)) {
                    favorites.restaurants.push(item);
                    alert('Restaurant saved to favorites!');
                } else {
                    alert('Restaurant already in favorites.');
                }
            }
        }

        function addToFavoritesById(id) {
            const item = placeTableData.find(p => p.id === id);
            if (item) addToFavorites('restaurant', item);
        }

        function removeFromFavorites(type, id) {
            if (type === 'recipe') {
                favorites.recipes = favorites.recipes.filter(r => r.id !== id);
            } else if (type === 'restaurant') {
                favorites.restaurants = favorites.restaurants.filter(r => r.id !== id);
            }
            renderFavorites();
        }

        function renderFavorites() {
            const recipeContainer = document.getElementById('fav-recipes');
            const restContainer = document.getElementById('fav-restaurants');

            // Render Recipes
            if (favorites.recipes.length === 0) {
                recipeContainer.innerHTML = '<p class="text-gray-400 text-sm col-span-2">No saved recipes yet.</p>';
            } else {
                recipeContainer.innerHTML = favorites.recipes.map(r => `
                    <div class="bg-white border rounded-xl p-4 shadow-sm hover:shadow-md transition relative">
                        <div class="flex justify-between items-start">
                            <h4 class="font-bold text-gray-800 mb-2 pr-2">${r.title || 'Untitled Recipe'}</h4>
                            <button onclick="removeFromFavorites('recipe', ${r.id})" class="text-gray-300 hover:text-red-500 transition flex-shrink-0" title="Remove">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                            </button>
                        </div>
                        <div class="text-xs text-gray-500 line-clamp-3 mb-3">${r.summary || 'No description'}</div>
                        <button onclick="switchView('chat')" class="text-xs text-blue-600 font-medium hover:underline">View in Chat</button>
                    </div>
                `).join('');
            }

            // Render Restaurants
            if (favorites.restaurants.length === 0) {
                restContainer.innerHTML = '<p class="text-gray-400 text-sm col-span-2">No saved restaurants yet.</p>';
            } else {
                restContainer.innerHTML = favorites.restaurants.map(r => `
                    <div class="bg-white border rounded-xl p-4 shadow-sm hover:shadow-md transition relative">
                        <div class="flex justify-between items-start mb-1">
                            <h4 class="font-bold text-gray-800">${r.name}</h4>
                            <div class="flex items-center gap-2">
                                <span class="text-xs bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded border border-yellow-100">⭐ ${r.rating}</span>
                                <button onclick="removeFromFavorites('restaurant', ${r.id})" class="text-gray-300 hover:text-red-500 transition" title="Remove">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                </button>
                            </div>
                        </div>
                        <div class="text-xs text-gray-500 mb-2">${r.desc}</div>
                        <div class="flex items-center gap-2 text-xs text-gray-400">
                            <span class="bg-gray-100 px-1.5 rounded">${r.price_str}</span>
                            <span>${r.dist_str}</span>
                        </div>
                    </div>
                `).join('');
            }
        }

        function renderPlaceTable(containerId, data) {
            placeTableData = data;
            const container = document.getElementById(containerId);
            if(!container) return;
            
            // Initial Render
            updatePlaceTable(containerId);
        }

        function updatePlaceTable(containerId, sortBy = null, filterVeg = false) {
            const container = document.getElementById(containerId);
            if(!container) return;

            let displayData = [...placeTableData];

            // 1. Filter
            const isVegChecked = document.getElementById(`veg-filter-${containerId}`)?.checked || false;
            if (isVegChecked) {
                displayData = displayData.filter(item => item.is_veg);
            }

            // 2. Sort
            const sortVal = document.getElementById(`sort-select-${containerId}`)?.value || 'default';
            if (sortVal === 'price_asc') {
                displayData.sort((a, b) => a.price - b.price);
            } else if (sortVal === 'dist_asc') {
                displayData.sort((a, b) => a.dist - b.dist);
            }

            // Render Controls + Table
            let controlsHtml = `
                <div class="flex flex-wrap items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <div class="flex items-center gap-2">
                        <span class="text-sm text-gray-600 font-medium">Sort by:</span>
                        <select id="sort-select-${containerId}" onchange="updatePlaceTable('${containerId}')" class="text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-200 focus:ring-opacity-50 p-1 border">
                            <option value="default" ${sortVal === 'default' ? 'selected' : ''}>Default</option>
                            <option value="price_asc" ${sortVal === 'price_asc' ? 'selected' : ''}>Price: Low to High</option>
                            <option value="dist_asc" ${sortVal === 'dist_asc' ? 'selected' : ''}>Distance: Nearest</option>
                        </select>
                    </div>
                    <div class="flex items-center gap-2">
                        <label class="inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="veg-filter-${containerId}" onchange="updatePlaceTable('${containerId}')" class="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-200 focus:ring-opacity-50" ${isVegChecked ? 'checked' : ''}>
                            <span class="ml-2 text-sm text-gray-600">Vegetarian Only 🥦</span>
                        </label>
                    </div>
                    <div class="ml-auto text-xs text-gray-400">
                        Found ${displayData.length} result(s)
                    </div>
                </div>
            `;

            let tableHtml = `
                <div class="overflow-x-auto border rounded-xl shadow-sm">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                                <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rating</th>
                                <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                                <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Dist</th>
                                <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                                <th scope="col" class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
            `;

            if (displayData.length === 0) {
                tableHtml += `<tr><td colspan="6" class="px-4 py-8 text-center text-sm text-gray-500">No matching results found.</td></tr>`;
            } else {
                displayData.forEach(item => {
                    tableHtml += `
                        <tr class="hover:bg-gray-50 transition cursor-pointer">
                            <td class="px-4 py-3 whitespace-nowrap">
                                <div class="text-sm font-medium text-gray-900">${item.name}</div>
                                <div class="text-xs text-gray-500 truncate max-w-[120px]">${item.desc}</div>
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap">
                                <div class="text-sm text-gray-900 flex items-center gap-1">
                                    <span class="text-yellow-500">★</span> ${item.rating}
                                </div>
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap">
                                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                    ${item.price_str}
                                </span>
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                ${item.dist_str}
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                ${item.is_veg ? '🥦 Veg' : '🍖 Non-Veg'}
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                <button onclick="event.stopPropagation(); addToFavoritesById(${item.id})" class="text-red-500 hover:bg-red-50 p-2 rounded-full transition border border-red-100 bg-white shadow-sm" title="Save to Favorites">
                                    ❤️
                                </button>
                            </td>
                        </tr>
                    `;
                });
            }

            tableHtml += `
                        </tbody>
                    </table>
                </div>
            `;

            container.innerHTML = controlsHtml + tableHtml;
            
            // Re-attach focus if needed (simplified here)
        }

        function handleKeyPress(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        }

        function handleFileSelect(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    currentImageBase64 = e.target.result;
                    document.getElementById('previewImg').src = currentImageBase64;
                    document.getElementById('imagePreview').classList.remove('hidden');
                };
                reader.readAsDataURL(input.files[0]);
            }
        }

        function clearImage() {
            currentImageBase64 = null;
            document.getElementById('fileInput').value = '';
            document.getElementById('imagePreview').classList.add('hidden');
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const text = input.value.trim();
            await processMessage(text);
        }

        async function handleFormSubmit(inputId) {
            const input = document.getElementById(inputId);
            const text = input.value.trim();
            if (text) {
                // Send as user message, but with "Correction: " prefix handled by backend if needed
                // Here we just send the text directly to simulate conversation
                await processMessage("Correction: " + text);
            }
        }

        async function resetChat() {
            // Call backend to reset state
            try {
                await fetch('/api/reset', { method: 'POST' });
            } catch (e) {
                console.error("Failed to reset backend state", e);
            }

            // Reset Chat State
            chatState = [
                 {
                    id: 'welcome-msg',
                    role: 'ai',
                    content: "Hello! I'm Wabi. I can help you identify food from photos or recommend healthy restaurants nearby."
                }
            ];
            
            // Re-render
            renderChatHistory();
            
            // Clear inputs
            document.getElementById('userInput').value = '';
            clearImage();
        }

        function deleteMessagePair(userMsgId, aiMsgId) {
            // Remove from State
            chatState = chatState.filter(msg => msg.id !== userMsgId && msg.id !== aiMsgId);
            
            // Re-render (This effectively "refreshes" the interface layout)
            renderChatHistory();
        }

        function renderChatHistory() {
            const history = document.getElementById('chatHistory');
            history.innerHTML = ''; // Clear DOM

            chatState.forEach(msg => {
                if (msg.role === 'user') {
                    // Render User Message
                    const userContainer = document.createElement('div');
                    userContainer.id = msg.id;
                    userContainer.className = 'user-message-container user-message message-group';
                    
                    let displayHtml = '';
                    if (msg.image) {
                        displayHtml += `<img src="${msg.image}" class="max-h-48 rounded-lg mb-2 border border-blue-400 block">`;
                    }
                    if (msg.text) {
                        displayHtml += `<div>${msg.text}</div>`;
                    }
                    
                    // Add Delete Button (linked to corresponding AI message ID if exists)
                    // We need to find the AI message ID that follows this user message
                    // Simplified: The AI message usually follows the user message immediately in our logic
                    // But in state array, we can just pass the next ID if it's AI
                    // Or simpler: The delete button knows its AI pair ID from creation time? 
                    // No, let's look it up or store it in the user msg object
                    
                    let deleteBtnHtml = '';
                    if (msg.aiPairId) {
                         deleteBtnHtml = `<button onclick="deleteMessagePair('${msg.id}', '${msg.aiPairId}')" class="delete-btn" title="Delete Q&A Pair"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>`;
                    }
                    
                    userContainer.innerHTML = deleteBtnHtml + `<div class="message-bubble">${displayHtml}</div>`;
                    history.appendChild(userContainer);

                } else if (msg.role === 'ai') {
                    // Render AI Message
                    const aiContainer = document.createElement('div');
                    aiContainer.id = msg.id;
                    aiContainer.className = 'ai-message-container ai-message message-group';
                    
                    let contentHtml = '';
                    if (msg.isLoading) {
                         contentHtml = `
                            <div class="message-bubble" style="min-width: 200px">
                                <div class="font-medium mb-2">Processing Request...</div>
                                <div class="process-steps">
                                    <div class="step-item ${msg.step >= 1 ? 'done' : 'active'}" id="step-1-${msg.id}"><div class="step-icon"></div><span>Analyzing Intent...</span></div>
                                    <div class="step-item ${msg.step >= 2 ? 'done' : (msg.step===1?'active':'')}" id="step-2-${msg.id}"><div class="step-icon"></div><span>Running Agents...</span></div>
                                    <div class="step-item ${msg.step >= 3 ? 'done' : (msg.step===2?'active':'')}" id="step-3-${msg.id}"><div class="step-icon"></div><span>Generating UI...</span></div>
                                </div>
                            </div>`;
                    } else if (msg.plan) {
                        // Render Plan
                        contentHtml = `
                            <div class="message-bubble w-full">
                                <div id="content-${msg.id}"></div>
                                <div class="process-steps mt-4">
                                     <div class="step-item done"><div class="step-icon"></div><span>Request Processed (${msg.plan ? 'UI Generated' : 'Text Only'})</span></div>
                                </div>
                            </div>
                        `;
                    } else if (msg.content) {
                        // Simple Text (e.g. Welcome)
                         contentHtml = `
                            <div class="message-bubble">
                                ${msg.content}
                            </div>
                        `;
                    }

                    aiContainer.innerHTML = `<div class="avatar ai">AI</div>${contentHtml}`;
                    history.appendChild(aiContainer);
                    
                    // Hydrate UI components if plan exists
                    if (msg.plan) {
                        const contentDiv = aiContainer.querySelector(`#content-${msg.id}`);
                        if(contentDiv) renderWebComponents(contentDiv, msg.plan);
                    }
                }
            });
            
            // Scroll to bottom
            history.scrollTop = history.scrollHeight;
        }

        async function processMessage(text) {
            if (!text && !currentImageBase64) return;
            
            // IDs
            const uniqueId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
            const userMsgId = 'msg-' + uniqueId;
            const loadingId = 'loading-' + uniqueId;
            
            // 1. Add User Message to State
            chatState.push({
                id: userMsgId,
                role: 'user',
                text: text,
                image: currentImageBase64,
                aiPairId: loadingId
            });
            
            // 2. Add AI Loading Message to State
            chatState.push({
                id: loadingId,
                role: 'ai',
                isLoading: true,
                step: 0
            });
            
            // Render Initial State
            renderChatHistory();

            // Prepare Payload
            let payload;
            if (currentImageBase64) {
                payload = {
                    message: [
                        { "type": "image_url", "image_url": {"url": currentImageBase64} }
                    ]
                };
                if (text) {
                    payload.message.unshift({"type": "text", "text": text});
                }
            } else {
                payload = { message: text };
            }

            // Reset Input
            document.getElementById('userInput').value = '';
            clearImage();

            // Simulate Progress (Update State)
            const updateProgress = (step) => {
                const aiMsg = chatState.find(m => m.id === loadingId);
                if (aiMsg) {
                    aiMsg.step = step;
                    renderChatHistory(); // Re-render to show progress
                }
            };

            const simulateProgress = async () => {
                await new Promise(r => setTimeout(r, 600));
                updateProgress(1);
                await new Promise(r => setTimeout(r, 800));
                updateProgress(2);
            };
            
            const progressPromise = simulateProgress();

            try {
                // Call API
                const response = await fetch('/api/ui', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                await progressPromise;
                
                // Update AI Message in State with Real Content
                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                if (aiMsgIndex !== -1) {
                    chatState[aiMsgIndex] = {
                        id: loadingId,
                        role: 'ai',
                        isLoading: false,
                        plan: data.web_ui_plan
                    };
                    renderChatHistory(); // Final Render
                }

            } catch (error) {
                console.error(error);
                // Show Error
                 const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                if (aiMsgIndex !== -1) {
                    chatState[aiMsgIndex] = {
                        id: loadingId,
                        role: 'ai',
                        content: `<div class="text-red-500">Error: ${error.message}</div>`
                    };
                    renderChatHistory();
                }
            }
        }

        function renderWebComponents(container, plan) {
            const wrapper = document.createElement('div');
            wrapper.className = 'space-y-4';

            // Header/Summary
            if (plan.summary) {
                wrapper.innerHTML += `<div class="text-gray-800 mb-3">${plan.summary}</div>`;
            }

            plan.sections.forEach(section => {
                if (section.type === 'carousel') {
                    let itemsHtml = '';
                    section.items.forEach(item => {
                        itemsHtml += `
                            <div class="min-w-[240px] bg-white border rounded-xl shadow-sm overflow-hidden mr-4 flex-shrink-0 transition hover:shadow-md cursor-pointer">
                                <div class="p-4">
                                    <h3 class="font-bold text-gray-800 truncate">${item.title}</h3>
                                    <p class="text-xs text-gray-500 mt-1 line-clamp-2">${item.subtitle}</p>
                                    <div class="mt-3 flex items-center justify-between">
                                         <span class="text-xs font-bold text-blue-600">View Details</span>
                                         <span class="text-xs bg-gray-100 px-2 py-1 rounded">⭐ 4.5</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    wrapper.innerHTML += `
                        <div class="mt-4">
                            <h3 class="text-sm font-bold mb-3 text-gray-400 uppercase tracking-wider flex items-center gap-2">
                                <span>🍽️</span> ${section.title}
                            </h3>
                            <div class="flex overflow-x-auto pb-4 scrollbar-hide -mx-1 px-1">${itemsHtml}</div>
                        </div>
                    `;
                } else if (section.type === 'dynamic_place_table') {
                    const tableContainerId = 'table-' + Math.random().toString(36).substr(2, 9);
                    wrapper.innerHTML += `
                        <div class="mt-4">
                            <h3 class="text-sm font-bold mb-3 text-gray-400 uppercase tracking-wider flex items-center gap-2">
                                <span>🍽️</span> ${section.title}
                            </h3>
                            <div id="${tableContainerId}"></div>
                        </div>
                    `;
                    // Use setTimeout to ensure the DOM element exists before rendering table
                    setTimeout(() => renderPlaceTable(tableContainerId, section.items), 0);
                } else if (section.type === 'place_list') {
                    let itemsHtml = '';
                    section.items.forEach(item => {
                        itemsHtml += `
                            <div class="bg-white border rounded-xl shadow-sm overflow-hidden mb-3 transition hover:shadow-md cursor-pointer flex flex-col p-4">
                                <div class="flex justify-between items-start">
                                    <h3 class="font-bold text-gray-800 text-sm">${item.name}</h3>
                                    <span class="text-xs bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded border border-yellow-100">⭐ ${item.rating}</span>
                                </div>
                                <p class="text-xs text-gray-500 mt-1">${item.description}</p>
                                ${item.meta ? `<div class="mt-2 text-xs text-gray-500 font-medium bg-gray-50 inline-block px-2 py-1 rounded border border-gray-100">${item.meta}</div>` : ''}
                                <div class="mt-3 flex items-center">
                                     <span class="text-xs font-bold text-blue-600 hover:underline">View Details</span>
                                </div>
                            </div>
                        `;
                    });
                    wrapper.innerHTML += `
                        <div class="mt-4">
                            <h3 class="text-sm font-bold mb-3 text-gray-400 uppercase tracking-wider flex items-center gap-2">
                                <span>🏢</span> RECOMMENDED PLACES
                            </h3>
                            <div class="flex flex-col">${itemsHtml}</div>
                        </div>
                    `;
                } else if (section.type === 'key_value_list') {
                    let rows = '';
                    section.items.forEach(item => {
                        rows += `
                            <div class="flex justify-between py-2 border-b border-dashed border-gray-200 last:border-0 hover:bg-gray-50 px-2 rounded transition">
                                <span class="text-sm text-gray-600">${item.label}</span>
                                <span class="text-sm font-mono font-bold ${item.highlight === false ? 'text-red-500' : 'text-green-600'}">${item.value}</span>
                            </div>
                        `;
                    });
                    wrapper.innerHTML += `
                        <div class="bg-white border rounded-xl p-5 mt-3 shadow-sm">
                            <h3 class="text-sm font-bold mb-3 text-gray-800 flex items-center gap-2">
                                <span>📊</span> ${section.title}
                            </h3>
                            <div class="space-y-1">${rows}</div>
                        </div>
                    `;
                } else if (section.type === 'highlight_box') {
                    wrapper.innerHTML += `
                        <div class="p-4 rounded-xl font-medium text-center text-sm mt-3 flex items-center justify-center gap-2 ${section.variant === 'warning' ? 'bg-amber-50 text-amber-800 border border-amber-100' : 'bg-emerald-50 text-emerald-800 border border-emerald-100'}">
                            <span>${section.variant === 'warning' ? '⚠️' : '✅'}</span>
                            ${section.content}
                        </div>
                    `;
                } else if (section.type === 'text') {
                    // Support markdown-like bolding
                    let content = section.content.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
                    wrapper.innerHTML += `<div class="text-sm text-gray-700 leading-relaxed">${content}</div>`;
                } else if (section.type === 'input_prompt') {
                    // Generate unique ID for this input
                    const inputId = 'input-' + Math.random().toString(36).substr(2, 9);
                    wrapper.innerHTML += `
                        <div class="mt-3">
                            <input type="text" id="${inputId}" placeholder="${section.placeholder}" class="w-full border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 text-sm">
                            ${section.action_label ? `<button onclick="handleFormSubmit('${inputId}')" class="mt-2 w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">${section.action_label}</button>` : ''}
                        </div>
                    `;
                }
            });

            // Suggestions
            if (plan.suggestions && plan.suggestions.length > 0) {
               let btnsHtml = '';
               plan.suggestions.forEach(s => {
                   if (s === 'Save to favorites') {
                       // Special handler for recipe saving
                       btnsHtml += `<button onclick="addToFavorites('recipe', currentRecipe)" class="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full text-xs text-gray-700 border border-gray-200 transition">❤️ Save to favorites</button>`;
                   } else {
                       btnsHtml += `<button onclick="document.getElementById('userInput').value='${s}'; sendMessage()" class="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full text-xs text-gray-700 border border-gray-200 transition">${s}</button>`;
                   }
               });
               wrapper.innerHTML += `
                   <div class="flex flex-wrap gap-2 mt-4 pt-2 border-t border-gray-100">
                       ${btnsHtml}
                   </div>
               `;
            }

            container.appendChild(wrapper);
            
            // Capture recipe data if this is a recipe result
            if (plan.mode === 'recipe') {
                // Extract simple data from plan
                let title = "Healthy Recipe";
                let summary = plan.summary;
                
                // Try to find summary text
                const textSection = plan.sections.find(s => s.type === 'text');
                if (textSection) summary = textSection.content;

                currentRecipe = {
                    title: summary.split('\\n')[0].replace('Here is a healthy recipe for ', '').replace('.', ''),
                    summary: summary,
                    id: Date.now()
                };
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)