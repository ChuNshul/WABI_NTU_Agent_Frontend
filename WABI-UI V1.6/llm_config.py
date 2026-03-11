from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum

class LLMProvider(Enum):
    """LLM提供商"""
    BEDROCK = "bedrock"
    DASHSCOPE = "dashscope"

@dataclass
class ModelConfig:
    """模型配置"""
    model_id: str
    provider: LLMProvider
    display_name: str
    description: str
    max_tokens: int = 4096
    temperature: float = 0.7
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider.value,
            "display_name": self.display_name,
            "description": self.description,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


# 预定义的模型配置
AVAILABLE_MODELS: Dict[str, ModelConfig] = {
    "claude-3.5-sonnet": ModelConfig(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        provider=LLMProvider.BEDROCK,
        display_name="Claude 3.5 Sonnet",
        description="AWS Bedrock Claude 3.5 Sonnet - 强大的多语言理解和生成能力",
        max_tokens=4096,
        temperature=0.7,
    ),
    "qwen-plus": ModelConfig(
        model_id="qwen-plus",
        provider=LLMProvider.DASHSCOPE,
        display_name="Qwen plus",
        description="阿里云通义千问plus - 优秀的中文理解和生成能力",
        max_tokens=4096,
        temperature=0.7,
    ),
}

# 默认模型
DEFAULT_MODEL = "qwen-plus"

def get_model_config(model_name: Optional[str] = None) -> ModelConfig:
    """
    获取模型配置
    
    Args:
        model_name: 模型名称，如果为None则返回默认模型
        
    Returns:
        ModelConfig对象
    """
    if model_name is None:
        model_name = DEFAULT_MODEL
    
    # 检查是否是有效的模型名称
    if model_name not in AVAILABLE_MODELS:
        model_name = DEFAULT_MODEL
    
    return AVAILABLE_MODELS[model_name]

def get_available_models() -> Dict[str, Dict[str, Any]]:
    """
    获取所有可用模型的信息
    
    Returns:
        模型名称到模型信息的字典
    """
    return {name: config.to_dict() for name, config in AVAILABLE_MODELS.items()}

# LLM 客户端工厂
def create_bedrock_client():
    """创建AWS Bedrock客户端"""
    try:
        import boto3
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "ap-southeast-1"
        return boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        )
    except Exception as e:
        return None

def create_dashscope_client():
    """创建DashScope客户端"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        import sys
        # 尝试导入 dashscope
        import dashscope
            
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            return None
        dashscope.api_key = api_key

        return dashscope
    except ImportError as e:
        return None
    except Exception as e:
        return None

def get_llm_client(model_config: ModelConfig):
    """
    根据模型配置获取对应的客户端
    
    Args:
        model_config: 模型配置
        
    Returns:
        客户端实例或None
    """
    if model_config.provider == LLMProvider.BEDROCK:
        return create_bedrock_client()
    elif model_config.provider == LLMProvider.DASHSCOPE:
        return create_dashscope_client()
    else:
        return None

# LLM 调用函数
def call_bedrock_model(
    client,
    model_id: str,
    messages: list,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    调用Bedrock模型
    
    Args:
        client: Bedrock客户端
        model_id: 模型ID
        messages: 消息列表
        max_tokens: 最大token数
        temperature: 温度参数
        
    Returns:
        包含响应文本和token使用信息的字典
    """
    try:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        
        # 提取token使用量
        headers = response.get("ResponseMetadata", {}).get("HTTPHeaders", {})
        input_tokens = int(headers.get("x-amzn-bedrock-input-token-count", 0))
        output_tokens = int(headers.get("x-amzn-bedrock-output-token-count", 0))
        
        result = json.loads(response["body"].read())
        output_text = result["content"][0]["text"]
        
        return {
            "text": output_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
        
    except Exception as e:
        return None

def call_dashscope_model(
    client,
    model_id: str,
    messages: list,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    调用DashScope模型 (Qwen)
    
    Args:
        client: DashScope客户端
        model_id: 模型ID
        messages: 消息列表
        max_tokens: 最大token数
        temperature: 温度参数
        
    Returns:
        包含响应文本和token使用信息的字典
    """
    try:
        # 转换消息格式为DashScope格式
        dashscope_messages = []
        for msg in messages:
            content = msg["content"]
            if isinstance(content, list) and len(content) > 0:
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                content_text = " ".join(text_parts) if text_parts else str(content)
            elif isinstance(content, str):
                content_text = content
            else:
                content_text = str(content)
            
            dashscope_messages.append({
                "role": msg["role"],
                "content": content_text
            })
        
        # 使用DashScope的Generation.call方法
        response = client.Generation.call(
            model=model_id,
            messages=dashscope_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            result_format="message",
        )
        
        if response.status_code == 200:
            result = response.output.choices[0].message
            usage = response.usage
            
            return {
                "text": result.content,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            }
        else:
            return None
            
    except Exception as e:
        return None

def call_llm(
    model_name: str,
    messages: list,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    trace: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    统一调用LLM的接口
    
    Args:
        model_name: 模型名称
        messages: 消息列表
        max_tokens: 最大token数
        temperature: 温度参数
        
    Returns:
        包含响应文本和token使用信息的字典，失败返回None
    """
    model_config = get_model_config(model_name)
    client = get_llm_client(model_config)
    
    if not client:
        return None

    input_chars = 0
    try:
        for msg in messages or []:
            content = msg.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        input_chars += len(str(item.get("text", "") or ""))
            elif isinstance(content, str):
                input_chars += len(content)
    except Exception:
        input_chars = 0

    t0 = time.perf_counter()
    
    if model_config.provider == LLMProvider.BEDROCK:
        result = call_bedrock_model(
            client=client,
            model_id=model_config.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
    elif model_config.provider == LLMProvider.DASHSCOPE:
        result = call_dashscope_model(
            client=client,
            model_id=model_config.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
    else:
        result = None
    
    dt_ms = int((time.perf_counter() - t0) * 1000)
    if not result:
        return None

    return result
