"""
生成策划案功能模块
"""

import streamlit as st

from ..core.api import stream_to_container, call_gemini
from ..config.prompts import GENERATE_PRD_SYSTEM_PROMPT, SELF_CHECK_SYSTEM_PROMPT


def generate_prd(user_input: str, use_stream: bool = False, container=None, 
                 thinking_container=None, status_container=None) -> tuple:
    """
    功能模块1：生成策划案（支持流式输出）
    
    Args:
        user_input: 用户输入的功能描述
        use_stream: 是否使用流式输出
        container: Streamlit容器对象，用于流式显示
        thinking_container: 用于显示思考过程的容器
        status_container: 用于显示状态信息的容器
    
    Returns:
        tuple: (生成的策划案文本, 是否成功, 错误信息)
    """
    prompt = f"请根据以下功能描述生成完整的策划案：\n\n{user_input}"
    
    if use_stream and container:
        return stream_to_container(prompt, GENERATE_PRD_SYSTEM_PROMPT, container, 
                                   thinking_container, status_container)
    else:
        result = call_gemini(prompt, GENERATE_PRD_SYSTEM_PROMPT)
        return (result, result is not None, st.session_state.last_error if not result else "")


def ai_self_check(prd_content: str, use_stream: bool = False, container=None, 
                  thinking_container=None, status_container=None) -> tuple:
    """
    AI自检功能：对策划案进行复检清单检查（支持流式输出）
    
    Args:
        prd_content: 策划案内容
        use_stream: 是否使用流式输出
        container: Streamlit容器对象，用于流式显示
        thinking_container: 用于显示思考过程的容器
        status_container: 用于显示状态信息的容器
    
    Returns:
        tuple: (检查结果报告, 是否成功, 错误信息)
    """
    prompt = f"""请对以下策划案进行复检清单检查：

{prd_content}

请逐一检查每一项，给出详细的检查结果。"""
    
    if use_stream and container:
        return stream_to_container(prompt, SELF_CHECK_SYSTEM_PROMPT, container, 
                                   thinking_container, status_container)
    else:
        result = call_gemini(prompt, SELF_CHECK_SYSTEM_PROMPT)
        return (result, result is not None, st.session_state.last_error if not result else "")
