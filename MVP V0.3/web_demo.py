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
from langchain_core.messages import HumanMessage, AIMessage

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

# Import Core Agent Logic
from langgraph_app.orchestrator.state import GraphState
from langgraph_app.agents.ui_agent.agent import generate_ui_plan

# Import Mock Data for Fallback/Simulation
try:
    from .mock_data import (
        MOCK_RECOGNITION_RESULT, 
        MOCK_RECOMMENDATION_TABLE_RESULT,
        MOCK_GUARDRAIL_RESULT
    )
except ImportError:
    from langgraph_app.agents.ui_agent.mock_data import (
        MOCK_RECOGNITION_RESULT, 
        MOCK_RECOMMENDATION_TABLE_RESULT,
        MOCK_GUARDRAIL_RESULT
    )

# Set Mock Mode to False to use the Real UI Agent
MOCK_MODE = False
MOCK_STATE = {
    "is_corrected": False,
    "chat_history": [] # Store history in memory for demo
}

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
    print(f"Received request: {_truncate_log(request.message)}")
    
    # Simulate processing delay
    await asyncio.sleep(1.0) 
    
    # Extract text and check for image
    msg_content = request.message
    text_content = ""
    is_image = False
    
    if isinstance(msg_content, str):
        text_content = msg_content
    elif isinstance(msg_content, list):
        for item in msg_content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_content += item.get("text", "")
                elif item.get("type") == "image_url" or "image" in item:
                    is_image = True
    
    # Add User Message to History
    MOCK_STATE["chat_history"].append(HumanMessage(content=text_content))

    # Prepare GraphState
    state = GraphState(
        user_input=text_content + " (Please generate the UI plan in Chinese)", # Force Chinese instruction
        patient_id=request.patient_id,
        has_image=is_image,
        chat_history=MOCK_STATE["chat_history"][-10:] # Pass last 10 messages
    )

    # Simple Intent Simulation for Demo Purposes
    text_lower = text_content.lower()
    
    if is_image or "identify" in text_lower or "what is this" in text_lower:
        # Simulate Recognition Scenario
        state.intent = "recognition"
        state.agent_response = MOCK_RECOGNITION_RESULT["agent_response"]
        state.nutrition_facts = MOCK_RECOGNITION_RESULT["nutrition_facts"]
        state.food_detection_json = MOCK_RECOGNITION_RESULT.get("food_detection_json")
        
    elif "recommend" in text_lower or "restaurant" in text_lower or "hungry" in text_lower or "food" in text_lower or "餐厅" in text_lower:
        # Simulate Recommendation Scenario
        # Added "餐厅" to trigger condition
        state.intent = "recommendation"
        state.agent_response = MOCK_RECOMMENDATION_TABLE_RESULT["agent_response"]
        state.recommended_restaurants = MOCK_RECOMMENDATION_TABLE_RESULT["recommended_restaurants"]
    
    elif "die" in text_lower or "kill" in text_lower or "suicide" in text_lower:
        # Simulate Guardrail Scenario
        state.intent = "guardrail"
        state.agent_response = MOCK_GUARDRAIL_RESULT["agent_response"]
        
        # Inject context from mock data so Adaptive UI Agent knows the resources
        if "ui_plan" in MOCK_GUARDRAIL_RESULT:
            sections = MOCK_GUARDRAIL_RESULT["ui_plan"].get("sections", [])
            for sec in sections:
                if sec["type"] == "key_value_list":
                    items = sec.get("items", [])
                    resource_text = "\n\nAvailable Resources:\n" + "\n".join([f"- {i['label']}: {i['value']}" for i in items])
                    state.agent_response += resource_text
                    break
        # In a real app, safety_passed would be set by the Safety Agent
        
    elif any(k in text_lower for k in ["wrong", "mistake", "incorrect", "error", "错误", "不对", "不准"]):
        # Simulate Correction Scenario
        state.intent = "correction"
        state.agent_response = "I apologize for the error. Could you please correct me? I am always learning."

    else:
        # Generic / Chat / Follow-up
        # If there is history and no clear new intent, it might be a follow-up
        state.intent = "generic"
        
        # Simple heuristic: if previous turn was recognition, carry over context
        if len(MOCK_STATE["chat_history"]) > 2:
             # In a real app, Orchestrator would handle context retrieval
             # Here we simulate carrying over nutrition facts if available
             state.nutrition_facts = MOCK_RECOGNITION_RESULT["nutrition_facts"] # Mock retrieval
             
             # Also carry over restaurant context if the user is asking about sorting/filtering
             # This simulates the Orchestrator remembering the previous "recommendation" state
             if any(k in text_lower for k in ["sort", "price", "dist", "cheap", "expensive", "near", "排序", "价格", "距离", "便宜", "贵"]):
                 state.recommended_restaurants = MOCK_RECOMMENDATION_TABLE_RESULT["recommended_restaurants"]
             
        state.agent_response = "I see. Let me help you with that based on the food we just discussed."

    # --- EXECUTE REAL UI AGENT ---
    try:
        print(f"Invoking UI Agent with Intent: {state.intent}")
        final_state = generate_ui_plan(state)
        
        # Add AI Response to History
        if final_state.ui_plan:
             summary = final_state.ui_plan.get("summary", "Here is the info.")
             MOCK_STATE["chat_history"].append(AIMessage(content=summary))
             return JSONResponse(content={"web_ui_plan": final_state.ui_plan})
        else:
            return JSONResponse(content={"error": "UI Agent returned no plan"})
            
    except Exception as e:
        print(f"Error in UI Agent: {e}")
        return JSONResponse(content={"error": str(e)})

