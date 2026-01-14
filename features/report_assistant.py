"""
汇报助手功能模块
将碎片化的工作信息转化为结构化的汇报文案
"""

import streamlit as st

from ..core.api import call_gemini_stream
from ..core.chat import (
    init_chat_history, add_chat_message, get_chat_history,
    clear_chat_history, build_chat_context
)
from ..core.history import add_to_history
from ..config.prompts import REPORT_ASSISTANT_SYSTEM_PROMPT


def render_report_assistant():
    """渲染汇报助手功能界面"""
    st.markdown("### 📊 汇报助手")
    st.markdown("将碎片化的工作信息转化为结构化的汇报文案，用于向领导同步工作事项。")
    
    # 三个独立的输入框
    col1, col2 = st.columns([1, 1])
    
    with col1:
        current_problem = st.text_area(
            "📌 当前问题 (Current Problem)",
            height=150,
            placeholder="描述当前遇到的问题或背景...\n\n例如：\n当前用户反馈游戏内好友添加流程繁琐，需要手动输入ID，且没有推荐好友功能...",
            key="report_problem"
        )
        
        expected_result = st.text_area(
            "🎯 预期结果 (Expected Result)",
            height=150,
            placeholder="描述期望达成的效果...\n\n例如：\n好友添加成功率提升30%，用户好友数量平均增加2个...",
            key="report_result"
        )
    
    with col2:
        solution = st.text_area(
            "💡 解决方案 (Solution)",
            height=332,
            placeholder="描述您的解决方案或计划采取的措施...\n\n例如：\n1. 新增「可能认识的人」推荐列表\n2. 支持通过游戏内昵称搜索\n3. 添加好友后自动发送一条招呼语...",
            key="report_solution"
        )
    
    # 初始化汇报助手相关的session_state
    if "generated_report" not in st.session_state:
        st.session_state.generated_report = ""
    if "report_processing" not in st.session_state:
        st.session_state.report_processing = False
    
    # 生成按钮
    if st.button("📝 生成汇报", type="primary", disabled=st.session_state.report_processing):
        # 验证输入
        if not current_problem.strip():
            st.error("请填写【当前问题】！")
        elif not solution.strip():
            st.error("请填写【解决方案】！")
        elif not expected_result.strip():
            st.error("请填写【预期结果】！")
        else:
            st.session_state.report_processing = True
            st.session_state.should_stop = False
            st.session_state.generated_report = ""
            st.session_state.report_saved_to_history = False
            st.rerun()
    
    # 处理生成阶段
    if st.session_state.report_processing:
        _process_report_generation(current_problem, solution, expected_result)
    
    # 显示已生成的汇报（非处理中状态）
    if st.session_state.generated_report and not st.session_state.report_processing:
        _display_report_result()


def _process_report_generation(current_problem: str, solution: str, expected_result: str):
    """处理汇报生成过程"""
    # 显示中止按钮和状态
    col_status, col_stop = st.columns([4, 1])
    with col_status:
        st.markdown("**✍️ 正在生成汇报文案...**")
    with col_stop:
        if st.button("⏹️ 中止生成", key="stop_report", type="secondary"):
            st.session_state.should_stop = True
            st.warning("正在中止...")
    
    # 思考过程展示区域
    thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
    with thinking_expander:
        thinking_container = st.empty()
    
    # 输出容器
    output_container = st.empty()
    
    # 构建Prompt
    user_prompt = f"""请根据以下信息，撰写一份给领导的工作汇报文案：

【当前问题】
{current_problem}

【解决方案】
{solution}

【预期结果】
{expected_result}

请按照模板格式输出汇报文案。"""
    
    # 调用Gemini API（流式）
    full_response = ""
    thinking_content = ""
    was_stopped = False
    has_error = False
    error_message = ""
    
    for chunk in call_gemini_stream(user_prompt, REPORT_ASSISTANT_SYSTEM_PROMPT, thinking_container):
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
            st.session_state.generated_report = full_response
    else:
        st.success("✅ 汇报文案生成完成！")
        st.session_state.generated_report = full_response
    
    st.session_state.report_processing = False
    st.session_state.should_stop = False
    st.rerun()


def _display_report_result():
    """显示汇报结果和多轮对话界面"""
    st.markdown("### 📄 生成的汇报文案")
    st.markdown(st.session_state.generated_report)
    
    # 复制按钮（使用下载按钮模拟）
    st.download_button(
        label="📋 下载汇报文案 (TXT)",
        data=st.session_state.generated_report,
        file_name="工作汇报.txt",
        mime="text/plain"
    )
    
    # 保存到会话历史（仅在首次完成时保存，避免重复）
    if not st.session_state.get("report_saved_to_history"):
        add_to_history(
            function_type="汇报助手",
            input_data={
                "当前问题": st.session_state.get("report_problem", ""),
                "解决方案": st.session_state.get("report_solution", ""),
                "预期结果": st.session_state.get("report_result", "")
            },
            output_data=st.session_state.generated_report,
            download_data=st.session_state.generated_report.encode("utf-8"),
            download_filename="工作汇报.txt",
            download_mime="text/plain"
        )
        st.session_state.report_saved_to_history = True
    
    # ========== 多轮对话区域 ==========
    st.markdown("---")
    st.markdown("### 💬 继续对话")
    st.caption("您可以继续追问或要求修改，AI将基于已生成的汇报文案进行回答。")
    
    # 初始化对话历史
    chat_key = "report_chat"
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
    report_chat_col1, report_chat_col2, report_chat_col3 = st.columns([6, 1, 1])
    with report_chat_col1:
        report_chat_input = st.text_input(
            "追问或修改要求",
            placeholder="例如：请把解决方案写得更详细一些...",
            key="report_chat_input",
            label_visibility="collapsed"
        )
    with report_chat_col2:
        report_chat_send = st.button("发送", key="report_chat_send", type="primary", use_container_width=True)
    with report_chat_col3:
        if st.button("清空", key="report_chat_clear", use_container_width=True):
            clear_chat_history(chat_key)
            st.rerun()
    
    # 处理对话
    if report_chat_send and report_chat_input.strip():
        add_chat_message(chat_key, "user", report_chat_input)
        
        # 构建上下文
        function_context = f"""【已生成的汇报文案】
{st.session_state.generated_report}"""
        
        history_context = build_chat_context(chat_key, REPORT_ASSISTANT_SYSTEM_PROMPT)
        full_prompt = f"""{function_context}

{history_context}

【当前用户输入】
{report_chat_input}

请基于以上汇报文案和对话历史，回答用户的问题或按要求进行修改。如果用户要求修改，请输出修改后的完整内容。"""
        
        with st.spinner("正在思考..."):
            response_container = st.empty()
            full_response = ""
            for chunk in call_gemini_stream(full_prompt, REPORT_ASSISTANT_SYSTEM_PROMPT):
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
