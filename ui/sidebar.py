"""
侧边栏UI模块
处理API配置、模型选择等侧边栏界面
"""

import streamlit as st

from ..config.models import AVAILABLE_MODELS
from ..core.api import fetch_available_models
from ..core.history import render_history_sidebar


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("⚙️ API 配置")
        
        # 如果从 Secrets 加载了 API Key，显示提示
        if st.session_state.secrets_api_key_loaded and st.session_state.api_key:
            st.success("🔐 已从云端配置加载 API Key")
            # 显示隐藏的 API Key 状态
            st.text_input(
                "🔑 Gemini API Key",
                type="password",
                value="********（云端配置）",
                disabled=True,
                help="API Key 已从 Streamlit Secrets 自动加载"
            )
            # 提供手动覆盖选项
            with st.expander("✏️ 使用自定义 API Key"):
                custom_api_key = st.text_input(
                    "输入自定义 API Key",
                    type="password",
                    placeholder="留空则使用云端配置的 Key",
                    help="如需使用自己的 API Key，请在此输入"
                )
                if custom_api_key:
                    st.session_state.api_key = custom_api_key
                    st.session_state.secrets_api_key_loaded = False
                    st.session_state.api_key_validated = False
                    st.rerun()
            api_key_input = st.session_state.api_key
        else:
            # 手动输入 API Key
            api_key_input = st.text_input(
                "🔑 Gemini API Key",
                type="password",
                value=st.session_state.api_key,
                placeholder="请输入您的 Gemini API Key",
                help="请前往 Google AI Studio 获取 API Key: https://aistudio.google.com/apikey"
            )
            
            # 检测API Key变化
            if api_key_input != st.session_state.api_key:
                st.session_state.api_key = api_key_input
                st.session_state.api_key_validated = False
                st.session_state.models_list = AVAILABLE_MODELS
        
        # 验证并获取模型列表按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 验证 & 刷新模型", disabled=not api_key_input):
                if api_key_input:
                    with st.spinner("正在验证API Key并获取模型列表..."):
                        models = fetch_available_models()
                        if models:
                            st.session_state.models_list = models
                            st.session_state.api_key_validated = True
                            st.success(f"✅ 验证成功！获取到 {len(models)} 个可用模型")
                        else:
                            st.error("❌ API Key 无效或无法获取模型列表")
                            st.session_state.api_key_validated = False
        
        with col2:
            if st.session_state.api_key_validated:
                st.markdown("✅ 已验证")
            elif api_key_input:
                st.markdown("⚠️ 未验证")
        
        # 云端部署提示
        if st.session_state.secrets_api_key_loaded:
            st.caption("💡 云端部署模式：API Key 已安全存储")
        
        st.markdown("---")
        
        # 模型选择
        st.subheader("🤖 模型选择")
        
        # 模型下拉选择框
        selected_model = st.selectbox(
            "选择模型",
            options=st.session_state.models_list,
            index=0 if st.session_state.selected_model not in st.session_state.models_list 
                  else st.session_state.models_list.index(st.session_state.selected_model),
            help="选择要使用的 Gemini 模型"
        )
        st.session_state.selected_model = selected_model
        
        # 显示当前选择的模型
        st.info(f"当前模型: **{selected_model}**")
        
        st.markdown("---")
        
        # 帮助信息
        with st.expander("📖 使用帮助"):
            st.markdown("""
            **如何获取 API Key：**
            1. 访问 [Google AI Studio](https://aistudio.google.com/apikey)
            2. 登录您的 Google 账号
            3. 点击 "Create API Key" 创建密钥
            4. 复制密钥并粘贴到上方输入框
            
            **模型说明：**
            - `gemini-2.5-*`: 最新一代模型，能力最强
            - `gemini-2.0-flash`: 速度快，适合大多数场景
            - `gemini-1.5-pro`: 上一代Pro模型，稳定可靠
            - `gemini-1.5-flash`: 轻量快速模型
            
            **注意事项：**
            - 点击"验证 & 刷新模型"可获取最新的可用模型列表
            - 不同模型的能力和响应速度有所不同
            - API Key 仅存储在本地浏览器会话中
            
            **云端部署（Streamlit Cloud）：**
            - 支持通过 Secrets 安全配置 API Key
            - 在 Streamlit Cloud 的 Settings → Secrets 中添加：
            ```
            GOOGLE_API_KEY = "your-api-key"
            ```
            - 本地开发时，可在项目根目录创建 `.streamlit/secrets.toml`
            """)
        
        st.markdown("---")
        st.caption("Powered by Google Gemini API")
        
        # 渲染会话历史侧边栏
        render_history_sidebar()
