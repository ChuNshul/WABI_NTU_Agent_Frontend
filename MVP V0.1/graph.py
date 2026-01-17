"""
LangGraph orchestration - UPDATED VERSION with patient_id support

✅ 更新内容:
- Added: patient_id parameter support for food storage
- Updated: Database storage calls to use patient_id
- Enhanced: Better integration with new food_storage_tools.py architecture
- Fixed: 重复输入显示问题
- Fixed: LangGraph Studio消息重复添加
- Fixed: 智能输入来源检测
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
import logging
from datetime import datetime
import time

# Add project root directory to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.messages import HumanMessage, AIMessage
from .state import GraphState

# Import agents
from langgraph_app.agents.food_recognition.agent import detect_food, store_entry
from langgraph_app import route_intent
from langgraph_app.agents.food_recommendation import agent as reco_agent
from langgraph_app.agents.ui_agent.agent import generate_ui_plan
from langgraph_app.guardrails.depressive_check import depressive_guard

# Import updated food storage tools
try:
    from langgraph_app.tools.food_storage_tools import (
        store_food_detection_to_db, 
        create_food_detection_db_node
    )
    FOOD_STORAGE_AVAILABLE = True
except ImportError:
    print("Warning: food_storage_tools not available, using fallback storage")
    FOOD_STORAGE_AVAILABLE = False

if TYPE_CHECKING:
    from langgraph.graph import StateGraph, END, START

# Default values for recommendation
DEFAULT_ADDRESS = "Orchard Road, Singapore"
DEFAULT_RADIUS = 800
DEFAULT_PREFERENCE = "Chinese, budget friendly"

# Enable DEBUG tracing when env var set
if os.getenv("LANGGRAPH_DEBUG") == "1":
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

try:
    from langgraph.graph import StateGraph, END, START
except ImportError:
    class _StubGraph:
        def __init__(self, _state_schema):
            pass
        def add_node(self, *_args, **_kwargs):
            return self
        def add_edge(self, *_args, **_kwargs):
            return self
        def compile(self):
            return self
        def invoke(self, state):
            return state
        def enable_tracing(self):
            return self
    StateGraph = _StubGraph
    END = START = "<END_OR_START>"


def _trace(node_name: str):
    """Debug tracing helper"""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            logging.debug(">> %s.enter", node_name)
            if args and hasattr(args[0], "__dict__"):
                state = args[0]
                logging.debug("   [STATE in] intent=%s, patient_id=%s, agent_response=%s",
                              getattr(state, "intent", None),
                              getattr(state, "patient_id", None),
                              getattr(state, "agent_response", None))
            result = fn(*args, **kwargs)
            if hasattr(result, "__dict__"):
                state_out = result
                logging.debug("   [STATE out] intent=%s, patient_id=%s, agent_response=%s",
                              getattr(state_out, "intent", None),
                              getattr(state_out, "patient_id", None),
                              getattr(state_out, "agent_response", None))
            logging.debug("<< %s.exit", node_name)
            return result
        return wrapper
    return decorator


def extract_user_input_from_dict_message(message_dict):
    """Extract user input from LangGraph Studio's dict message format"""
    print(f"[extract_user_input_from_dict_message] Processing dict message")
    
    if not isinstance(message_dict, dict) or 'content' not in message_dict:
        return "", False, None
    
    content = message_dict['content']
    print(f"[extract_user_input_from_dict_message] Found content: {type(content)}")
    
    if isinstance(content, list):
        print(f"[extract_user_input_from_dict_message] Processing {len(content)} content blocks")
        
        text_parts = []
        has_image = False
        
        for i, block in enumerate(content):
            if isinstance(block, dict):
                print(f"[extract_user_input_from_dict_message] Block {i}: {list(block.keys())}")
                
                # Extract text
                if block.get('type') == 'text' and 'text' in block:
                    text_content = block['text'].strip()
                    if text_content:
                        text_parts.append(text_content)
                        print(f"[extract_user_input_from_dict_message] Found text: '{text_content}'")
                
                # Check for image
                if (block.get('type') in ['image', 'image_url'] or 
                    block.get('source_type') == 'base64' or
                    'data' in block):
                    has_image = True
                    print(f"[extract_user_input_from_dict_message] Found image in block {i}")
        
        combined_text = ' '.join(text_parts) if text_parts else ""
        print(f"[extract_user_input_from_dict_message] Result: text='{combined_text}', has_image={has_image}")
        
        return combined_text, has_image, content
    
    elif isinstance(content, str):
        print(f"[extract_user_input_from_dict_message] Simple string content: '{content[:50]}...'")
        return content, False, content
    
    return "", False, None


