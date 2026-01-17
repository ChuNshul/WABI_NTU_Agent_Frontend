import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pydantic import BaseModel
import asyncio
from typing import Optional, Union, List, Dict, Any

from langchain_core.messages import HumanMessage

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langgraph_app.orchestrator.graph import create_graph_fixed
from langgraph_app.orchestrator.state import GraphState
from langgraph_app.agents.ui_agent.whatsapp_adapter import convert_web_to_whatsapp

app = FastAPI()

# Compile graph once
graph = create_graph_fixed()

class ChatRequest(BaseModel):
    message: Union[str, List[Dict[str, Any]]]
    patient_id: str = "demo_user"

@app.post("/api/ui")
async def get_ui_response(request: ChatRequest):
    print(f"Received request: {request.message}")
    
    # Initialize state with manual history to ensure guardrails work
    # Handle complex input (image) correctly for history
    msg_content = request.message
    
    # Adapter: Preprocess OpenAI image_url format to be compatible with food_recognition agent
    # The agent expects a simple 'image' field or specific dictionary structure
    if isinstance(msg_content, list):
        for item in msg_content:
            if isinstance(item, dict) and item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url:
                    # Adapt to legacy agent format (list iteration checks for source_type='base64')
                    item["source_type"] = "base64"
                    item["mime_type"] = "image/jpeg" # Default to jpeg for detection
                    item["data"] = url
                    print("Adapted image_url to legacy agent format (base64/data)")
    
    initial_state = GraphState(
        user_input=msg_content,
        patient_id=request.patient_id,
        chat_history=[HumanMessage(content=msg_content)] 
    )
    
    # Run graph
    try:
        final_state = await asyncio.to_thread(graph.invoke, initial_state)
        
        # Extract UI Plan (Web Version - Primary)
        # Handle both dict (LangGraph standard output) and object (GraphState instance)
        if isinstance(final_state, dict):
            web_ui_plan = final_state.get("ui_plan")
            agent_response = final_state.get("agent_response", "No response")
        else:
            web_ui_plan = getattr(final_state, "ui_plan", None)
            agent_response = getattr(final_state, "agent_response", "No response")
        
        if not web_ui_plan:
            # Fallback if something went wrong
            web_ui_plan = {
                "mode": "error",
                "sections": [{"type": "text", "content": agent_response}]
            }
            
        # Convert to WhatsApp (Adapter Pattern)
        whatsapp_payload = convert_web_to_whatsapp(web_ui_plan)
            
        return JSONResponse({
            "response": agent_response,
            "web_ui_plan": web_ui_plan,
            "whatsapp_payload": whatsapp_payload,
            "debug_state": str(final_state)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WABI Adaptive UI Demo</title>
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
        .ai-message-container { display: flex; gap: 16px; max-width: 85%; animation: fadeIn 0.3s ease; }
        .user-message-container { display: flex; justify-content: flex-end; margin-bottom: 10px; animation: fadeIn 0.3s ease; }
        
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
            
            <div class="nav-item active">
                <span>💬</span> Chat Interface
            </div>
            <div class="nav-item">
                <span>📊</span> Dashboard
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
                <div class="status-badge">● Online</div>
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

            <div class="input-wrapper">
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
            
            if (!text && !currentImageBase64) return;
            
            // 1. Display User Message
            const history = document.getElementById('chatHistory');
            const userContainer = document.createElement('div');
            userContainer.className = 'user-message-container user-message';
            
            let displayHtml = '';
            if (currentImageBase64) {
                displayHtml += `<img src="${currentImageBase64}" class="max-h-48 rounded-lg mb-2 border border-blue-400 block">`;
            }
            if (text) {
                displayHtml += `<div>${text}</div>`;
            }
            
            userContainer.innerHTML = `<div class="message-bubble">${displayHtml}</div>`;
            history.appendChild(userContainer);
            history.scrollTop = history.scrollHeight;

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
            input.value = '';
            clearImage();

            // 2. Show Progress Placeholder
            const loadingId = 'loading-' + Date.now();
            const loadingContainer = document.createElement('div');
            loadingContainer.className = 'ai-message-container ai-message';
            loadingContainer.id = loadingId;
            loadingContainer.innerHTML = `
                <div class="avatar ai">AI</div>
                <div class="message-bubble" style="min-width: 200px">
                    <div class="font-medium mb-2">Processing Request...</div>
                    <div class="process-steps">
                        <div class="step-item active" id="step-1-${loadingId}">
                            <div class="step-icon"></div>
                            <span>Analyzing Intent...</span>
                        </div>
                        <div class="step-item" id="step-2-${loadingId}">
                            <div class="step-icon"></div>
                            <span>Running Agents...</span>
                        </div>
                        <div class="step-item" id="step-3-${loadingId}">
                            <div class="step-icon"></div>
                            <span>Generating UI...</span>
                        </div>
                    </div>
                </div>
            `;
            history.appendChild(loadingContainer);
            history.scrollTop = history.scrollHeight;

            // Simulate Steps (Fake progress for better UX, since backend is one-shot)
            // Ideally we'd use SSE/WebSockets for real progress
            const simulateProgress = async () => {
                await new Promise(r => setTimeout(r, 800));
                document.querySelector(`#step-1-${loadingId}`).className = 'step-item done';
                document.querySelector(`#step-2-${loadingId}`).className = 'step-item active';
                
                await new Promise(r => setTimeout(r, 1200));
                document.querySelector(`#step-2-${loadingId}`).className = 'step-item done';
                document.querySelector(`#step-3-${loadingId}`).className = 'step-item active';
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

                // Wait for animation to finish minimal steps
                await progressPromise;
                
                // Replace Loading with Real Content
                const finalContainer = document.getElementById(loadingId);
                finalContainer.innerHTML = `
                    <div class="avatar ai">AI</div>
                    <div class="message-bubble w-full">
                        <div id="content-${loadingId}"></div>
                        <div class="process-steps mt-4">
                             <div class="step-item done"><div class="step-icon"></div><span>Request Processed (${data.web_ui_plan ? 'UI Generated' : 'Text Only'})</span></div>
                        </div>
                    </div>
                `;
                
                renderWebComponents(finalContainer.querySelector(`#content-${loadingId}`), data.web_ui_plan);
                history.scrollTop = history.scrollHeight;

            } catch (error) {
                console.error(error);
                document.getElementById(loadingId).querySelector('.message-bubble').innerHTML = `<div class="text-red-500">Error: ${error.message}</div>`;
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
                    wrapper.innerHTML += `<div class="text-sm text-gray-700 leading-relaxed">${section.content}</div>`;
                }
            });

            container.appendChild(wrapper);
        }
    </script>
</body>
</html>

    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
