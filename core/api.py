"""
Gemini API 调用模块
封装与Google Gemini API的所有交互
"""

import streamlit as st
from google import genai
from google.genai import types
from typing import Optional, Generator
import time

from ..config.models import AVAILABLE_MODELS, FILE_UPLOAD_SUPPORTED_MODELS


def get_gemini_client():
    """获取Gemini客户端实例"""
    api_key = st.session_state.get("api_key", "")
    if not api_key:
        st.error("⚠️ 请先在侧边栏配置 API Key")
        return None
    try:
        client = genai.Client(api_key=api_key)
        return client
    except Exception as e:
        st.error(f"API初始化失败: {str(e)}")
        return None


def get_selected_model():
    """获取当前选择的模型"""
    return st.session_state.get("selected_model", AVAILABLE_MODELS[0])


def fetch_available_models():
    """从API获取可用的模型列表"""
    api_key = st.session_state.get("api_key", "")
    if not api_key:
        return []
    try:
        client = genai.Client(api_key=api_key)
        models = []
        for model in client.models.list():
            # 只获取支持generateContent的模型
            if hasattr(model, 'supported_actions') and 'generateContent' in model.supported_actions:
                models.append(model.name.replace("models/", ""))
            elif not hasattr(model, 'supported_actions'):
                # 如果没有supported_actions属性，也添加（兼容性处理）
                model_name = model.name.replace("models/", "")
                if 'gemini' in model_name.lower():
                    models.append(model_name)
        return sorted(models) if models else AVAILABLE_MODELS
    except Exception as e:
        st.sidebar.warning(f"获取模型列表失败，使用默认列表: {str(e)}")
        return AVAILABLE_MODELS


def is_file_upload_supported() -> bool:
    """检查当前选择的模型是否支持文件上传"""
    current_model = get_selected_model()
    # 检查模型名称是否在支持列表中（部分匹配）
    for supported_model in FILE_UPLOAD_SUPPORTED_MODELS:
        if supported_model in current_model or current_model in supported_model:
            return True
    return False


def call_gemini(prompt: str, system_prompt: str = "") -> Optional[str]:
    """
    调用Gemini API（非流式，用于内部处理）
    
    Args:
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
    
    Returns:
        API返回的文本内容，失败返回None
    """
    try:
        client = get_gemini_client()
        if client is None:
            return None
        
        # 构建配置
        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None
        )
        
        response = client.models.generate_content(
            model=get_selected_model(),
            contents=prompt,
            config=config
        )
        return response.text
    except Exception as e:
        st.error(f"API调用失败: {str(e)}")
        return None


