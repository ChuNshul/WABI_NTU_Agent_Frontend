# Project Wabi C 更新日志

本项目探索使用代理式 AI（Agentic AI）为健康聊天机器人生成自适应用户界面（Adaptive UI），通过 LLM/VLM 根据用户目标与行为信号动态生成、调整并推荐对话界面元素，强调与推理代理和 UI 生成模块的协同，以确保可解释性、可用性与符合健康指导的一致性。

## 概览
- 目标：利用 LLM/VLM 动态生成与调整健康聊天机器人的界面组件（提示、视觉摘要、交互流程、反馈布局等）
- 重点：推理代理与 UI 生成模块协同、平台兼容（Web/社交平台）、可解释性与健康合规
- 受益：提升用户参与度与决策支持，同时与现有平台与医疗约束兼容

---

## WABI-UI V1.0 rc1
流式处理与用户反馈系统
- 新增：异步流式图执行器（StreamingGraph），支持节点级流式输出与实时进度反馈
  - 参考：[streaming_graph.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/WABI-UI%20V1.0%20rc1/streaming_graph.py)
- 新增：用户反馈记录模块，纠错意图的反馈保存到 CSV 文件
  - 参考：[feedback_logger.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/WABI-UI%20V1.0%20rc1/feedback_logger.py)
- 优化：意图跟随机制，用户跟进问题继承上一轮意图，无需重新提供数据
  - 参考：[nodes/intent_detector.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/WABI-UI%20V1.0%20rc1/nodes/intent_detector.py)
- 架构：模块化节点设计（context_manager, intent_detector, data_provider, ui_generator, renderer）
  - 参考：[graph.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/WABI-UI%20V1.0%20rc1/graph.py)

## WABI-UI V1.0 beta
上下文记忆与增强流水线
- 新增：上下文管理节点（Context Manager），从历史对话中提取相关信息
  - 参考：[nodes/context_manager.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/WABI-UI%20V1.0%20beta/nodes/context_manager.py)
- 新增：基于 LLM 的意图检测，支持七种意图分类（食物识别/餐厅推荐/纠错/澄清/安全护栏/目标计划/通用聊天）
  - 参考：[nodes/intent_detector.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/WABI-UI%20V1.0%20beta/nodes/intent_detector.py)
- 架构：增强流水线（context_manager → intent_detector → data_provider → ui_generator → renderer）
  - 参考：[graph.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/WABI-UI%20V1.0%20beta/graph.py)

## WABI-UI V1.0 alpha
UI Agent 独立架构
- 重构：从 MVP 的单文件架构迁移到模块化 UI Agent 架构
  - 参考：[ui_graph.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/WABI-UI%20V1.0%20alpha/ui_graph.py)
- 新增：UI 配置模块（ui_config.py），集中管理配置参数
- 新增：专用 LLM 模块（ui_llm.py），封装 Bedrock 调用逻辑
- 架构：拓扑路由（router → clarification | food_rec_no_img | goal_no_data | llm_generator → platform_enforcer | fallback）

## MVP V0.9
多语言支持与意图识别优化
- 新增：完整的多语言支持（中文/英文），根据 `state.language` 动态生成对应语言的 UI
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.9/agent.py)
- 优化：澄清意图的确定性处理，无需调用 LLM 即可快速响应
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.9/agent.py)
- 延续：平台感知与安全校验机制

## MVP V0.8
代码结构优化与性能提升
- 优化：UI 生成逻辑的模块化重构
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.8/agent.py)
- 强化：平台兼容性处理，针对不同平台优化输出格式

## MVP V0.7
意图处理与平台适配增强
- 新增：澄清意图（clarification）的确定性处理，Web 平台显示交互式按钮
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.7/agent.py)
- 优化：平台检测与适配逻辑，提升跨平台一致性

## MVP V0.6
平台感知与安全增强，跨平台输出规范
- 新增：平台指令注入与强制兼容（web/wechat/whatsapp），对 WeChat/WhatsApp 禁用复杂组件与 suggestions，自动退化为纯文本
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.6/agent.py)
- 强化：JSON 解析鲁棒性，尝试宽松解析与控制字符清理
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.6/agent.py)
- 延续：Bedrock Token 使用统计注入到 `ui_plan.token_usage`
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.6/agent.py)
- 保持：自定义 HTML 组件的安全与结构校验（移除 `<script>`、闭合 `<div>`）
  - 参考：[ui_components.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.6/ui_components.py)

## MVP V0.5
成本可观察性与安全校验
- 新增：从 Bedrock 响应头提取 Token 计数并注入 `ui_plan.token_usage`
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.5/agent.py)
- 强化：自定义 HTML 组件安全校验与结构修复（移除 `<script>`，自动补齐未闭合 `<div>`）
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.5/agent.py)

## MVP V0.4
可扩展 UI 能力与自我校验
- 新增：`custom_html` 组件，用于当标准组件不适配时由 LLM 生成 Tailwind 风格的自定义渲染
  - 参考：[ui_components.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.4/ui_components.py)
- 增强：在 LLM 生成后执行安全/结构校验，移除脚本与修复标签不匹配
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.4/agent.py)

## MVP V0.3
引入 LLM 自适应 UI 生成与组件库
- 新增：通过 AWS Bedrock（Claude）生成自适应 `ui_plan`，失败时回退到最小可用界面
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.3/agent.py)
- 新增：UI 组件库与系统提示模板，明确组件语义与输出格式
  - 参考：[ui_components.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.3/ui_components.py)
- 新增：适配性测试脚本，验证餐厅推荐使用 `dynamic_place_table` 与包含排序建议
  - 参考：[test_adaptive_ui.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.3/test_adaptive_ui.py)

## MVP V0.2
Mock 驱动的 UI/UX 快速迭代
- 切换：后端进入 Mock 模式以独立演示 UI/UX，支持识别、纠错、食谱与健康分析等场景
  - 参考：[web_demo.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.2/web_demo.py)
- 新增：动态餐厅表格 `dynamic_place_table`，并在 Mock 数据中提供排序/过滤用字段
  - 参考：[mock_data.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.2/mock_data.py)
- 增强：CORS 支持、状态重置端点、关键词级心理健康守护（guardrail）路由
  - 参考：[web_demo.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.2/web_demo.py)

## MVP V0.1
端到端原型与编排框架
- 初始：LangGraph 编排（路由、历史管理、重复输入规避）、患者 ID 贯穿数据存储
  - 参考：[graph.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.1/graph.py)、[state.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.1/state.py)
- UI Agent：根据识别/推荐意图生成通用 `ui_plan`（文本、轮播、键值列表、高亮框、图片展示等）
  - 参考：[agent.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.1/agent.py)
- Web 演示：FastAPI 前后端一体的对话式界面，支持图片上传与处理进度可视化
  - 参考：[web_demo.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.1/web_demo.py)
- 修复：重复输入显示问题、Studio 消息重复添加、智能输入来源检测
  - 参考：[graph.py](https://github.com/ChuNshul/WABI_NTU_Agent_Frontend/MVP%20V0.1/graph.py)

---

## 兼容性与注意事项
- 平台规范：WeChat/WhatsApp 输出需退化为纯文本并禁用建议项，Web 端可使用全部丰富组件
- 安全与健康合规：移除潜在不安全脚本、突出高热量/健康风险信息，避免建议不可执行的外部动作
- 成本可观察：记录与展示 LLM Token 使用，便于后续优化推理与生成成本

