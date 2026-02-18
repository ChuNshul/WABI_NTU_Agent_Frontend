# -*- coding: utf-8 -*-
"""
streaming_graph.py — Async Streaming Graph for Wabi UI Agent

提供异步流式处理能力，支持：
1. 节点级流式输出（每个节点的中间结果）
2. 动态UI渲染（逐步生成UI组件）
3. 实时进度反馈

Usage:
    from UI.streaming_graph import streaming_graph
    
    async for event in streaming_graph.astream(initial_state):
        if event["type"] == "node_start":
            print(f"开始节点: {event['node']}")
        elif event["type"] == "node_output":
            print(f"节点输出: {event['data']}")
        elif event["type"] == "ui_delta":
            print(f"UI更新: {event['delta']}")
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, Optional, Callable
from datetime import datetime

from langgraph.graph import StateGraph

from UI.state import GraphState, Intent
from UI.nodes.context_manager import manage_context
from UI.nodes.intent_detector import detect_intent
from UI.nodes.data_provider import get_data
from UI.nodes.ui_generator import generate_ui_plan
from UI.nodes.renderer import render_output


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------
class StreamingEvent:
    """流式事件类型"""
    NODE_START = "node_start"
    NODE_OUTPUT = "node_output"
    NODE_END = "node_end"
    PROGRESS = "progress"
    UI_DELTA = "ui_delta"
    UI_COMPLETE = "ui_complete"
    ERROR = "error"
    COMPLETE = "complete"


# ---------------------------------------------------------------------------
# Progress Tracker
# ---------------------------------------------------------------------------
class ProgressTracker:
    """跟踪处理进度"""
    
    NODE_PROGRESS = {
        "context_manager": (10, 20),
        "intent_detector": (20, 35),
        "data_provider": (35, 55),
        "ui_generator": (55, 80),
        "renderer": (80, 100),
    }
    
    def __init__(self):
        self.current_node: Optional[str] = None
        self.completed_nodes: set = set()
        self.current_progress: int = 0
    
    def start_node(self, node_name: str) -> int:
        """开始一个节点，返回起始进度"""
        self.current_node = node_name
        start, _ = self.NODE_PROGRESS.get(node_name, (0, 100))
        self.current_progress = start
        return start
    
    def end_node(self, node_name: str) -> int:
        """结束一个节点，返回结束进度"""
        self.completed_nodes.add(node_name)
        _, end = self.NODE_PROGRESS.get(node_name, (0, 100))
        self.current_progress = end
        return end
    
    def get_progress(self) -> int:
        """获取当前进度"""
        return self.current_progress


# ---------------------------------------------------------------------------
# Streaming Graph Builder
# ---------------------------------------------------------------------------
class StreamingGraph:
    """
    支持流式输出的图执行器
    
    特性：
    - 异步执行
    - 节点级事件流
    - 动态UI渲染
    - 实时进度反馈
    """
    
    def __init__(self):
        self.graph = self._build_graph()
        self.progress_tracker = ProgressTracker()
    
    def _build_graph(self) -> StateGraph:
        """构建基础图结构"""
        workflow = StateGraph(GraphState)
        
        # 注册节点
        workflow.add_node("context_manager", manage_context)
        workflow.add_node("intent_detector", detect_intent)
        workflow.add_node("data_provider", get_data)
        workflow.add_node("ui_generator", generate_ui_plan)
        workflow.add_node("renderer", render_output)
        
        # 定义边
        workflow.set_entry_point("context_manager")
        workflow.add_edge("context_manager", "intent_detector")
        workflow.add_edge("intent_detector", "data_provider")
        workflow.add_edge("data_provider", "ui_generator")
        workflow.add_edge("ui_generator", "renderer")
        
        return workflow.compile()
    
    async def astream(
        self,
        initial_state: GraphState,
        include_intermediate: bool = True
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        异步流式执行图
        
        Args:
            initial_state: 初始状态
            include_intermediate: 是否包含中间结果
            
        Yields:
            流式事件字典
        """
        state = initial_state.copy()
        tracker = ProgressTracker()
        
        # 节点执行顺序
        node_sequence = [
            ("context_manager", self._run_context_manager),
            ("intent_detector", self._run_intent_detector),
            ("data_provider", self._run_data_provider),
            ("ui_generator", self._run_ui_generator),
            ("renderer", self._run_renderer),
        ]
        
        try:
            for node_name, node_func in node_sequence:
                # 节点开始
                progress = tracker.start_node(node_name)
                yield {
                    "type": StreamingEvent.NODE_START,
                    "node": node_name,
                    "progress": progress,
                    "timestamp": datetime.now().isoformat(),
                }
                
                # 执行节点（在线程池中运行同步代码）
                result = await asyncio.to_thread(node_func, state)
                
                # 更新状态
                state.update(result)
                
                # 节点输出
                if include_intermediate:
                    yield {
                        "type": StreamingEvent.NODE_OUTPUT,
                        "node": node_name,
                        "data": self._sanitize_output(result),
                        "progress": tracker.get_progress(),
                        "timestamp": datetime.now().isoformat(),
                    }
                
                # 特殊处理：UI生成器输出UI增量
                if node_name == "ui_generator" and "ui_plan" in result:
                    yield {
                        "type": StreamingEvent.UI_DELTA,
                        "delta": self._extract_ui_delta(result["ui_plan"]),
                        "progress": tracker.get_progress(),
                        "timestamp": datetime.now().isoformat(),
                    }
                
                # 节点结束
                progress = tracker.end_node(node_name)
                yield {
                    "type": StreamingEvent.NODE_END,
                    "node": node_name,
                    "progress": progress,
                    "timestamp": datetime.now().isoformat(),
                }
            
            # 完成
            yield {
                "type": StreamingEvent.COMPLETE,
                "state": self._sanitize_output(state),
                "progress": 100,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            yield {
                "type": StreamingEvent.ERROR,
                "error": str(e),
                "node": tracker.current_node,
                "progress": tracker.get_progress(),
                "timestamp": datetime.now().isoformat(),
            }
    
    def _run_context_manager(self, state: GraphState) -> Dict:
        """运行上下文管理器节点"""
        return manage_context(state)
    
    def _run_intent_detector(self, state: GraphState) -> Dict:
        """运行意图检测器节点"""
        return detect_intent(state)
    
    def _run_data_provider(self, state: GraphState) -> Dict:
        """运行数据提供者节点"""
        return get_data(state)
    
    def _run_ui_generator(self, state: GraphState) -> Dict:
        """运行UI生成器节点"""
        return generate_ui_plan(state)
    
    def _run_renderer(self, state: GraphState) -> Dict:
        """运行渲染器节点"""
        return render_output(state)
    
    def _sanitize_output(self, data: Dict) -> Dict:
        """清理输出数据，移除敏感信息"""
        # 创建副本以避免修改原始数据
        sanitized = {}
        for key, value in data.items():
            # 跳过内部字段
            if key.startswith("_"):
                continue
            # 截断长字符串
            if isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "..."
            else:
                sanitized[key] = value
        return sanitized
    
    def _extract_ui_delta(self, ui_plan: Dict) -> Dict:
        """提取UI增量更新"""
        return {
            "mode": ui_plan.get("mode"),
            "summary": ui_plan.get("summary"),
            "sections_count": len(ui_plan.get("sections", [])),
            "section_types": [s.get("type") for s in ui_plan.get("sections", [])],
        }


# ---------------------------------------------------------------------------
# Dynamic UI Renderer
# ---------------------------------------------------------------------------
class DynamicUIRenderer:
    """
    动态UI渲染器
    
    支持逐步渲染UI组件，提供实时反馈
    """
    
    def __init__(self):
        self.rendered_sections: list = []
        self.current_section: Optional[Dict] = None
    
    async def render_stream(
        self,
        ui_plan_stream: AsyncIterator[Dict]
    ) -> AsyncIterator[Dict]:
        """
        流式渲染UI计划
        
        Args:
            ui_plan_stream: UI计划流
            
        Yields:
            渲染事件
        """
        async for event in ui_plan_stream:
            if event["type"] == StreamingEvent.UI_DELTA:
                # 处理UI增量
                delta = event["delta"]
                render_event = self._process_ui_delta(delta)
                yield render_event
                
            elif event["type"] == StreamingEvent.NODE_END:
                if event["node"] == "renderer":
                    yield {
                        "type": "render_complete",
                        "rendered_sections": self.rendered_sections,
                    }
            else:
                yield event
    
    def _process_ui_delta(self, delta: Dict) -> Dict:
        """处理UI增量更新"""
        section_types = delta.get("section_types", [])
        
        # 为每个section类型生成渲染指令
        render_instructions = []
        for section_type in section_types:
            instruction = self._get_render_instruction(section_type)
            render_instructions.append(instruction)
        
        return {
            "type": "render_instruction",
            "mode": delta.get("mode"),
            "summary": delta.get("summary"),
            "instructions": render_instructions,
        }
    
    def _get_render_instruction(self, section_type: str) -> Dict:
        """获取渲染指令"""
        instructions = {
            "text": {"action": "render_text", "priority": 1},
            "highlight_box": {"action": "render_highlight", "priority": 1},
            "key_value_list": {"action": "render_list", "priority": 2},
            "statistic_grid": {"action": "render_grid", "priority": 2},
            "bar_chart": {"action": "render_chart", "priority": 3, "chart_type": "bar"},
            "pie_chart": {"action": "render_chart", "priority": 3, "chart_type": "pie"},
            "line_chart": {"action": "render_chart", "priority": 3, "chart_type": "line"},
            "radar_chart": {"action": "render_chart", "priority": 3, "chart_type": "radar"},
            "dynamic_place_table": {"action": "render_table", "priority": 3},
            "carousel": {"action": "render_carousel", "priority": 4},
            "button_group": {"action": "render_buttons", "priority": 2},
            "image_display": {"action": "render_image", "priority": 1},
            "steps_list": {"action": "render_steps", "priority": 2},
            "progress_bar": {"action": "render_progress", "priority": 2},
            "tag_list": {"action": "render_tags", "priority": 2},
            "custom_html": {"action": "render_html", "priority": 5},
        }
        return instructions.get(section_type, {"action": "render_generic", "priority": 99})


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------
async def stream_with_progress(
    initial_state: GraphState,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Dict:
    """
    带进度回调的流式执行
    
    Args:
        initial_state: 初始状态
        progress_callback: 进度回调函数 (progress, message) -> None
        
    Returns:
        最终状态
    """
    graph = StreamingGraph()
    final_state = None
    
    async for event in graph.astream(initial_state):
        if event["type"] == StreamingEvent.PROGRESS:
            if progress_callback:
                progress_callback(event["progress"], event.get("message", ""))
        elif event["type"] == StreamingEvent.COMPLETE:
            final_state = event["state"]
        elif event["type"] == StreamingEvent.ERROR:
            raise Exception(event["error"])
    
    return final_state or {}


async def stream_ui_plan(
    initial_state: GraphState
) -> AsyncIterator[Dict]:
    """
    只流式输出UI计划
    
    Args:
        initial_state: 初始状态
        
    Yields:
        UI计划增量
    """
    graph = StreamingGraph()
    renderer = DynamicUIRenderer()
    
    async for event in renderer.render_stream(graph.astream(initial_state)):
        yield event


# ---------------------------------------------------------------------------
# Singleton Instance
# ---------------------------------------------------------------------------
streaming_graph = StreamingGraph()


# ---------------------------------------------------------------------------
# Example Usage
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        """演示流式执行"""
        initial_state: GraphState = {
            "user_input": "附近有什么健康餐厅？",
            "patient_id": "demo_user",
            "language": "Chinese",
            "platform": "web",
            "has_image": False,
            "chat_history": [],
        }
        
        print("开始流式执行...\n")
        
        async for event in streaming_graph.astream(initial_state):
            print(f"[{event['type']}] {event.get('node', '')}")
            
            if event["type"] == StreamingEvent.NODE_OUTPUT:
                data = event.get("data", {})
                for key, value in data.items():
                    if isinstance(value, str) and len(value) < 100:
                        print(f"  {key}: {value}")
            
            elif event["type"] == StreamingEvent.UI_DELTA:
                delta = event.get("delta", {})
                print(f"  UI Mode: {delta.get('mode')}")
                print(f"  Sections: {delta.get('sections_count')}")
            
            elif event["type"] == StreamingEvent.ERROR:
                print(f"  Error: {event.get('error')}")
        
        print("\n执行完成!")
    
    asyncio.run(demo())