def call_gemini_stream(prompt: str, system_prompt: str = "", thinking_container=None) -> Generator[dict, None, None]:
    """
    流式调用Gemini API，支持中止、错误展示、思考过程和自动重试
    
    Args:
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
        thinking_container: 用于显示思考过程的容器（可选）
    
    Yields:
        dict: {"type": "text"|"thinking"|"error"|"retry", "content": str}
    """
    # 清空之前的错误
    st.session_state.last_error = ""
    st.session_state.thinking_content = ""
    
    # 重试配置
    max_retries = 3
    retry_delay = 5  # 秒
    retryable_errors = ["503", "429", "overloaded", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "rate limit"]
    
    for attempt in range(max_retries):
        try:
            client = get_gemini_client()
            if client is None:
                yield {"type": "error", "content": "API客户端初始化失败，请检查API Key"}
                return
            
            # 构建配置 - 启用思考过程（如果模型支持）
            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                # 尝试启用思考模式（部分模型支持）
                thinking_config=types.ThinkingConfig(
                    thinking_budget=10000  # 允许的思考token数
                ) if "2.5" in get_selected_model() or "think" in get_selected_model().lower() else None
            )
            
            # 使用流式API
            response_stream = client.models.generate_content_stream(
                model=get_selected_model(),
                contents=prompt,
                config=config
            )
            
            for chunk in response_stream:
                # 检查是否需要中止
                if st.session_state.should_stop:
                    yield {"type": "stopped", "content": "用户已中止生成"}
                    st.session_state.should_stop = False
                    return
                
                # 处理思考过程（如果有）
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'content') and candidate.content:
                            for part in candidate.content.parts:
                                # 检查是否是思考内容
                                if hasattr(part, 'thought') and part.thought:
                                    thinking_text = part.text if hasattr(part, 'text') else str(part)
                                    st.session_state.thinking_content += thinking_text
                                    yield {"type": "thinking", "content": thinking_text}
                                elif hasattr(part, 'text') and part.text:
                                    yield {"type": "text", "content": part.text}
                elif chunk.text:
                    yield {"type": "text", "content": chunk.text}
            
            # 成功完成，退出重试循环
            return
                    
        except Exception as e:
            error_msg = str(e)
            st.session_state.last_error = error_msg
            
            # 检查是否是可重试的错误
            is_retryable = any(err_key in error_msg for err_key in retryable_errors)
            
            if is_retryable and attempt < max_retries - 1:
                # 通知用户正在重试
                remaining = max_retries - attempt - 1
                yield {
                    "type": "retry", 
                    "content": f"⚠️ 服务暂时不可用 ({error_msg[:50]}...)，{retry_delay}秒后自动重试（剩余{remaining}次）..."
                }
                time.sleep(retry_delay)
                # 增加下次重试的等待时间（指数退避）
                retry_delay = min(retry_delay * 2, 30)
                continue
            else:
                # 不可重试或已用完重试次数
                yield {"type": "error", "content": error_msg}
                return


def stream_to_container(prompt: str, system_prompt: str, container, thinking_container=None, status_container=None) -> tuple:
    """
    流式输出到Streamlit容器，实时显示打字效果，支持中止、错误展示和思考过程
    
    Args:
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
        container: Streamlit容器对象（如st.empty()或st.container()）
        thinking_container: 用于显示思考过程的容器（可选）
        status_container: 用于显示状态信息的容器（可选）
    
    Returns:
        tuple: (完整的响应文本, 是否成功, 错误信息)
    """
    full_response = ""
    thinking_text = ""
    error_msg = ""
    was_stopped = False
    
    # 使用生成器进行流式输出
    for chunk_data in call_gemini_stream(prompt, system_prompt, thinking_container):
        chunk_type = chunk_data.get("type", "text")
        chunk_content = chunk_data.get("content", "")
        
        if chunk_type == "text":
            full_response += chunk_content
            # 实时更新显示内容，添加光标效果
            container.markdown(full_response + " ▌")
        elif chunk_type == "thinking":
            thinking_text += chunk_content
            # 显示思考过程
            if thinking_container:
                thinking_container.markdown(f"💭 **模型思考中...**\n\n{thinking_text}")
        elif chunk_type == "retry":
            # 显示重试状态
            if status_container:
                status_container.warning(chunk_content)
            else:
                st.warning(chunk_content)
        elif chunk_type == "error":
            error_msg = chunk_content
            if status_container:
                status_container.error(f"❌ API调用失败: {error_msg}")
            else:
                st.error(f"❌ API调用失败: {error_msg}")
            break
        elif chunk_type == "stopped":
            was_stopped = True
            if status_container:
                status_container.warning("⏹️ 生成已中止")
            break
        
        # 强制刷新显示
        time.sleep(0.01)
    
    # 移除光标，显示最终结果
    if full_response:
        container.markdown(full_response)
    
    # 判断是否成功
    success = bool(full_response) and not error_msg and not was_stopped
    
    return (full_response, success, error_msg)


def stream_generator(prompt: str, system_prompt: str):
    """
    创建流式输出生成器，配合st.write_stream使用
    
    Args:
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
    
    Yields:
        文本片段
    """
    for chunk_data in call_gemini_stream(prompt, system_prompt):
        if chunk_data.get("type") == "text":
            yield chunk_data.get("content", "")