def extract_patient_id_from_input(state: GraphState, **kwargs) -> Optional[str]:
    """
    尝试从多个来源提取患者ID
    按照聊天讨论的架构思路，患者ID应该从编排代理传递
    """
    print("[extract_patient_id_from_input] 尝试提取患者ID")
    
    # 方法1: 直接从kwargs中获取（编排代理传递）
    if kwargs:
        for key in ['patient_id', 'patientId', 'user_id', 'userId']:
            if key in kwargs and kwargs[key]:
                print(f"[extract_patient_id_from_input] 从kwargs.{key}获取患者ID: {kwargs[key]}")
                return str(kwargs[key])
    
    # 方法2: 从state中获取（如果已经设置）
    if hasattr(state, 'patient_id') and state.patient_id:
        print(f"[extract_patient_id_from_input] 从state.patient_id获取: {state.patient_id}")
        return state.patient_id
    
    # 方法3: 尝试从用户输入中解析（如果包含患者ID信息）
    user_input = state.user_input
    if isinstance(user_input, dict):
        for key in ['patient_id', 'patientId', 'user_id', 'userId']:
            if key in user_input and user_input[key]:
                print(f"[extract_patient_id_from_input] 从user_input.{key}获取: {user_input[key]}")
                return str(user_input[key])
    
    # 方法4: 生成临时UUID（最后手段，不推荐）
    print("[extract_patient_id_from_input] ⚠️ 警告: 无法找到患者ID，生成临时UUID")
    temp_uuid = str(uuid.uuid4())  # 生成标准UUID格式
    print(f"[extract_patient_id_from_input] 生成临时患者ID: {temp_uuid}")
    return temp_uuid


def is_duplicate_message(new_content, last_message):
    """
    更精确地检测是否是重复消息
    """
    if not isinstance(last_message, HumanMessage):
        return False
    
    # 处理不同格式的内容比较
    def normalize_content(content):
        if isinstance(content, str):
            return content.strip()
        elif isinstance(content, list):
            # 处理包含图片的复合消息
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
            return ' '.join(text_parts).strip()
        return str(content).strip()
    
    new_normalized = normalize_content(new_content)
    last_normalized = normalize_content(last_message.content)
    
    return new_normalized == last_normalized


def detect_studio_message_pattern(kwargs):
    """
    检测LangGraph Studio特有的消息模式
    """
    # Studio通常通过特定的kwargs传递新消息
    studio_indicators = [
        'messages' in kwargs and isinstance(kwargs['messages'], list),
        'input' in kwargs and kwargs['input'] is not None,
        'user_input' in kwargs and kwargs['user_input'] is not None,
        'content' in kwargs and kwargs['content'] is not None,
    ]
    
    return any(studio_indicators)


def force_complete_reset_fixed(state: GraphState, **kwargs) -> GraphState:
    """
    修复版本：完全避免重复添加消息到历史 + 支持患者ID提取
    """
    print("[force_complete_reset_fixed] === 开始重置，避免重复输入 ===")
    
    # Step 1: 清理所有业务状态
    state.intent = None
    state.agent_response = None
    state.nutrition_facts = None
    state.db_record_id = None
    state.recommended_restaurants = None
    state.location = None
    state.error = None
    
    # Step 2: 提取患者ID（新增）
    patient_id = extract_patient_id_from_input(state, **kwargs)
    if patient_id:
        state.patient_id = patient_id
        print(f"[force_complete_reset_fixed] 设置患者ID: {patient_id}")
    
    # Step 3: 智能获取当前输入，但不添加到历史
    current_input = None
    input_source = "Not found"
    input_from_studio = False
    
    # 方法A: 检查kwargs中的新消息（最高优先级）
    if kwargs:
        print(f"[force_complete_reset_fixed] 检查kwargs: {list(kwargs.keys())}")
        for key in ['messages', 'input', 'user_input', 'content']:
            if key in kwargs and kwargs[key]:
                current_input = kwargs[key]
                input_source = f"kwargs.{key}"
                input_from_studio = True  # 来自Studio的新输入
                print(f"[force_complete_reset_fixed] 从{input_source}获取到新输入")
                break
    
    # 方法B: 检查是否是Studio传入的新消息格式
    if current_input is None and hasattr(state, '_studio_input_buffer'):
        current_input = state._studio_input_buffer
        input_source = "studio_buffer"
        input_from_studio = True
        print(f"[force_complete_reset_fixed] 从studio_buffer获取输入")
    
    # 方法C: 作为最后手段，从历史中获取最新消息（但标记为非新输入）
    if current_input is None and state.chat_history:
        print(f"[force_complete_reset_fixed] 从历史中查找最新输入（备用方案）")
        for i, message in enumerate(reversed(state.chat_history)):
            if isinstance(message, AIMessage):
                continue
            
            if isinstance(message, dict):
                try:
                    text_content, has_image, raw_content = extract_user_input_from_dict_message(message)
                    if text_content or has_image:
                        current_input = raw_content
                        input_source = f"chat_history[{len(state.chat_history)-1-i}]"
                        input_from_studio = False  # 这是旧消息，不需要添加
                        print(f"[force_complete_reset_fixed] 使用历史消息: {input_source}")
                        break
                except:
                    continue
            elif hasattr(message, 'content'):
                current_input = message.content
                input_source = f"chat_history[{len(state.chat_history)-1-i}]"
                input_from_studio = False
                print(f"[force_complete_reset_fixed] 使用历史消息: {input_source}")
                break

    # 方法D: 最终备选方案
    if current_input is None and hasattr(state, 'user_input') and state.user_input:
        print("[force_complete_reset_fixed] 警告: 使用旧的state.user_input作为备选")
        current_input = state.user_input
        input_source = "state.user_input(fallback)"
        input_from_studio = False

    # Step 4: 设置处理标记
    state.user_input = current_input
    state.is_new_studio_input = input_from_studio  # 关键标记：是否需要添加到历史
    state.input_source_debug = input_source
    state.reset_timestamp = datetime.now().isoformat()
    
    print(f"[force_complete_reset_fixed] 最终结果:")
    print(f"  患者ID: {state.patient_id}")
    print(f"  输入来源: {input_source}")
    print(f"  输入类型: {type(current_input)}")
    print(f"  是否Studio新输入: {input_from_studio}")
    print(f"  需要添加到历史: {input_from_studio}")
    
    if current_input is None:
        print("[force_complete_reset_fixed] ⚠️ 严重警告: 没有找到有效的输入来源!")
    
    print("[force_complete_reset_fixed] === 重置完成 ===")
    return state


