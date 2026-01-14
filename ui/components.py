"""
通用UI组件模块
"""

import streamlit as st


def render_history_detail():
    """渲染历史详情查看区域"""
    if not st.session_state.get("show_history_detail") or not st.session_state.get("viewing_history_id"):
        return
    
    history_id = st.session_state.viewing_history_id
    # 查找对应的历史记录
    history_item = None
    for item in st.session_state.session_history:
        if item.get("id") == history_id:
            history_item = item
            break
    
    if not history_item:
        return
    
    st.markdown("---")
    st.markdown(f"### 📜 历史记录详情 #{history_id}")
    
    # 关闭按钮
    if st.button("❌ 关闭详情", key="close_history_detail"):
        st.session_state.show_history_detail = False
        st.session_state.viewing_history_id = None
        st.rerun()
    
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.markdown(f"**功能类型：** {history_item.get('function_type', '未知')}")
    with col_info2:
        st.markdown(f"**生成时间：** {history_item.get('timestamp', '未知')}")
    
    # 显示输入数据
    with st.expander("📥 输入内容", expanded=False):
        input_data = history_item.get("input_data", {})
        for key, value in input_data.items():
            st.markdown(f"**{key}：**")
            st.text(str(value)[:500] + ("..." if len(str(value)) > 500 else ""))
    
    # 显示输出数据
    with st.expander("📤 输出内容", expanded=True):
        st.markdown(history_item.get("output_data", ""))
    
    # 下载按钮
    if history_item.get("download_data"):
        st.download_button(
            label=f"📥 下载 {history_item.get('download_filename', '文件')}",
            data=history_item["download_data"],
            file_name=history_item.get("download_filename", "download.txt"),
            mime=history_item.get("download_mime", "text/plain"),
            key=f"history_download_{history_id}"
        )
    
    st.markdown("---")


def render_api_key_warning():
    """渲染API Key缺失警告"""
    st.warning("⚠️ 请在左侧侧边栏配置 API Key 后使用本工具")
    st.info("👈 点击左侧侧边栏输入您的 Gemini API Key")
    
    # 显示快速指南
    with st.expander("🚀 快速开始指南", expanded=True):
        st.markdown("""
        ### 第一步：获取 API Key
        1. 访问 [Google AI Studio](https://aistudio.google.com/apikey)
        2. 使用 Google 账号登录
        3. 点击 "Create API Key" 按钮
        4. 复制生成的 API Key
        
        ### 第二步：配置工具
        1. 在左侧侧边栏的 "API Key" 输入框中粘贴您的密钥
        2. 点击 "验证 & 刷新模型" 按钮验证密钥
        3. 选择您想要使用的模型
        
        ### 第三步：开始使用
        - **生成策划案**：输入功能描述，AI将生成完整的策划案
        - **优化策划案**：输入现有策划案，AI将通过多轮迭代优化
        - **汇报助手**：将工作信息转化为结构化汇报文案
        """)


def render_footer():
    """渲染页脚"""
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "🎮 游戏策划Agent（酸奶） | Powered by Gemini API"
        "</div>",
        unsafe_allow_html=True
    )
