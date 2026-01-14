"""
优化策划案功能模块
包含Reflection循环优化流程
"""

import streamlit as st

from ..core.api import stream_to_container, call_gemini
from ..config.prompts import (
    INITIAL_FIX_SYSTEM_PROMPT,
    DEVELOPER_REVIEW_PROMPT,
    PLANNER_FIX_PROMPT
)


def optimize_prd_initial(old_prd: str, feedback: str, use_stream: bool = False, 
                         container=None, thinking_container=None, status_container=None) -> tuple:
    """
    优化策划案 - 初始修正（支持流式输出）
    
    Args:
        old_prd: 旧策划案
        feedback: 用户的修改意见
        use_stream: 是否使用流式输出
        container: Streamlit容器对象，用于流式显示
        thinking_container: 用于显示思考过程的容器
        status_container: 用于显示状态信息的容器
    
    Returns:
        tuple: (初步修正后的策划案, 是否成功, 错误信息)
    """
    prompt = f"""【旧策划案】
{old_prd}

【用户修改意见】
{feedback if feedback else "无特别意见，请根据复检清单进行检查和完善"}

请根据复检清单检查旧案，结合用户意见进行修改和填补。"""
    
    if use_stream and container:
        return stream_to_container(prompt, INITIAL_FIX_SYSTEM_PROMPT, container, 
                                   thinking_container, status_container)
    else:
        result = call_gemini(prompt, INITIAL_FIX_SYSTEM_PROMPT)
        return (result, result is not None, st.session_state.last_error if not result else "")


def developer_review(current_prd: str, use_stream: bool = False, container=None, 
                     thinking_container=None, status_container=None) -> tuple:
    """
    开发人员角色审查策划案（支持流式输出）
    
    Args:
        current_prd: 当前版本的策划案
        use_stream: 是否使用流式输出
        container: Streamlit容器对象，用于流式显示
        thinking_container: 用于显示思考过程的容器
        status_container: 用于显示状态信息的容器
    
    Returns:
        tuple: (开发人员提出的问题列表, 是否成功, 错误信息)
    """
    prompt = f"""请审查以下策划案，提出你的问题和疑虑：

{current_prd}"""
    
    if use_stream and container:
        return stream_to_container(prompt, DEVELOPER_REVIEW_PROMPT, container, 
                                   thinking_container, status_container)
    else:
        result = call_gemini(prompt, DEVELOPER_REVIEW_PROMPT)
        return (result, result is not None, st.session_state.last_error if not result else "")


def planner_fix(current_prd: str, dev_questions: str, use_stream: bool = False, 
                container=None, thinking_container=None, status_container=None) -> tuple:
    """
    策划角色根据开发人员问题修改策划案（支持流式输出）
    
    Args:
        current_prd: 当前版本的策划案
        dev_questions: 开发人员提出的问题
        use_stream: 是否使用流式输出
        container: Streamlit容器对象，用于流式显示
        thinking_container: 用于显示思考过程的容器
        status_container: 用于显示状态信息的容器
    
    Returns:
        tuple: (修改后的策划案, 是否成功, 错误信息)
    """
    prompt = f"""【当前策划案】
{current_prd}

【开发人员提出的问题】
{dev_questions}

请针对以上问题修改和完善策划案。"""
    
    if use_stream and container:
        return stream_to_container(prompt, PLANNER_FIX_PROMPT, container, 
                                   thinking_container, status_container)
    else:
        result = call_gemini(prompt, PLANNER_FIX_PROMPT)
        return (result, result is not None, st.session_state.last_error if not result else "")


def reflection_loop(initial_prd: str, max_iterations: int) -> tuple:
    """
    Reflection循环优化策划案（流式输出版本，支持中止）
    
    Args:
        initial_prd: 初始修正后的策划案
        max_iterations: 最大迭代轮次
    
    Returns:
        tuple: (最终优化后的策划案, 是否被中止)
    """
    current_prd = initial_prd
    was_stopped = False
    
    for i in range(max_iterations):
        # 检查是否需要中止
        if st.session_state.should_stop:
            was_stopped = True
            st.warning(f"⏹️ 迭代已在第 {i + 1} 轮前中止")
            break
            
        st.markdown(f"### 🔄 第 {i + 1} 轮迭代")
        
        # 显示中止按钮
        col_status, col_stop = st.columns([4, 1])
        with col_stop:
            if st.button(f"⏹️ 中止迭代", key=f"stop_iteration_{i}", type="secondary"):
                st.session_state.should_stop = True
                st.warning("正在中止...")
        
        # 角色A: 开发人员审查
        with st.expander(f"📋 第 {i + 1} 轮 - 开发人员审查", expanded=True):
            st.markdown("**🔍 开发人员正在审查策划案...**")
            
            # 思考过程展示
            thinking_expander = st.expander("💭 查看思考过程", expanded=False)
            with thinking_expander:
                thinking_container = st.empty()
            
            status_container = st.empty()
            dev_container = st.empty()
            
            dev_questions, success, error = developer_review(
                current_prd, 
                use_stream=True, 
                container=dev_container,
                thinking_container=thinking_container,
                status_container=status_container
            )
            
            if st.session_state.should_stop:
                was_stopped = True
                st.warning("⏹️ 已中止")
                break
                
            if success and dev_questions:
                st.success("审查完成！")
            elif error:
                st.error(f"❌ 审查失败: {error}")
                st.warning("跳过本轮")
                continue
            else:
                st.warning("开发人员审查失败，跳过本轮")
                continue
        
        # 角色B: 策划修改
        with st.expander(f"✏️ 第 {i + 1} 轮 - 策划优化", expanded=True):
            st.markdown("**✏️ 策划酸奶正在优化策划案...**")
            
            # 思考过程展示
            thinking_expander2 = st.expander("💭 查看思考过程", expanded=False)
            with thinking_expander2:
                thinking_container2 = st.empty()
            
            status_container2 = st.empty()
            fix_container = st.empty()
            
            updated_prd, success, error = planner_fix(
                current_prd, 
                dev_questions, 
                use_stream=True, 
                container=fix_container,
                thinking_container=thinking_container2,
                status_container=status_container2
            )
            
            if st.session_state.should_stop:
                was_stopped = True
                st.warning("⏹️ 已中止")
                break
                
            if success and updated_prd:
                current_prd = updated_prd
                st.success(f"第 {i + 1} 轮优化完成！")
            elif error:
                st.error(f"❌ 优化失败: {error}")
                st.warning("保持当前版本")
            else:
                st.warning("策划优化失败，保持当前版本")
        
        st.markdown("---")
    
    return (current_prd, was_stopped)