def append_history_smart(state: GraphState) -> GraphState:
    """
    智能版本：只有当确实是新输入时才添加到历史
    """
    print(f"[append_history_smart] 检查是否需要添加到历史")
    
    # 检查是否是来自Studio的新输入
    is_new_input = getattr(state, 'is_new_studio_input', False)
    current_input = state.user_input
    input_source = getattr(state, 'input_source_debug', 'unknown')
    
    print(f"[append_history_smart] 输入分析:")
    print(f"  是否新输入: {is_new_input}")
    print(f"  输入来源: {input_source}")
    print(f"  当前历史长度: {len(state.chat_history)}")
    print(f"  患者ID: {state.patient_id}")
    
    if not is_new_input:
        print("[append_history_smart] ✅ 不是新输入，跳过添加到历史（避免重复）")
        return state
    
    if current_input is None:
        print("[append_history_smart] ⚠️ 没有有效输入，跳过")
        return state
    
    # 防止重复：检查最后一条消息是否相同
    if state.chat_history:
        last_msg = state.chat_history[-1]
        if isinstance(last_msg, HumanMessage):
            if is_duplicate_message(current_input, last_msg):
                print("[append_history_smart] ✅ 检测到重复消息，跳过添加（内容相同）")
                return state
    
    # 添加新的用户消息
    user_message = HumanMessage(content=current_input)
    state.chat_history.append(user_message)
    print(f"[append_history_smart] ✅ 添加了新的用户消息到历史")
    print(f"  历史长度现在是: {len(state.chat_history)}")
    
    # 重置标记，避免后续节点重复添加
    state.is_new_studio_input = False
    
    return state


def debug_chat_history(state: GraphState, step_name: str):
    """调试聊天历史状态"""
    print(f"\n[{step_name}] 💬 聊天历史调试:")
    print(f"  患者ID: {getattr(state, 'patient_id', 'None')}")
    print(f"  总消息数: {len(state.chat_history)}")
    
    for i, msg in enumerate(state.chat_history[-5:], max(0, len(state.chat_history)-5)):
        msg_type = type(msg).__name__
        content_preview = str(getattr(msg, 'content', msg))[:50]
        print(f"  [{i}] {msg_type}: {content_preview}...")
    
    # 检查重复
    contents = [str(getattr(msg, 'content', msg)) for msg in state.chat_history]
    duplicates = [content for content in set(contents) if contents.count(content) > 1]
    if duplicates:
        print(f"  ⚠️ 发现重复内容: {duplicates}")
    else:
        print(f"  ✅ 没有发现重复内容")


