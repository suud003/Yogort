"""
白皮书助手功能模块
将功能关键词扩写为标准的版本功能陈述
"""

import streamlit as st

from ..core.api import call_gemini_stream
from ..core.chat import (
    init_chat_history, add_chat_message, get_chat_history,
    clear_chat_history, build_chat_context
)
from ..core.history import add_to_history
from ..config.prompts import WHITEPAPER_ASSISTANT_SYSTEM_PROMPT


def render_whitepaper_assistant():
    """渲染白皮书助手功能界面"""
    st.markdown("### 📖 白皮书助手")
    st.markdown("将简短的功能关键词扩写为标准的PUBGM WoW模式版本功能陈述。")
    
    # 单行文本框
    feature_keyword = st.text_input(
        "请输入功能关键词",
        placeholder="例如：动画生成、自定义UI、武装AI、全局变量...",
        key="whitepaper_keyword"
    )
    
    # 初始化白皮书助手相关的session_state
    if "generated_feature_desc" not in st.session_state:
        st.session_state.generated_feature_desc = ""
    if "whitepaper_processing" not in st.session_state:
        st.session_state.whitepaper_processing = False
    
    # 生成按钮
    if st.button("📝 生成功能描述", type="primary", disabled=st.session_state.whitepaper_processing):
        if not feature_keyword.strip():
            st.error("请输入功能关键词！")
        else:
            st.session_state.whitepaper_processing = True
            st.session_state.should_stop = False
            st.session_state.generated_feature_desc = ""
            st.session_state.saved_feature_keyword = feature_keyword
            st.session_state.whitepaper_saved_to_history = False
            st.rerun()
    
    # 处理生成阶段
    if st.session_state.whitepaper_processing:
        _process_whitepaper_generation(feature_keyword)
    
    # 显示已生成的功能描述（非处理中状态）
    if st.session_state.generated_feature_desc and not st.session_state.whitepaper_processing:
        _display_whitepaper_result()


def _process_whitepaper_generation(feature_keyword: str):
    """处理功能描述生成过程"""
    # 显示中止按钮和状态
    col_status, col_stop = st.columns([4, 1])
    with col_status:
        st.markdown("**✍️ 正在生成功能描述...**")
    with col_stop:
        if st.button("⏹️ 中止生成", key="stop_whitepaper", type="secondary"):
            st.session_state.should_stop = True
            st.warning("正在中止...")
    
    # 思考过程展示区域
    thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
    with thinking_expander:
        thinking_container = st.empty()
    
    # 输出容器
    output_container = st.empty()
    
    # 构建Prompt
    saved_keyword = st.session_state.get("saved_feature_keyword", feature_keyword)
    user_prompt = f"""
{WHITEPAPER_ASSISTANT_SYSTEM_PROMPT}

---
请输入功能关键词：
【{saved_keyword}】
"""
    
    # 调用Gemini API（流式）
    full_response = ""
    thinking_content = ""
    was_stopped = False
    has_error = False
    error_message = ""
    
    for chunk in call_gemini_stream(user_prompt, ""):
        if st.session_state.should_stop:
            was_stopped = True
            break
        
        if chunk["type"] == "text":
            full_response += chunk["content"]
            output_container.markdown(full_response + "▌")
        elif chunk["type"] == "thinking":
            thinking_content += chunk["content"]
            with thinking_expander:
                thinking_container.markdown(thinking_content)
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
        st.error(f"❌ 生成失败: {error_message}")
    elif was_stopped:
        st.warning("⚠️ 生成已中止")
        if full_response:
            st.session_state.generated_feature_desc = full_response
    else:
        st.success("✅ 功能描述生成完成！")
        st.session_state.generated_feature_desc = full_response
    
    st.session_state.whitepaper_processing = False
    st.session_state.should_stop = False
    st.rerun()


def _display_whitepaper_result():
    """显示功能描述结果和多轮对话界面"""
    st.markdown("### 📄 生成的功能描述")
    st.markdown(st.session_state.generated_feature_desc)
    
    # 下载按钮
    st.download_button(
        label="📋 下载功能描述 (TXT)",
        data=st.session_state.generated_feature_desc,
        file_name="功能描述.txt",
        mime="text/plain"
    )
    
    # 保存到会话历史（仅在首次完成时保存，避免重复）
    if not st.session_state.get("whitepaper_saved_to_history"):
        add_to_history(
            function_type="白皮书助手",
            input_data={"功能关键词": st.session_state.get("saved_feature_keyword", "")},
            output_data=st.session_state.generated_feature_desc,
            download_data=st.session_state.generated_feature_desc.encode("utf-8"),
            download_filename="功能描述.txt",
            download_mime="text/plain"
        )
        st.session_state.whitepaper_saved_to_history = True
    
    # ========== 多轮对话区域 ==========
    st.markdown("---")
    st.markdown("### 💬 继续对话")
    st.caption("您可以继续追问或要求修改，AI将基于已生成的功能描述进行回答。")
    
    # 初始化对话历史
    chat_key = "whitepaper_chat"
    init_chat_history(chat_key)
    
    # 显示对话历史
    chat_history = get_chat_history(chat_key)
    if chat_history:
        for msg in chat_history:
            if msg["role"] == "user":
                st.markdown(f"**🧑 用户** _{msg['timestamp']}_")
                st.info(msg["content"])
            else:
                st.markdown(f"**🤖 助手** _{msg['timestamp']}_")
                st.markdown(msg["content"])
    
    # 对话输入
    wp_chat_col1, wp_chat_col2, wp_chat_col3 = st.columns([6, 1, 1])
    with wp_chat_col1:
        wp_chat_input = st.text_input(
            "追问或修改要求",
            placeholder="例如：请再生成一个关于武装AI的功能描述...",
            key="whitepaper_chat_input",
            label_visibility="collapsed"
        )
    with wp_chat_col2:
        wp_chat_send = st.button("发送", key="whitepaper_chat_send", type="primary", use_container_width=True)
    with wp_chat_col3:
        if st.button("清空", key="whitepaper_chat_clear", use_container_width=True):
            clear_chat_history(chat_key)
            st.rerun()
    
    # 处理对话
    if wp_chat_send and wp_chat_input.strip():
        add_chat_message(chat_key, "user", wp_chat_input)
        
        # 构建上下文
        function_context = f"""【已生成的功能描述】
{st.session_state.generated_feature_desc}"""
        
        history_context = build_chat_context(chat_key, WHITEPAPER_ASSISTANT_SYSTEM_PROMPT)
        full_prompt = f"""{function_context}

{history_context}

【当前用户输入】
{wp_chat_input}

请基于以上内容和对话历史，回答用户的问题或按要求进行修改。如果用户要求生成新的功能描述，请按照标准句式输出。"""
        
        with st.spinner("正在思考..."):
            response_container = st.empty()
            full_response = ""
            for chunk in call_gemini_stream(full_prompt, WHITEPAPER_ASSISTANT_SYSTEM_PROMPT):
                if chunk["type"] == "text":
                    full_response += chunk["content"]
                    response_container.markdown(full_response + "▌")
                elif chunk["type"] == "error":
                    st.error(f"生成失败: {chunk['content']}")
                    break
            
            if full_response:
                response_container.markdown(full_response)
                add_chat_message(chat_key, "assistant", full_response)
                st.rerun()
