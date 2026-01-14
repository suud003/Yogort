"""
多轮对话管理模块
管理各功能模块的对话历史和上下文
"""

import streamlit as st
from datetime import datetime
from typing import Optional

from .api import call_gemini_stream


def init_chat_history(chat_key: str):
    """
    初始化指定功能的对话历史
    
    Args:
        chat_key: 对话历史的键名（如 'generate_chat', 'report_chat' 等）
    """
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []


def add_chat_message(chat_key: str, role: str, content: str):
    """
    添加消息到对话历史
    
    Args:
        chat_key: 对话历史的键名
        role: 角色（'user' 或 'assistant'）
        content: 消息内容
    """
    init_chat_history(chat_key)
    st.session_state[chat_key].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })


def get_chat_history(chat_key: str) -> list:
    """
    获取对话历史
    
    Args:
        chat_key: 对话历史的键名
    
    Returns:
        对话历史列表
    """
    init_chat_history(chat_key)
    return st.session_state[chat_key]


def clear_chat_history(chat_key: str):
    """
    清空对话历史
    
    Args:
        chat_key: 对话历史的键名
    """
    st.session_state[chat_key] = []


def build_chat_context(chat_key: str, system_prompt: str, max_history: int = 10) -> str:
    """
    构建包含对话历史的上下文Prompt
    
    Args:
        chat_key: 对话历史的键名
        system_prompt: 系统提示词
        max_history: 最大历史消息数量
    
    Returns:
        包含历史上下文的完整Prompt
    """
    history = get_chat_history(chat_key)
    
    if not history:
        return ""
    
    # 只取最近的N条历史
    recent_history = history[-max_history:] if len(history) > max_history else history
    
    # 构建对话历史文本
    history_text = "\n\n【对话历史】\n"
    for msg in recent_history:
        role_label = "用户" if msg["role"] == "user" else "助手"
        history_text += f"{role_label}: {msg['content']}\n\n"
    
    return history_text


def render_chat_interface(chat_key: str, system_prompt: str, container, 
                          placeholder: str = "请输入您的问题或修改要求...",
                          function_context: str = ""):
    """
    渲染多轮对话界面
    
    Args:
        chat_key: 对话历史的键名
        system_prompt: 系统提示词
        container: Streamlit容器
        placeholder: 输入框占位文本
        function_context: 当前功能的上下文（如已生成的内容）
    
    Returns:
        是否有新的对话产生
    """
    init_chat_history(chat_key)
    history = get_chat_history(chat_key)
    
    # 显示对话历史
    if history:
        with container:
            st.markdown("#### 💬 对话历史")
            for i, msg in enumerate(history):
                if msg["role"] == "user":
                    st.markdown(f"**🧑 用户** _{msg['timestamp']}_")
                    st.info(msg["content"])
                else:
                    st.markdown(f"**🤖 助手** _{msg['timestamp']}_")
                    st.markdown(msg["content"])
            st.markdown("---")
    
    # 用于控制对话输入的状态
    chat_input_key = f"{chat_key}_input"
    chat_processing_key = f"{chat_key}_processing"
    
    if chat_processing_key not in st.session_state:
        st.session_state[chat_processing_key] = False
    
    # 对话输入区域
    col_input, col_btn, col_clear = container.columns([6, 1, 1])
    
    with col_input:
        user_message = st.text_input(
            "继续对话",
            placeholder=placeholder,
            key=chat_input_key,
            label_visibility="collapsed"
        )
    
    with col_btn:
        send_clicked = st.button("发送", key=f"{chat_key}_send", type="primary", use_container_width=True)
    
    with col_clear:
        if st.button("清空", key=f"{chat_key}_clear", use_container_width=True):
            clear_chat_history(chat_key)
            st.rerun()
    
    return send_clicked, user_message, chat_processing_key


def process_chat_message(chat_key: str, user_message: str, system_prompt: str, 
                         function_context: str, output_container):
    """
    处理用户的对话消息并生成回复
    
    Args:
        chat_key: 对话历史的键名
        user_message: 用户消息
        system_prompt: 系统提示词
        function_context: 当前功能的上下文
        output_container: 输出容器
    
    Returns:
        生成的回复内容
    """
    # 添加用户消息到历史
    add_chat_message(chat_key, "user", user_message)
    
    # 构建完整的Prompt
    history_context = build_chat_context(chat_key, system_prompt)
    
    full_prompt = f"""{function_context}

{history_context}

【当前用户输入】
{user_message}

请基于以上上下文和对话历史，回答用户的问题或按要求进行修改。"""
    
    # 调用API生成回复
    full_response = ""
    was_stopped = False
    has_error = False
    error_message = ""
    
    for chunk in call_gemini_stream(full_prompt, system_prompt):
        if st.session_state.should_stop:
            was_stopped = True
            break
        
        if chunk["type"] == "text":
            full_response += chunk["content"]
            output_container.markdown(full_response + "▌")
        elif chunk["type"] == "error":
            has_error = True
            error_message = chunk["content"]
            break
        elif chunk["type"] == "retry":
            st.info(chunk["content"])
    
    # 移除光标
    if full_response:
        output_container.markdown(full_response)
    
    # 处理结果
    if has_error:
        return None, error_message
    elif was_stopped:
        if full_response:
            add_chat_message(chat_key, "assistant", full_response)
        return full_response, "已中止"
    else:
        add_chat_message(chat_key, "assistant", full_response)
        return full_response, None