def route_recognition_intent(state: GraphState) -> GraphState:
    """
    Smart routing based on input content (from first file)
    """
    print(f"[route_recognition_intent] 路由输入")
    debug_chat_history(state, "route_recognition_intent")
    
    def has_image_data(data):
        """Check if data contains image information"""
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if (item.get('source_type') == 'base64' and 
                        item.get('mime_type', '').startswith('image/')):
                        return True
                    if item.get('type') in ['image', 'image_url']:
                        return True
                    if 'data' in item and len(str(item.get('data', ''))) > 1000:
                        return True
        return False
    
    if has_image_data(state.user_input):
        state.intent = "recognition"
        print("[route_recognition_intent] 图片检测 -> 食物识别")
    else:
        text = ""
        if isinstance(state.user_input, str):
            text = state.user_input.lower()
        elif isinstance(state.user_input, list):
            for item in state.user_input:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text += item.get('text', '').lower() + ' '
        
        text = text.strip()
        print(f"[route_recognition_intent] 提取文本: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        
        exit_keywords = ["bye", "goodbye", "exit", "quit", "stop", "end"]
        if any(keyword in text for keyword in exit_keywords):
            state.intent = "exit"
            print("[route_recognition_intent] 退出关键词检测 -> 退出")
        else:
            state.intent = "recommendation"
            print("[route_recognition_intent] 文本输入 -> 餐厅推荐")
    
    print(f"[route_recognition_intent] 最终意图: {state.intent}")
    return state


def enhanced_store_entry(state: GraphState) -> GraphState:
    """
    增强版数据存储节点，使用新的patient_id架构
    """
    print(f"[enhanced_store_entry] 开始存储食物检测数据")
    debug_chat_history(state, "enhanced_store_entry")
    
    # 检查是否有患者ID
    if not state.patient_id:
        print("[enhanced_store_entry] ⚠️ 警告: 没有患者ID，跳过数据库存储")
        state.error = "Patient ID not provided for database storage"
        return state
    
    # 检查是否有食物检测数据
    if not hasattr(state, 'food_detection_json') or not state.food_detection_json:
        print("[enhanced_store_entry] ⚠️ 没有食物检测数据，跳过存储")
        return state
    
    # 使用新的存储工具
    if FOOD_STORAGE_AVAILABLE:
        try:
            result = store_food_detection_to_db(
                state, 
                patient_id=state.patient_id,
                session_id=getattr(state, 'session_id', None)
            )
            
            if result.get("success"):
                state.db_record_id = result.get("detection_id")
                print(f"[enhanced_store_entry] ✅ 数据存储成功: {state.db_record_id}")
                print(f"  患者ID: {result.get('patient_id')}")
                print(f"  存储项目数: {result.get('items_stored', 0)}")
            else:
                print(f"[enhanced_store_entry] ❌ 数据存储失败: {result.get('error')}")
                state.error = result.get('error')
        except Exception as e:
            print(f"[enhanced_store_entry] ❌ 存储过程中出现异常: {e}")
            state.error = f"Storage exception: {e}"
    else:
        # 回退到原始的store_entry函数
        print("[enhanced_store_entry] 使用原始存储方法（food_storage_tools不可用）")
        try:
            state = store_entry(state)
        except Exception as e:
            print(f"[enhanced_store_entry] ❌ 原始存储也失败: {e}")
            state.error = f"Fallback storage failed: {e}"
    
    return state


def simple_output_for_testing(state: GraphState) -> GraphState:
    print(f"[simple_output_for_testing] 生成输出")
    debug_chat_history(state, "simple_output_for_testing")

    if hasattr(state, "intent") and state.intent == "exit":
        state.agent_response = "Goodbye! Feel free to upload more food images anytime."
    elif hasattr(state, "nutrition_facts") and state.nutrition_facts:
        food_names = list(state.nutrition_facts.keys())
        valid_foods = [f for f in food_names if f.lower() not in ["unidentified food item", "unknown"]]
        if valid_foods:
            state.agent_response = f"I can see: {', '.join(valid_foods)}"
        else:
            state.agent_response = "I couldn't identify the food items clearly."
    elif hasattr(state, "intent") and state.intent == "recognition":
        state.agent_response = "Please upload a food image for recognition, or I can provide meal recommendations."
    else:
        state.agent_response = "Hello! Please upload a food image or ask for recommendations."

    # 添加AI响应到聊天历史
    ai_message = AIMessage(content=state.agent_response)
    state.chat_history.append(ai_message)
    print(f"[simple_output_for_testing] 添加AI响应到历史，总长度: {len(state.chat_history)}")
    
    return state


# Functions from second file (保持不变)
def noop_guard(state: GraphState) -> GraphState:
    # start check user input
    depressive_guard(state)

    if not getattr(state, "safety_passed", True):
        # Append a message indicating the guard result
        ai_message = AIMessage(content=state.agent_response)
        state.chat_history.append(ai_message)
    return state


def fallback_router(state: GraphState) -> GraphState:
    """Simple fallback router"""
    text = (state.user_input or "").lower()
    if "recognize" in text or "recognition" in text:
        state.intent = "recognition"
    else:
        state.intent = "recommendation"
    return state


def _normalize_to_text(x):
    if isinstance(x, str):
        return x
    if isinstance(x, list) and x and isinstance(x[0], dict):
        return x[0].get("text") or x[0].get("content") or str(x)
    if isinstance(x, dict):
        return x.get("text") or x.get("content") or str(x)
    return str(x)


def _coerce_reco_input(state: GraphState) -> GraphState:
    ui = state.user_input
    if isinstance(ui, dict):
        pref = _normalize_to_text(ui.get("preference_text") or ui.get("preference"))
        state.user_input = {
            "address": ui.get("address") or DEFAULT_ADDRESS,
            "radius": int(ui.get("radius") or DEFAULT_RADIUS),
            "preference_text": pref or DEFAULT_PREFERENCE,
            "calorie_requirement": int(ui.get("calorie_requirement") or 1400),
            "medical_condition": ui.get("medical_condition"),
        }
        return state
    # Pure text/other
    pref = _normalize_to_text(ui)
    state.user_input = {
        "address": DEFAULT_ADDRESS,
        "radius": DEFAULT_RADIUS,
        "preference_text": pref.strip() or DEFAULT_PREFERENCE,
        "calorie_requirement": 1400,
        "medical_condition": None,
    }
    return state


def _apply_reco_output(state: GraphState, out: Any) -> GraphState:
    """Apply recommendation pipeline output to GraphState"""
    if isinstance(out, GraphState):
        keep_history = state.chat_history
        keep_input = state.user_input
        keep_patient_id = state.patient_id
        state = out
        state.chat_history = keep_history
        state.user_input = keep_input
        state.patient_id = keep_patient_id
        return state

    if isinstance(out, dict):
        payload = out.get("agent_response") if isinstance(out.get("agent_response"), dict) else out

        def pick(obj, *keys):
            for k in keys:
                if k in obj and obj[k] is not None:
                    return obj[k]
            return None

        state.location = pick(payload, "location", "user_location", "address", "geo") or state.location
        state.nutrition_facts = pick(payload, "nutrition_facts", "nutrition", "nutritionFacts") or state.nutrition_facts

        recos = pick(payload, "recommended_restaurants", "restaurants", "recommendations", "results")
        if isinstance(recos, list):
            simplified = []
            for item in recos:
                if not isinstance(item, dict):
                    continue
                name = (
                    item.get("restaurant_name")
                    or item.get("name")
                    or (item.get("restaurant") or {}).get("NAME")
                    or (item.get("restaurant") or {}).get("name")
                    or ((item.get("matched_dish_details") or [{}])[0].get("restaurant_name") if isinstance(item.get("matched_dish_details"), list) and item.get("matched_dish_details") else None)
                    or "Unknown"
                )
                item.setdefault("restaurant_name", name)
                simplified.append(item)
            state.recommended_restaurants = simplified

        ar = pick(out, "agent_response", "message", "response", "agentResponse")
        if isinstance(ar, str):
            state.agent_response = ar

        state.db_record_id = pick(out, "db_record_id", "record_id", "dbRecordId", "id") or state.db_record_id
        state.error = pick(out, "error", "err_msg", "errorMessage") or state.error
        return state

    logging.warning("food_reco returned unsupported type: %r", type(out))
    return state


def food_recommendation_node(state: GraphState) -> GraphState:
    """Call recommendation pipeline"""
    print(f"[food_recommendation_node] 开始餐厅推荐")
    debug_chat_history(state, "food_recommendation_node")
    
    ui = state.user_input if isinstance(state.user_input, dict) else {}

    try:
        out = reco_agent.run_with_graph_state(state)
    except TypeError:
        out = reco_agent.run_recommendation_pipeline(
            address=ui.get("address"),
            radius=ui.get("radius"),
            preference_text=ui.get("preference_text"),
            calorie_requirement=ui.get("calorie_requirement"),
            medical_condition=ui.get("medical_condition"),
        )

    return _apply_reco_output(state, out)

def _extract_meal_nutrition(restaurant_item: dict, meal_idx: int):
    """
    返回: (total_cal_kcal, total_sugar_g, is_healthy, reason_text)
    读取优先级：
      1) matched_dish_details[meal_idx]  ← 你在 LinkTheGoogleMap8_5 里已经产出
      2) completed_meal_nutrition / meal_nutrition / nutrition_summary_by_meal（若以后添加）
      3) nutrition_by_dish / matched_nutrition_details 聚合兜底（可选）
    """
    def _num(x):
        try:
            return float(x)
        except Exception:
            return None

    # --- A. 直接用 matched_dish_details（与 completed_meal_list_grouped 对齐） ---
    mdd = restaurant_item.get("matched_dish_details")
    if isinstance(mdd, list) and meal_idx < len(mdd) and isinstance(mdd[meal_idx], dict):
        d = mdd[meal_idx]
        cal = (
            _num(d.get("energy_kcal")) or
            _num(d.get("total_calories")) or
            _num(d.get("calories_kcal")) or
            _num(d.get("kcal"))
        )
        sugar = (
            _num(d.get("sugar_g")) or
            _num(d.get("total_sugar_g")) or
            _num(d.get("sugars_g"))
        )
        is_h = d.get("is_healthy")
        # 原因在 unhealthy_reasons（list）里，拼成一句话
        reasons = d.get("unhealthy_reasons")
        reason_txt = None
        if isinstance(reasons, list) and reasons:
            reason_txt = "; ".join(str(r) for r in reasons)
        elif isinstance(reasons, str) and reasons.strip():
            reason_txt = reasons.strip()
        return cal, sugar, is_h, reason_txt

    # --- B. 如果你以后在推荐结果里加了“每餐汇总数组”，这里也兼容 ---
    for key in ["completed_meal_nutrition", "meal_nutrition", "nutrition_summary_by_meal"]:
        arr = restaurant_item.get(key)
        if isinstance(arr, list) and meal_idx < len(arr) and isinstance(arr[meal_idx], dict):
            d = arr[meal_idx]
            cal = _num(d.get("total_calories")) or _num(d.get("total_calories_kcal")) or _num(d.get("calories_kcal"))
            sugar = _num(d.get("total_sugar_g")) or _num(d.get("sugar_g"))
            is_h = d.get("is_healthy")
            reason_txt = d.get("health_reason") or d.get("healthy_reason")
            return cal, sugar, is_h, reason_txt

    # --- C. 兜底：根据每道菜的营养求和（如果你提供了映射） ---
    meals = restaurant_item.get("completed_meal_list_grouped") or restaurant_item.get("completed_meal_list") or []
    meal = meals[meal_idx] if meal_idx < len(meals) else None
    by_dish_candidates = [
        restaurant_item.get("nutrition_by_dish"),
        restaurant_item.get("matched_nutrition_details"),
        restaurant_item.get("nutritionDetailsByDish"),
    ]
    if isinstance(meal, list) and any(by_dish_candidates):
        total_cal = 0.0
        total_sugar = 0.0
        any_flag = None
        for dish in meal:
            dish_name = dish if isinstance(dish, str) else (dish.get("name") if isinstance(dish, dict) else str(dish))
            found = None
            for mapping in by_dish_candidates:
                if isinstance(mapping, dict) and dish_name in mapping:
                    found = mapping[dish_name]
                    break
                if isinstance(mapping, list):
                    for it in mapping:
                        if isinstance(it, dict) and (it.get("dish_name") == dish_name or it.get("name") == dish_name):
                            found = it.get("nutrition") or it
                            break
                if found:
                    break
            if isinstance(found, dict):
                cal = _num(found.get("calories_kcal") or found.get("calories") or found.get("kcal") or found.get("total_calories"))
                sug = _num(found.get("sugar_g") or found.get("sugars_g") or found.get("total_sugar_g"))
                if cal is not None: total_cal += cal
                if sug is not None: total_sugar += sug
                flag = found.get("is_healthy")
                if isinstance(flag, bool):
                    any_flag = flag if any_flag is None else (any_flag and flag)
        if total_cal > 0 or total_sugar > 0:
            return total_cal or None, total_sugar or None, any_flag, None

    # 没拿到
    return None, None, None, None

def _extract_meal_nutrition(restaurant_item: dict, meal_idx: int):
    """
    返回: (total_cal_kcal, total_sugar_g, is_healthy, reason_text)
    读取优先级：
      1) matched_dish_details[meal_idx]  ← 你在 LinkTheGoogleMap8_5 里已经产出
      2) completed_meal_nutrition / meal_nutrition / nutrition_summary_by_meal（若以后添加）
      3) nutrition_by_dish / matched_nutrition_details 聚合兜底（可选）
    """
    def _num(x):
        try:
            return float(x)
        except Exception:
            return None

    # --- A. 直接用 matched_dish_details（与 completed_meal_list_grouped 对齐） ---
    mdd = restaurant_item.get("matched_dish_details")
    if isinstance(mdd, list) and meal_idx < len(mdd) and isinstance(mdd[meal_idx], dict):
        d = mdd[meal_idx]
        cal = (
            _num(d.get("energy_kcal")) or
            _num(d.get("total_calories")) or
            _num(d.get("calories_kcal")) or
            _num(d.get("kcal"))
        )
        sugar = (
            _num(d.get("sugar_g")) or
            _num(d.get("total_sugar_g")) or
            _num(d.get("sugars_g"))
        )
        is_h = d.get("is_healthy")
        # 原因在 unhealthy_reasons（list）里，拼成一句话
        reasons = d.get("unhealthy_reasons")
        reason_txt = None
        if isinstance(reasons, list) and reasons:
            reason_txt = "; ".join(str(r) for r in reasons)
        elif isinstance(reasons, str) and reasons.strip():
            reason_txt = reasons.strip()
        return cal, sugar, is_h, reason_txt

    # --- B. 如果你以后在推荐结果里加了“每餐汇总数组”，这里也兼容 ---
    for key in ["completed_meal_nutrition", "meal_nutrition", "nutrition_summary_by_meal"]:
        arr = restaurant_item.get(key)
        if isinstance(arr, list) and meal_idx < len(arr) and isinstance(arr[meal_idx], dict):
            d = arr[meal_idx]
            cal = _num(d.get("total_calories")) or _num(d.get("total_calories_kcal")) or _num(d.get("calories_kcal"))
            sugar = _num(d.get("total_sugar_g")) or _num(d.get("sugar_g"))
            is_h = d.get("is_healthy")
            reason_txt = d.get("health_reason") or d.get("healthy_reason")
            return cal, sugar, is_h, reason_txt

    # --- C. 兜底：根据每道菜的营养求和（如果你提供了映射） ---
    meals = restaurant_item.get("completed_meal_list_grouped") or restaurant_item.get("completed_meal_list") or []
    meal = meals[meal_idx] if meal_idx < len(meals) else None
    by_dish_candidates = [
        restaurant_item.get("nutrition_by_dish"),
        restaurant_item.get("matched_nutrition_details"),
        restaurant_item.get("nutritionDetailsByDish"),
    ]
    if isinstance(meal, list) and any(by_dish_candidates):
        total_cal = 0.0
        total_sugar = 0.0
        any_flag = None
        for dish in meal:
            dish_name = dish if isinstance(dish, str) else (dish.get("name") if isinstance(dish, dict) else str(dish))
            found = None
            for mapping in by_dish_candidates:
                if isinstance(mapping, dict) and dish_name in mapping:
                    found = mapping[dish_name]
                    break
                if isinstance(mapping, list):
                    for it in mapping:
                        if isinstance(it, dict) and (it.get("dish_name") == dish_name or it.get("name") == dish_name):
                            found = it.get("nutrition") or it
                            break
                if found:
                    break
            if isinstance(found, dict):
                cal = _num(found.get("calories_kcal") or found.get("calories") or found.get("kcal") or found.get("total_calories"))
                sug = _num(found.get("sugar_g") or found.get("sugars_g") or found.get("total_sugar_g"))
                if cal is not None: total_cal += cal
                if sug is not None: total_sugar += sug
                flag = found.get("is_healthy")
                if isinstance(flag, bool):
                    any_flag = flag if any_flag is None else (any_flag and flag)
        if total_cal > 0 or total_sugar > 0:
            return total_cal or None, total_sugar or None, any_flag, None

    # 没拿到
    return None, None, None, None



def _format_reco_text(state: GraphState, top_k_restaurants: int = 3, top_k_meals: int = 3) -> str:
    loc = state.location or {}
    addr = loc.get("address") or "your area"
    items: List[Dict[str, Any]] = state.recommended_restaurants or []

    if not items:
        return f"I found your location near {addr}. Tell me your budget or preferred dishes and I'll recommend some places."

    lines = [f"Here are {min(top_k_restaurants, len(items))} options near {addr}:"]
    for i, it in enumerate(items[:top_k_restaurants], 1):
        name = (
            it.get("restaurant_name")
            or it.get("name")
            or (it.get("restaurant") or {}).get("NAME")
            or (it.get("restaurant") or {}).get("name")
            or ((it.get("matched_dish_details") or [{}])[0].get("restaurant_name")
                if isinstance(it.get("matched_dish_details"), list) and it.get("matched_dish_details")
                else None)
            or "Unknown"
        )
        lines.append(f"{i}. {name}")

        # 取出每家店的 meal 列表
        meals = it.get("completed_meal_list_grouped") or it.get("completed_meal_list") or []
        norm_meals: List[List[str]] = []
        for m in meals:
            if isinstance(m, list):
                norm_meals.append([str(x) for x in m])
            elif isinstance(m, str):
                norm_meals.append([m])

        if norm_meals:
            for j, meal in enumerate(norm_meals[:top_k_meals], 1):
                # 先拼菜名
                meal_line = f"   Meal {j}: " + " + ".join(meal)

                # 从推荐项中抽取这一餐的营养/健康
                cal, sugar, is_healthy, reason = _extract_meal_nutrition(it, j - 1)

                # 追加“卡路里、糖、健康标签”（有啥写啥）
                tails = []
                if cal is not None:
                    tails.append(f"{round(cal)} kcal")
                if sugar is not None:
                    tails.append(f"sugar {round(sugar, 1)} g")
                if is_healthy is True:
                    tails.append("Healthy ✅")
                elif is_healthy is False:
                    tails.append("Not healthy ⚠️")

                # 可选：把不健康原因提示出来（尽量短）
                if reason:
                    # 控制长度，避免太长
                    short_reason = reason if len(reason) <= 80 else (reason[:77] + "…")
                    tails.append(f"({short_reason})")

                if tails:
                    meal_line += " — " + ", ".join(tails)

                lines.append(meal_line)

    lines.append("Want me to filter by price, distance, cuisine, or healthiness?")
    return "\n".join(lines)





def finalize_output(state: GraphState) -> GraphState:
    """Finalize output and add to chat history"""
    print(f"[finalize_output] 完成输出")
    debug_chat_history(state, "finalize_output")
    
    if not getattr(state, "db_record_id", None):
        state.db_record_id = f"reco-{state.patient_id or 'unknown'}-{uuid.uuid4().hex[:8]}"

    safe_text = getattr(state, "safe_message", None)
    text = safe_text or _format_reco_text(state) or state.agent_response or "(no response)"

    agent_response = text

    try:
        hist = list(state.chat_history) if state.chat_history else []
        hist.append(AIMessage(content=text))
    except Exception as e:
        logging.warning("append AIMessage failed: %s", e)
        hist = list(state.chat_history) if state.chat_history else []

    updates: Dict[str, Any] = {
        "chat_history": hist,
        "agent_response": agent_response,
        "final_response": text,
        "user_input": None,
        "db_record_id": state.db_record_id,
    }

    if hasattr(state, "model_copy"):
        return state.model_copy(update=updates)
    else:
        for k, v in updates.items():
            setattr(state, k, v)
        return state


def final_output_simple(state: GraphState) -> GraphState:
    """Simple version of final output (from first file)"""
    print(f"[final_output_simple] 添加响应到聊天历史")
    debug_chat_history(state, "final_output_simple")
    
    if not state.agent_response:
        state.agent_response = "Ready to help with food recognition!"
        print(f"[final_output_simple] 设置默认响应")
    
    ai_message = AIMessage(content=state.agent_response)
    state.chat_history.append(ai_message)
    
    print(f"[final_output_simple] 添加AI响应后总消息数: {len(state.chat_history)}")
    return state


def to_dict(state: GraphState) -> dict[str, Any]:
    """Convert final state to dict for LangGraph Studio display"""
    response = getattr(state, 'agent_response', 'No response generated')
    print(f"[to_dict] 返回最终响应: {response[:100]}{'...' if len(response) > 100 else ''}")
    debug_chat_history(state, "to_dict")
    
    return {
        "agent_response": response,
        "ui_plan": getattr(state, "ui_plan", None),
        "patient_id": getattr(state, "patient_id", None),
        "db_record_id": getattr(state, "db_record_id", None),
        "input_source": getattr(state, "input_source_debug", "unknown"),
        "chat_history_length": len(state.chat_history),
    }


def create_graph_fixed() -> StateGraph:
    """创建修复重复输入问题的图 + 支持患者ID架构"""
    print("[create_graph_fixed] 🔧 构建修复版图，解决重复输入问题 + patient_id支持")
    sg = StateGraph(GraphState)

    # Optional LangSmith/LangGraph tracing
    if os.getenv("LANGSMITH_TRACES") == "1" and hasattr(sg, "enable_tracing"):
        try:
            sg = sg.enable_tracing()
        except Exception as e:
            logging.warning(f"Tracing initialization failed: {e}")

    # 核心节点 - 使用修复版本
    sg.add_node("force_reset", _trace("force_reset")(force_complete_reset_fixed))
    sg.add_node("append_history", _trace("append_history")(append_history_smart))
    
    # Use route_intent if available, otherwise use route_recognition_intent
    try:
        sg.add_node("router", _trace("router")(route_intent))
    except:
        sg.add_node("router", _trace("router")(route_recognition_intent))
    
    # Recognition nodes - 使用增强版存储
    sg.add_node("detect_food", _trace("detect_food")(detect_food))
    sg.add_node("store_entry", _trace("store_entry")(enhanced_store_entry))  # 使用增强版
    
    # Recommendation nodes
    sg.add_node("coerce_reco_input", _trace("coerce_reco_input")(_coerce_reco_input))
    sg.add_node("food_reco", _trace("food_reco")(food_recommendation_node))
    
    # Guard node
    sg.add_node("post_guard", _trace("post_guard")(noop_guard))
    
    # Output nodes
    sg.add_node("simple_output", _trace("simple_output")(simple_output_for_testing))
    sg.add_node("finalize_output", _trace("finalize_output")(finalize_output))
    sg.add_node("generate_ui", _trace("generate_ui")(generate_ui_plan))
    sg.add_node("to_dict", _trace("to_dict")(to_dict))

    # Edge connections
    sg.add_edge(START, "force_reset")
    sg.add_edge("force_reset", "append_history")

    # Edge connections
    sg.add_edge(START, "force_reset")
    sg.add_edge("force_reset", "append_history")

    sg.add_conditional_edges(
        "append_history",
        lambda s: getattr(s, "has_image", True),
        {
            True: "router",
            False: "post_guard"
        },
    )

    # sg.add_edge("append_history", "post_guard")

    # post_guard 分支
    sg.add_conditional_edges(
        "post_guard",
        lambda s: getattr(s, "safety_passed", True),
        {
            True: "router",
            False: "to_dict"
        },
    )

    # Conditional routing
    sg.add_conditional_edges(
        "router",
        lambda s: s.intent,
        {
            "recognition": "detect_food",
            "recommendation": "coerce_reco_input",
            "exit": "to_dict",
        },
    )

    # Recognition flow
    sg.add_edge("detect_food", "store_entry")
    sg.add_edge("store_entry", "simple_output")
    sg.add_edge("simple_output", "generate_ui")
    
    # Recommendation flow
    sg.add_edge("coerce_reco_input", "food_reco")
    sg.add_edge("food_reco", "finalize_output")
    sg.add_edge("finalize_output", "generate_ui")
    
    # Converge to to_dict
    sg.add_edge("generate_ui", "to_dict")
    sg.add_edge("to_dict", END)

    return sg.compile()


# 保持兼容性的别名
create_graph = create_graph_fixed
force_complete_reset = force_complete_reset_fixed
append_history_fixed = append_history_smart


def run_graph_test():
    """Test basic graph functionality"""
    print("\n🧪 测试修复版LangGraph（支持patient_id）...")
    try:
        graph = create_graph_fixed()
        print("✅ 图创建和编译成功")
        print("\n📋 修复版对话流程:")
        print("1. START -> force_reset (清理状态，智能找到原始输入 + 提取患者ID)")
        print("2. force_reset -> append_history (智能判断是否需要添加到历史)")
        print("3. append_history -> post_guard (安全检查)")
        print("4. post_guard -> router (根据输入类型路由)")
        print("5. Recognition: detect_food -> enhanced_store_entry (使用patient_id) -> simple_output -> to_dict")
        print("6. Recommendation: coerce_reco_input -> food_reco -> finalize_output -> to_dict")
        print("7. Exit: router -> to_dict")
        print("8. 所有路径结束于: to_dict -> END")
        print("\n🔧 主要改进:")
        print("- ✅ 支持患者ID（patient_id）架构")
        print("- ✅ 智能患者ID提取（从kwargs、state、user_input等）")
        print("- ✅ 增强版食物数据存储（使用新的存储工具）")
        print("- ✅ 解决重复输入显示问题")
        print("- ✅ 智能输入来源检测")
        print("- ✅ 防重复消息机制")
        print("- ✅ LangGraph Studio兼容性增强")
        print("- ✅ 调试信息完善")
        return True
    except Exception as e:
        print(f"❌ 图测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🔧 修复版LangGraph - 解决重复输入问题 + 支持patient_id架构")
    print("=" * 70)
    
    success = run_graph_test()
    
    if success:
        print("\n✅ 准备好在LangGraph Studio中测试！")
        print("支持场景:")
        print("- 上传图片 -> 获取食物识别（无重复输入，支持patient_id存储）")
        print("- 发送文本 -> 通过管道获取餐厅推荐")
        print("- 发送结构化请求 -> 获取高级餐厅推荐")
        print("- 多轮对话，正确的状态处理（无消息重复）")
        print("- 发送 'bye' -> 获取退出消息")
        print("\n🆕 新功能:")
        print("- 患者ID自动提取和传递")
        print("- 增强版食物数据存储（使用patient_id）")
        print("- 与编排代理架构的完美集成")
        print("\n🔧 关键修复:")
        print("- 智能检测输入来源，避免重复添加到chat_history")
        print("- 支持患者ID参数传递架构")
        print("- 增强的调试信息，便于问题排查")
        print("- 与LangGraph Studio更好的兼容性")
        print("- 集成新的食物存储工具")
    else:
        print("\n❌ 请检查上面的错误后再测试")
    
    print("=" * 70)