@app.post("/api/reset")
async def reset_state():
    MOCK_STATE["is_corrected"] = False
    MOCK_STATE["chat_history"] = []
    return JSONResponse(content={"status": "success", "message": "State reset"})

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wabi Agent - UI Demo (Adaptive)</title>
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
        .user-message-container { display: flex; justify-content: flex-end; align-items: center; margin-bottom: 10px; animation: fadeIn 0.3s ease; position: relative; }
        
        /* Delete & Favorite Button */
        .msg-actions {
            opacity: 0;
            transition: all 0.2s;
            display: flex;
            gap: 4px;
            margin-right: 8px; /* Space between actions and bubble */
        }
        .message-group:hover .msg-actions { opacity: 1; }
        
        /* Buttons moved to left side of user message (relative to flex container) */
        .user-message .msg-actions { 
             /* Removed absolute positioning to let it sit naturally in flex flow */
        }
        .ai-message .msg-actions { display: none; }

        .action-btn {
            cursor: pointer;
            color: #9ca3af;
            padding: 6px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px; height: 28px;
        }
        .action-btn:hover { color: #2563eb; background-color: #eff6ff; }
        .delete-btn:hover { color: #ef4444; background-color: #fee2e2; }
        
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
        
        /* Highlight Animation */
        @keyframes highlightPulse {
            0% { background-color: rgba(37, 99, 235, 0.1); }
            50% { background-color: rgba(37, 99, 235, 0.3); }
            100% { background-color: transparent; }
        }
        .highlight-msg { animation: highlightPulse 2s ease-out; }
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
                v2.1.0 (Adaptive)<br>Project Wabi-C
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
                        你好！我是 Wabi。我可以帮你识别食物热量或推荐附近的健康餐厅。<br>Hello! I'm Wabi. How can I help you?
                    </div>
                </div>
            </div>

            <!-- Favorites View (Hidden by default) -->
            <div id="favoritesView" class="hidden flex-1 overflow-y-auto p-8">
                <h2 class="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
                    <span>❤️</span> Saved Favorites
                </h2>
                
                <div class="mb-8">
                    <h3 class="text-lg font-semibold text-gray-700 mb-4 border-b pb-2">Conversations (Q&A)</h3>
                    <div id="fav-qa" class="grid grid-cols-1 gap-4">
                        <p class="text-gray-400 text-sm">No saved conversations yet.</p>
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
                    
                    <textarea id="userInput" rows="1" placeholder="输入消息或上传食物图片..." onkeypress="handleKeyPress(event)"></textarea>
                    
                    <button onclick="sendMessage()" class="bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 transition shadow-sm">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </div>
                <div class="text-center text-xs text-gray-400 mt-2">Wabi AI may produce inaccurate information. Please verify.</div>
            </div>
        </div>
    </div>

    <script>
        let currentImageBase64 = null;
        let placeTableData = []; 
        
        let chatState = [
             {
                id: 'welcome-msg',
                role: 'ai',
                content: "你好！我是 Wabi。我可以帮你识别食物热量或推荐附近的健康餐厅。<br>Hello! I'm Wabi. How can I help you?"
            }
        ];

        let favorites = { qa: [] };

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
                setTimeout(() => chatHistory.scrollTop = chatHistory.scrollHeight, 0);
            } else if (viewName === 'favorites') {
                chatHistory.classList.add('hidden');
                favView.classList.remove('hidden');
                inputArea.classList.add('hidden');
                navItems[1].classList.add('active');
                renderFavorites();
            }
        }
        
        function scrollToMessage(msgId) {
            switchView('chat');
            setTimeout(() => {
                const el = document.getElementById(msgId);
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    el.classList.add('highlight-msg');
                    setTimeout(() => el.classList.remove('highlight-msg'), 2000);
                } else {
                    alert('Message not found in current session.');
                }
            }, 100);
        }

        function addToFavorites(type, item) {
            if (type === 'qa') {
                if (!favorites.qa.find(q => q.id === item.id)) {
                    favorites.qa.push(item);
                    alert('Conversation saved!');
                } else {
                    alert('Already saved.');
                }
            }
        }

        function saveQAPair(aiMsgId, userMsgId) {
            const aiMsg = chatState.find(m => m.id === aiMsgId);
            const userMsg = chatState.find(m => m.id === userMsgId);
            
            if (aiMsg && userMsg) {
                const qaItem = {
                    id: aiMsgId,
                    userMsgId: userMsgId,
                    question: userMsg.text || "[Image Upload]",
                    answer: aiMsg.plan ? aiMsg.plan.summary : aiMsg.content,
                    timestamp: new Date().toLocaleString()
                };
                addToFavorites('qa', qaItem);
            }
        }

        function addToFavoritesById(id) {
            // Functionality removed for restaurants
            console.log("Restaurant favorites removed.");
        }

        function removeFromFavorites(type, id) {
            if (type === 'qa') {
                favorites.qa = favorites.qa.filter(q => q.id !== id);
            }
            renderFavorites();
        }

        function renderFavorites() {
            const qaContainer = document.getElementById('fav-qa');

            // QA
            if (favorites.qa.length === 0) {
                qaContainer.innerHTML = '<p class="text-gray-400 text-sm">No saved conversations.</p>';
            } else {
                qaContainer.innerHTML = favorites.qa.map(q => `
                    <div class="bg-white border rounded-xl p-4 shadow-sm hover:shadow-md transition relative cursor-pointer" onclick="scrollToMessage('${q.userMsgId}')">
                        <div class="flex justify-between items-start mb-2">
                            <div class="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded">Q: ${q.question}</div>
                            <button onclick="event.stopPropagation(); removeFromFavorites('qa', '${q.id}')" class="text-gray-300 hover:text-red-500 transition flex-shrink-0 ml-2">×</button>
                        </div>
                        <div class="text-sm text-gray-700 pl-2 border-l-2 border-green-200 mb-2">${q.answer}</div>
                        <div class="flex justify-between items-center mt-2">
                            <span class="text-[10px] text-gray-400">${q.timestamp}</span>
                            <span class="text-xs text-blue-500 font-medium hover:underline">View in Chat →</span>
                        </div>
                    </div>
                `).join('');
            }
        }

        function renderPlaceTable(containerId, data) {
            placeTableData = data;
            const container = document.getElementById(containerId);
            if(!container) return;
            updatePlaceTable(containerId);
        }

        function updatePlaceTable(containerId, sortBy = null, filterVeg = false) {
            const container = document.getElementById(containerId);
            if(!container) return;

            let displayData = [...placeTableData];
            const isVegChecked = document.getElementById(`veg-filter-${containerId}`)?.checked || false;
            if (isVegChecked) displayData = displayData.filter(item => item.is_veg);

            const sortVal = document.getElementById(`sort-select-${containerId}`)?.value || 'default';
            if (sortVal === 'price_asc') displayData.sort((a, b) => a.price - b.price);
            else if (sortVal === 'dist_asc') displayData.sort((a, b) => a.dist - b.dist);

            let controlsHtml = `
                <div class="flex flex-wrap items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <div class="flex items-center gap-2">
                        <span class="text-sm text-gray-600 font-medium">Sort:</span>
                        <select id="sort-select-${containerId}" onchange="updatePlaceTable('${containerId}')" class="text-sm border-gray-300 rounded-md p-1 border">
                            <option value="default" ${sortVal === 'default' ? 'selected' : ''}>Default</option>
                            <option value="price_asc" ${sortVal === 'price_asc' ? 'selected' : ''}>Price: Low to High</option>
                            <option value="dist_asc" ${sortVal === 'dist_asc' ? 'selected' : ''}>Distance: Nearest</option>
                        </select>
                    </div>
                    <div class="flex items-center gap-2">
                        <label class="inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="veg-filter-${containerId}" onchange="updatePlaceTable('${containerId}')" class="rounded border-gray-300 text-blue-600" ${isVegChecked ? 'checked' : ''}>
                            <span class="ml-2 text-sm text-gray-600">Veg Only 🥦</span>
                        </label>
                    </div>
                </div>
            `;

            let tableHtml = `
                <div class="overflow-x-auto border rounded-xl shadow-sm">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rating</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Dist</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
            `;

            if (displayData.length === 0) {
                tableHtml += `<tr><td colspan="4" class="px-4 py-8 text-center text-sm text-gray-500">No results.</td></tr>`;
            } else {
                displayData.forEach(item => {
                    tableHtml += `
                        <tr class="hover:bg-gray-50 transition cursor-pointer">
                            <td class="px-4 py-3 whitespace-nowrap">
                                <div class="text-sm font-medium text-gray-900">${item.name}</div>
                                <div class="text-xs text-gray-500 truncate max-w-[120px]">${item.desc}</div>
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap"><span class="text-yellow-500">★</span> ${item.rating}</td>
                            <td class="px-4 py-3 whitespace-nowrap"><span class="px-2 text-xs rounded-full bg-green-100 text-green-800">${item.price_str}</span></td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">${item.dist_str}</td>
                        </tr>
                    `;
                });
            }
            tableHtml += `</tbody></table></div>`;
            container.innerHTML = controlsHtml + tableHtml;
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
            if (text) await processMessage("Correction: " + text);
        }

        async function resetChat() {
            try { await fetch('/api/reset', { method: 'POST' }); } catch (e) {}
            chatState = [{ id: 'welcome-msg', role: 'ai', content: "你好！我是 Wabi。我可以帮你识别食物热量或推荐附近的健康餐厅。<br>Hello! I'm Wabi. How can I help you?" }];
            renderChatHistory();
            document.getElementById('userInput').value = '';
            clearImage();
        }

        function deleteMessagePair(userMsgId, aiMsgId) {
            chatState = chatState.filter(msg => msg.id !== userMsgId && msg.id !== aiMsgId);
            renderChatHistory();
        }

        function renderChatHistory() {
            const history = document.getElementById('chatHistory');
            history.innerHTML = ''; 

            chatState.forEach(msg => {
                const pairId = msg.role === 'user' ? msg.aiPairId : (chatState.find(m => m.aiPairId === msg.id)?.id);
                const userMsgId = msg.role === 'user' ? msg.id : pairId;
                const aiMsgId = msg.role === 'ai' ? msg.id : (chatState.find(m => m.id === msg.aiPairId)?.id);
                
                if (msg.role === 'user') {
                    const userContainer = document.createElement('div');
                    userContainer.id = msg.id;
                    userContainer.className = 'user-message-container user-message message-group';
                    let displayHtml = '';
                    if (msg.image) displayHtml += `<img src="${msg.image}" class="max-h-48 rounded-lg mb-2 border border-blue-400 block">`;
                    if (msg.text) displayHtml += `<div>${msg.text}</div>`;
                    
                    // Move actions to User side (left of bubble)
                    let actionsHtml = '';
                    if (msg.aiPairId) {
                         actionsHtml = `
                            <div class="msg-actions">
                                <button onclick="saveQAPair('${aiMsgId}', '${userMsgId}')" class="action-btn" title="Save Conversation">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                                </button>
                                <button onclick="deleteMessagePair('${msg.id}', '${msg.aiPairId}')" class="action-btn delete-btn" title="Delete Pair">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                                </button>
                            </div>
                         `;
                    }
                    userContainer.innerHTML = actionsHtml + `<div class="message-bubble">${displayHtml}</div>`;
                    history.appendChild(userContainer);
                } else if (msg.role === 'ai') {
                    const aiContainer = document.createElement('div');
                    aiContainer.id = msg.id;
                    aiContainer.className = 'ai-message-container ai-message message-group';
                    let contentHtml = '';
                    if (msg.isLoading) {
                         contentHtml = `<div class="message-bubble" style="min-width: 200px">Thinking...</div>`;
                    } else if (msg.plan) {
                        contentHtml = `<div class="message-bubble w-full"><div id="content-${msg.id}"></div></div>`;
                    } else if (msg.content) {
                         contentHtml = `<div class="message-bubble">${msg.content}</div>`;
                    }
                    
                    // Removed actions from AI side
                    aiContainer.innerHTML = `<div class="avatar ai">AI</div>${contentHtml}`;
                    history.appendChild(aiContainer);
                    if (msg.plan) {
                        const contentDiv = aiContainer.querySelector(`#content-${msg.id}`);
                        if(contentDiv) renderWebComponents(contentDiv, msg.plan);
                    }
                }
            });
            history.scrollTop = history.scrollHeight;
        }

        async function processMessage(text) {
            if (!text && !currentImageBase64) return;
            const uniqueId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
            const userMsgId = 'msg-' + uniqueId;
            const loadingId = 'loading-' + uniqueId;
            
            chatState.push({ id: userMsgId, role: 'user', text: text, image: currentImageBase64, aiPairId: loadingId });
            chatState.push({ id: loadingId, role: 'ai', isLoading: true, step: 0 });
            renderChatHistory();

            let payload;
            if (currentImageBase64) {
                payload = { message: [{ "type": "image_url", "image_url": {"url": currentImageBase64} }] };
                if (text) payload.message.unshift({"type": "text", "text": text});
            } else {
                payload = { message: text };
            }

            document.getElementById('userInput').value = '';
            clearImage();

            try {
                const response = await fetch('/api/ui', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                
                const aiMsgIndex = chatState.findIndex(m => m.id === loadingId);
                if (aiMsgIndex !== -1) {
                    chatState[aiMsgIndex] = { id: loadingId, role: 'ai', isLoading: false, plan: data.web_ui_plan };
                    renderChatHistory();
                }
            } catch (error) {
                console.error(error);
            }
        }

        function renderWebComponents(container, plan) {
            const wrapper = document.createElement('div');
            wrapper.className = 'space-y-4';

            if (plan.summary) wrapper.innerHTML += `<div class="text-gray-800 mb-3">${plan.summary}</div>`;

            plan.sections.forEach(section => {
                if (section.type === 'carousel') {
                    let itemsHtml = '';
                    section.items.forEach(item => {
                        itemsHtml += `
                            <div class="min-w-[240px] bg-white border rounded-xl shadow-sm overflow-hidden mr-4 flex-shrink-0 transition hover:shadow-md cursor-pointer">
                                <div class="p-4">
                                    <h3 class="font-bold text-gray-800 truncate">${item.title}</h3>
                                    <p class="text-xs text-gray-500 mt-1 line-clamp-2">${item.subtitle}</p>
                                </div>
                            </div>`;
                    });
                    wrapper.innerHTML += `<div class="mt-4"><h3 class="text-sm font-bold mb-3 text-gray-400 uppercase">🍽️ ${section.title}</h3><div class="flex overflow-x-auto pb-4 scrollbar-hide -mx-1 px-1">${itemsHtml}</div></div>`;
                } else if (section.type === 'dynamic_place_table') {
                    const tableContainerId = 'table-' + Math.random().toString(36).substr(2, 9);
                    wrapper.innerHTML += `<div class="mt-4"><h3 class="text-sm font-bold mb-3 text-gray-400 uppercase">🍽️ ${section.title}</h3><div id="${tableContainerId}"></div></div>`;
                    setTimeout(() => renderPlaceTable(tableContainerId, section.items), 0);
                } else if (section.type === 'key_value_list') {
                    let rows = '';
                    section.items.forEach(item => {
                        rows += `<div class="flex justify-between py-2 border-b border-dashed border-gray-200 last:border-0"><span class="text-sm text-gray-600">${item.label}</span><span class="text-sm font-mono font-bold ${item.highlight===false?'text-red-500':'text-green-600'}">${item.value}</span></div>`;
                    });
                    wrapper.innerHTML += `<div class="bg-white border rounded-xl p-5 mt-3 shadow-sm"><h3 class="text-sm font-bold mb-3 text-gray-800">📊 ${section.title}</h3><div class="space-y-1">${rows}</div></div>`;
                } else if (section.type === 'highlight_box') {
                    wrapper.innerHTML += `<div class="p-4 rounded-xl font-medium text-center text-sm mt-3 flex items-center justify-center gap-2 ${section.variant==='warning'?'bg-amber-50 text-amber-800 border border-amber-100':'bg-emerald-50 text-emerald-800 border border-emerald-100'}"><span>${section.variant==='warning'?'⚠️':'✅'}</span>${section.content}</div>`;
                } else if (section.type === 'text') {
                    let content = section.content.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
                    wrapper.innerHTML += `<div class="text-sm text-gray-700 leading-relaxed">${content}</div>`;
                }
            });

            if (plan.suggestions && plan.suggestions.length > 0) {
               let btnsHtml = '';
               plan.suggestions.forEach(s => {
                   btnsHtml += `<button onclick="document.getElementById('userInput').value='${s}'; sendMessage()" class="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full text-xs text-gray-700 border border-gray-200 transition">${s}</button>`;
               });
               wrapper.innerHTML += `<div class="flex flex-wrap gap-2 mt-4 pt-2 border-t border-gray-100">${btnsHtml}</div>`;
            }

            container.appendChild(wrapper);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
