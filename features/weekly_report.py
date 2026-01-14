"""
周报助手功能模块
将零散的日报/工作记录汇总为专业周报
"""

import streamlit as st

from ..core.api import call_gemini_stream
from ..core.chat import (
    init_chat_history, add_chat_message, get_chat_history,
    clear_chat_history, build_chat_context
)
from ..core.history import add_to_history
from ..config.prompts import WEEKLY_REPORT_SYSTEM_PROMPT


def render_weekly_report():
    """渲染周报助手功能界面"""
    st.markdown("### 📅 周报助手")
    st.markdown("将零散的日报/工作记录汇总、提炼为逻辑清晰、重点突出的专业周报。")
    
    # 大的多行文本框
    daily_logs = st.text_area(
        "请输入本周日报/工作记录",
        height=400,
        placeholder="""请输入本周的工作记录，可以是日报汇总或工作流水...

示例格式：
【周一】
- 完成推荐算法的数据分析，发现头部固化问题
- 与产品对齐特辑分类来源逻辑

【周二】
- 调整混排策略，增加"热门趋势"多样性
- 修复作品更新后未重新审核的问题

【周三】
- 新增平均对局时长准入筛选条件
- 提高人审举报阈值从1调整到5
...""",
        key="weekly_daily_logs"
    )
    
    # 初始化周报助手相关的session_state
    if "generated_weekly_report" not in st.session_state:
        st.session_state.generated_weekly_report = ""
    if "weekly_report_processing" not in st.session_state:
        st.session_state.weekly_report_processing = False
    
    # 生成按钮
    if st.button("📝 生成周报", type="primary", disabled=st.session_state.weekly_report_processing):
        if not daily_logs.strip():
            st.error("请输入本周日报/工作记录！")
        else:
            st.session_state.weekly_report_processing = True
            st.session_state.should_stop = False
            st.session_state.generated_weekly_report = ""
            st.session_state.saved_daily_logs = daily_logs
            st.session_state.weekly_saved_to_history = False
            st.rerun()
    
    # 处理生成阶段
    if st.session_state.weekly_report_processing:
        _process_weekly_report_generation(daily_logs)
    
    # 显示已生成的周报（非处理中状态）
    if st.session_state.generated_weekly_report and not st.session_state.weekly_report_processing:
        _display_weekly_report_result()


def _process_weekly_report_generation(daily_logs: str):
    """处理周报生成过程"""
    # 显示中止按钮和状态
    col_status, col_stop = st.columns([4, 1])
    with col_status:
        st.markdown("**✍️ 正在生成周报...**")
    with col_stop:
        if st.button("⏹️ 中止生成", key="stop_weekly", type="secondary"):
            st.session_state.should_stop = True
            st.warning("正在中止...")
    
    # 思考过程展示区域
    thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
    with thinking_expander:
        thinking_container = st.empty()
    
    # 输出容器
    output_container = st.empty()
    
    # 构建Prompt
    saved_logs = st.session_state.get("saved_daily_logs", daily_logs)
    user_prompt = f"""
{WEEKLY_REPORT_SYSTEM_PROMPT}

Input Data (本周日报/工作记录):
{saved_logs}
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
            st.session_state.generated_weekly_report = full_response
    else:
        st.success("✅ 周报生成完成！")
        st.session_state.generated_weekly_report = full_response
    
    st.session_state.weekly_report_processing = False
    st.session_state.should_stop = False
    st.rerun()


def _display_weekly_report_result():
    """显示周报结果和多轮对话界面"""
    st.markdown("### 📄 生成的周报")
    st.markdown(st.session_state.generated_weekly_report)
    
    # 下载按钮
    st.download_button(
        label="📋 下载周报 (TXT)",
        data=st.session_state.generated_weekly_report,
        file_name="本周周报.txt",
        mime="text/plain"
    )
    
    # 保存到会话历史（仅在首次完成时保存，避免重复）
    if not st.session_state.get("weekly_saved_to_history"):
        add_to_history(
            function_type="周报助手",
            input_data={"工作记录": st.session_state.get("saved_daily_logs", "")[:200] + "..."},
            output_data=st.session_state.generated_weekly_report,
            download_data=st.session_state.generated_weekly_report.encode("utf-8"),
            download_filename="本周周报.txt",
            download_mime="text/plain"
        )
        st.session_state.weekly_saved_to_history = True
    
    # ========== 多轮对话区域 ==========
    st.markdown("---")
    st.markdown("### 💬 继续对话")
    st.caption("您可以继续追问或要求修改，AI将基于已生成的周报进行回答。")
    
    # 初始化对话历史
    chat_key = "weekly_chat"
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
    weekly_chat_col1, weekly_chat_col2, weekly_chat_col3 = st.columns([6, 1, 1])
    with weekly_chat_col1:
        weekly_chat_input = st.text_input(
            "追问或修改要求",
            placeholder="例如：请补充数据分析部分的内容...",
            key="weekly_chat_input",
            label_visibility="collapsed"
        )
    with weekly_chat_col2:
        weekly_chat_send = st.button("发送", key="weekly_chat_send", type="primary", use_container_width=True)
    with weekly_chat_col3:
        if st.button("清空", key="weekly_chat_clear", use_container_width=True):
            clear_chat_history(chat_key)
            st.rerun()
    
    # 处理对话
    if weekly_chat_send and weekly_chat_input.strip():
        add_chat_message(chat_key, "user", weekly_chat_input)
        
        # 构建上下文
        function_context = f"""【已生成的周报】
{st.session_state.generated_weekly_report}"""
        
        history_context = build_chat_context(chat_key, WEEKLY_REPORT_SYSTEM_PROMPT)
        full_prompt = f"""{function_context}

{history_context}

【当前用户输入】
{weekly_chat_input}

请基于以上周报和对话历史，回答用户的问题或按要求进行修改。如果用户要求修改，请输出修改后的完整内容。"""
        
        with st.spinner("正在思考..."):
            response_container = st.empty()
            full_response = ""
            for chunk in call_gemini_stream(full_prompt, WEEKLY_REPORT_SYSTEM_PROMPT):
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
