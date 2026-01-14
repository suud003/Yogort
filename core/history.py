"""
会话历史管理模块
管理用户的聊天记录和下载历史
"""

import streamlit as st
from datetime import datetime
from typing import Optional


def init_session_history():
    """初始化会话历史存储"""
    if "session_history" not in st.session_state:
        st.session_state.session_history = []


def add_to_history(function_type: str, input_data: dict, output_data: str, 
                   download_data: bytes = None, download_filename: str = None,
                   download_mime: str = None):
    """
    添加记录到会话历史
    
    Args:
        function_type: 功能类型（生成策划案/优化策划案/汇报助手/周报助手/白皮书助手）
        input_data: 输入数据字典
        output_data: 输出内容
        download_data: 可下载的文件数据（可选）
        download_filename: 下载文件名（可选）
        download_mime: 文件MIME类型（可选）
    """
    init_session_history()
    
    history_item = {
        "id": len(st.session_state.session_history) + 1,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "function_type": function_type,
        "input_data": input_data,
        "output_data": output_data,
        "download_data": download_data,
        "download_filename": download_filename,
        "download_mime": download_mime
    }
    
    st.session_state.session_history.append(history_item)


def get_history_summary(item: dict) -> str:
    """
    获取历史记录的摘要描述
    
    Args:
        item: 历史记录项
    
    Returns:
        摘要字符串
    """
    func_type = item.get("function_type", "未知")
    input_data = item.get("input_data", {})
    
    # 根据不同功能类型生成不同的摘要
    if func_type == "生成策划案":
        desc = input_data.get("功能描述", "")[:30]
        return f"📝 {desc}..." if len(input_data.get("功能描述", "")) > 30 else f"📝 {desc}"
    elif func_type == "优化策划案":
        return f"🔄 策划案优化"
    elif func_type == "汇报助手":
        problem = input_data.get("当前问题", "")[:20]
        return f"📊 {problem}..." if len(input_data.get("当前问题", "")) > 20 else f"📊 {problem}"
    elif func_type == "周报助手":
        return f"📅 周报生成"
    elif func_type == "白皮书助手":
        keyword = input_data.get("功能关键词", "")
        return f"📖 {keyword}"
    else:
        return f"📄 {func_type}"


def clear_session_history():
    """清空会话历史"""
    st.session_state.session_history = []


def render_history_sidebar():
    """
    在侧边栏渲染会话历史面板
    """
    init_session_history()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📜 会话历史")
    
    history = st.session_state.session_history
    
    if not history:
        st.sidebar.caption("暂无历史记录")
        return
    
    # 显示历史记录数量和清空按钮
    col1, col2 = st.sidebar.columns([2, 1])
    with col1:
        st.caption(f"共 {len(history)} 条记录")
    with col2:
        if st.button("🗑️ 清空", key="clear_history", use_container_width=True):
            clear_session_history()
            st.rerun()
    
    # 倒序显示历史记录（最新的在前）
    for item in reversed(history):
        item_id = item.get("id", 0)
        timestamp = item.get("timestamp", "")
        func_type = item.get("function_type", "")
        summary = get_history_summary(item)
        
        # 使用expander显示每条记录
        with st.sidebar.expander(f"#{item_id} {summary}", expanded=False):
            st.caption(f"🕐 {timestamp}")
            st.caption(f"📌 {func_type}")
            
            # 查看详情按钮
            if st.button("📄 查看详情", key=f"view_{item_id}", use_container_width=True):
                st.session_state.viewing_history_id = item_id
                st.session_state.show_history_detail = True
                st.rerun()
            
            # 如果有下载数据，显示下载按钮
            if item.get("download_data"):
                st.download_button(
                    label="📥 下载",
                    data=item["download_data"],
                    file_name=item.get("download_filename", "download.txt"),
                    mime=item.get("download_mime", "text/plain"),
                    key=f"download_{item_id}",
                    use_container_width=True
                )
