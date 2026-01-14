"""
游戏策划Agent（酸奶）
基于Gemini API的智能策划辅助工具

主入口文件 - 解耦重构版本
"""

import streamlit as st

# 配置导入
from config.models import AVAILABLE_MODELS, SUPPORTED_FILE_TYPES
from config.prompts import (
    GENERATE_PRD_SYSTEM_PROMPT, INITIAL_FIX_SYSTEM_PROMPT,
    CHECKLIST
)

# 核心模块导入
from core.api import (
    call_gemini_stream, is_file_upload_supported
)
from core.chat import (
    init_chat_history, add_chat_message, get_chat_history,
    clear_chat_history, build_chat_context
)
from core.history import init_session_history, add_to_history

# 工具模块导入
from utils.excel import create_excel_file
from utils.file_parser import extract_text_from_file

# 功能模块导入
from features.generate_prd import generate_prd, ai_self_check
from features.optimize_prd import optimize_prd_initial, reflection_loop
from features.report_assistant import render_report_assistant
from features.weekly_report import render_weekly_report
from features.whitepaper import render_whitepaper_assistant

# UI模块导入
from ui.sidebar import render_sidebar
from ui.components import render_history_detail, render_api_key_warning, render_footer


def init_session_state():
    """初始化所有session_state变量"""
    # 基础状态
    if "generated_prd" not in st.session_state:
        st.session_state.generated_prd = ""
    if "optimized_prd" not in st.session_state:
        st.session_state.optimized_prd = ""
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    
    # 初始化会话历史
    init_session_history()
    
    # 历史详情查看状态
    if "viewing_history_id" not in st.session_state:
        st.session_state.viewing_history_id = None
    if "show_history_detail" not in st.session_state:
        st.session_state.show_history_detail = False
    
    # 尝试从 Streamlit Secrets 获取 API Key（用于云部署）
    default_api_key = ""
    secrets_api_key_loaded = False
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            default_api_key = st.secrets["GOOGLE_API_KEY"]
            secrets_api_key_loaded = True
        elif "GEMINI_API_KEY" in st.secrets:
            default_api_key = st.secrets["GEMINI_API_KEY"]
            secrets_api_key_loaded = True
    except Exception:
        pass
    
    if "api_key" not in st.session_state:
        st.session_state.api_key = default_api_key
    if "secrets_api_key_loaded" not in st.session_state:
        st.session_state.secrets_api_key_loaded = secrets_api_key_loaded
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = AVAILABLE_MODELS[0]
    if "models_list" not in st.session_state:
        st.session_state.models_list = AVAILABLE_MODELS
    if "api_key_validated" not in st.session_state:
        st.session_state.api_key_validated = False
    
    # 中止控制
    if "should_stop" not in st.session_state:
        st.session_state.should_stop = False
    # 错误信息
    if "last_error" not in st.session_state:
        st.session_state.last_error = ""
    # 思考过程
    if "thinking_content" not in st.session_state:
        st.session_state.thinking_content = ""


def render_generate_prd_page():
    """渲染生成策划案页面"""
    st.markdown("### 📝 生成新策划案")
    st.markdown("请输入功能描述，AI将为您生成完整的策划案。")
    
    user_input = st.text_area(
        "功能描述",
        height=300,
        placeholder="请详细描述您要设计的游戏功能...\n\n例如：\n设计一个游戏内的好友系统，包括添加好友、删除好友、好友列表展示、在线状态显示等功能...",
        key="generate_input"
    )
    
    # 文件上传区域
    if is_file_upload_supported():
        upload_col1, upload_col2 = st.columns([2, 1])
        
        with upload_col2:
            uploaded_file = st.file_uploader(
                "📎 上传附件",
                type=SUPPORTED_FILE_TYPES,
                help="上传参考文档供AI参考（PDF/Word/TXT/MD）",
                key="generate_file_uploader"
            )
            
            if uploaded_file is not None:
                if "uploaded_file_content" not in st.session_state or \
                   st.session_state.get("uploaded_file_name") != uploaded_file.name:
                    with st.spinner("解析中..."):
                        file_text = extract_text_from_file(uploaded_file)
                        st.session_state.uploaded_file_content = file_text
                        st.session_state.uploaded_file_name = uploaded_file.name
                
                st.caption(f"✅ {uploaded_file.name}")
                
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("👁️ 预览", key="preview_gen", use_container_width=True):
                        st.session_state.show_preview_gen = not st.session_state.get("show_preview_gen", False)
                with btn_col2:
                    if st.button("🗑️ 清除", key="clear_gen", use_container_width=True):
                        st.session_state.uploaded_file_content = ""
                        st.session_state.uploaded_file_name = ""
                        st.session_state.show_preview_gen = False
                        st.rerun()
                
                if st.session_state.get("show_preview_gen", False):
                    with st.expander("📄 文件内容预览", expanded=True):
                        preview_text = st.session_state.uploaded_file_content
                        if len(preview_text) > 500:
                            st.text(preview_text[:500] + "\n\n... [已截断] ...")
                        else:
                            st.text(preview_text)
        
        with upload_col1:
            if st.session_state.get("uploaded_file_content"):
                st.info(f"📎 已添加附件: **{st.session_state.get('uploaded_file_name', '未知文件')}**")
    else:
        st.caption("💡 当前模型不支持文件上传，如需上传附件请切换至支持的模型")
    
    # 初始化状态
    if "generated_check_result" not in st.session_state:
        st.session_state.generated_check_result = ""
    if "current_stage" not in st.session_state:
        st.session_state.current_stage = "idle"
    
    # 生成按钮
    if st.button("🚀 生成策划案", type="primary", disabled=st.session_state.is_processing):
        if not user_input.strip():
            st.error("请输入功能描述！")
        else:
            st.session_state.is_processing = True
            st.session_state.should_stop = False
            st.session_state.generated_check_result = ""
            st.session_state.generated_prd = ""
            st.session_state.last_error = ""
            st.session_state.current_stage = "generating"
            st.session_state.generate_saved_to_history = False
            st.session_state.saved_user_input = user_input
            st.session_state.saved_attachment_content = st.session_state.get("uploaded_file_content", "")
            st.session_state.saved_attachment_name = st.session_state.get("uploaded_file_name", "")
            st.rerun()
    
    # 处理生成阶段
    if st.session_state.is_processing and st.session_state.current_stage == "generating":
        _handle_prd_generation()
    
    # 处理检查阶段
    elif st.session_state.is_processing and st.session_state.current_stage == "checking":
        _handle_prd_checking()
    
    # 显示已保存的生成结果
    if st.session_state.generated_prd and not st.session_state.is_processing:
        _display_generated_prd()


def _handle_prd_generation():
    """处理策划案生成阶段"""
    user_input_saved = st.session_state.get("saved_user_input", "")
    attachment_content = st.session_state.get("saved_attachment_content", "")
    attachment_name = st.session_state.get("saved_attachment_name", "")
    
    st.markdown("### 📄 生成的策划案")
    
    col_status, col_stop = st.columns([4, 1])
    with col_status:
        st.markdown("**✍️ 策划酸奶正在撰写策划案...**")
    with col_stop:
        if st.button("⏹️ 中止生成", key="stop_generate", type="secondary"):
            st.session_state.should_stop = True
            st.warning("正在中止...")
    
    thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
    with thinking_expander:
        thinking_container = st.empty()
    
    status_container = st.empty()
    
    final_input = user_input_saved
    if attachment_content:
        final_input = f"""【用户功能描述】
{user_input_saved}

【附件内容】（文件名: {attachment_name}）
{attachment_content}

请参考以上功能描述和附件内容，生成完整的策划案。"""
        st.info(f"📎 已包含附件: {attachment_name}")
    
    prd_container = st.empty()
    result, success, error = generate_prd(
        final_input, 
        use_stream=True, 
        container=prd_container,
        thinking_container=thinking_container,
        status_container=status_container
    )
    
    if success and result:
        st.session_state.generated_prd = result
        st.success("✅ 策划案生成完成！")
        st.session_state.current_stage = "checking"
        st.rerun()
    elif error:
        st.error(f"❌ 生成失败: {error}")
        st.session_state.is_processing = False
        st.session_state.current_stage = "idle"
    elif st.session_state.should_stop:
        st.warning("⏹️ 生成已中止")
        if result:
            st.session_state.generated_prd = result
        st.session_state.is_processing = False
        st.session_state.current_stage = "idle"
        st.session_state.should_stop = False
    else:
        st.error("生成失败，请重试")
        st.session_state.is_processing = False
        st.session_state.current_stage = "idle"


def _handle_prd_checking():
    """处理策划案检查阶段"""
    st.markdown("### 📄 生成的策划案")
    st.markdown(st.session_state.generated_prd)
    st.success("✅ 策划案生成完成！")
    
    st.markdown("### 🔍 AI复检清单检查结果")
    
    col_status, col_stop = st.columns([4, 1])
    with col_status:
        st.markdown("**🔍 AI正在进行复检清单检查...**")
    with col_stop:
        if st.button("⏹️ 中止检查", key="stop_check", type="secondary"):
            st.session_state.should_stop = True
            st.warning("正在中止...")
    
    thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
    with thinking_expander:
        thinking_container = st.empty()
    
    status_container = st.empty()
    check_container = st.empty()
    
    check_result, success, error = ai_self_check(
        st.session_state.generated_prd, 
        use_stream=True, 
        container=check_container,
        thinking_container=thinking_container,
        status_container=status_container
    )
    
    if success and check_result:
        st.session_state.generated_check_result = check_result
        st.success("✅ 复检完成！")
    elif error:
        st.error(f"❌ 复检失败: {error}")
    
    st.session_state.is_processing = False
    st.session_state.current_stage = "done"
    st.session_state.should_stop = False
    st.rerun()


def _display_generated_prd():
    """显示已生成的策划案"""
    st.markdown("### 📄 生成的策划案")
    st.markdown(st.session_state.generated_prd)
    
    if st.session_state.generated_check_result:
        st.markdown("### 🔍 AI复检清单检查结果")
        with st.expander("查看详细检查结果", expanded=True):
            st.markdown(st.session_state.generated_check_result)
    
    st.markdown(CHECKLIST)
    
    excel_data = create_excel_file(
        st.session_state.generated_prd,
        st.session_state.generated_check_result
    )
    
    st.download_button(
        label="📥 下载策划案 (Excel)",
        data=excel_data,
        file_name="策划案.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    if st.session_state.get("current_stage") == "done" and not st.session_state.get("generate_saved_to_history"):
        add_to_history(
            function_type="生成策划案",
            input_data={"功能描述": st.session_state.get("saved_user_input", "")},
            output_data=st.session_state.generated_prd,
            download_data=excel_data,
            download_filename="策划案.xlsx",
            download_mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.session_state.generate_saved_to_history = True
    
    # 多轮对话区域
    _render_generate_chat()


def _render_generate_chat():
    """渲染生成策划案的多轮对话区域"""
    st.markdown("---")
    st.markdown("### 💬 继续对话")
    st.caption("您可以继续追问或要求修改，AI将基于已生成的策划案进行回答。")
    
    chat_key = "generate_prd_chat"
    init_chat_history(chat_key)
    
    chat_history = get_chat_history(chat_key)
    if chat_history:
        for msg in chat_history:
            if msg["role"] == "user":
                st.markdown(f"**🧑 用户** _{msg['timestamp']}_")
                st.info(msg["content"])
            else:
                st.markdown(f"**🤖 助手** _{msg['timestamp']}_")
                st.markdown(msg["content"])
    
    chat_col1, chat_col2, chat_col3 = st.columns([6, 1, 1])
    with chat_col1:
        chat_input = st.text_input(
            "追问或修改要求",
            placeholder="例如：请详细说明第3章的验收标准...",
            key="generate_chat_input",
            label_visibility="collapsed"
        )
    with chat_col2:
        chat_send = st.button("发送", key="generate_chat_send", type="primary", use_container_width=True)
    with chat_col3:
        if st.button("清空", key="generate_chat_clear", use_container_width=True):
            clear_chat_history(chat_key)
            st.rerun()
    
    if chat_send and chat_input.strip():
        add_chat_message(chat_key, "user", chat_input)
        
        function_context = f"""【已生成的策划案】
{st.session_state.generated_prd}"""
        
        history_context = build_chat_context(chat_key, GENERATE_PRD_SYSTEM_PROMPT)
        full_prompt = f"""{function_context}

{history_context}

【当前用户输入】
{chat_input}

请基于以上策划案和对话历史，回答用户的问题或按要求进行修改。如果用户要求修改策划案，请输出修改后的完整内容。"""
        
        with st.spinner("正在思考..."):
            response_container = st.empty()
            full_response = ""
            for chunk in call_gemini_stream(full_prompt, GENERATE_PRD_SYSTEM_PROMPT):
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


def render_optimize_prd_page():
    """渲染优化策划案页面"""
    st.markdown("### 🔄 优化现有策划案")
    st.markdown("请输入原策划案和修改意见，AI将通过多轮迭代进行优化。")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        old_prd = st.text_area(
            "原策划案",
            height=400,
            placeholder="请粘贴需要优化的策划案内容...",
            key="optimize_input"
        )
        
        # 文件上传区域
        if is_file_upload_supported():
            opt_upload_col1, opt_upload_col2 = st.columns([2, 1])
            
            with opt_upload_col2:
                uploaded_file_opt = st.file_uploader(
                    "📎 上传附件",
                    type=SUPPORTED_FILE_TYPES,
                    help="上传参考文档供AI参考（PDF/Word/TXT/MD）",
                    key="optimize_file_uploader"
                )
                
                if uploaded_file_opt is not None:
                    if "uploaded_file_content" not in st.session_state or \
                       st.session_state.get("uploaded_file_name") != uploaded_file_opt.name:
                        with st.spinner("解析中..."):
                            file_text = extract_text_from_file(uploaded_file_opt)
                            st.session_state.uploaded_file_content = file_text
                            st.session_state.uploaded_file_name = uploaded_file_opt.name
                    
                    st.caption(f"✅ {uploaded_file_opt.name}")
                    
                    opt_btn_col1, opt_btn_col2 = st.columns(2)
                    with opt_btn_col1:
                        if st.button("👁️ 预览", key="preview_opt", use_container_width=True):
                            st.session_state.show_preview_opt = not st.session_state.get("show_preview_opt", False)
                    with opt_btn_col2:
                        if st.button("🗑️ 清除", key="clear_opt", use_container_width=True):
                            st.session_state.uploaded_file_content = ""
                            st.session_state.uploaded_file_name = ""
                            st.session_state.show_preview_opt = False
                            st.rerun()
                    
                    if st.session_state.get("show_preview_opt", False):
                        with st.expander("📄 文件内容预览", expanded=True):
                            preview_text = st.session_state.uploaded_file_content
                            if len(preview_text) > 500:
                                st.text(preview_text[:500] + "\n\n... [已截断] ...")
                            else:
                                st.text(preview_text)
            
            with opt_upload_col1:
                if st.session_state.get("uploaded_file_content"):
                    st.info(f"📎 已添加附件: **{st.session_state.get('uploaded_file_name', '未知文件')}**")
        else:
            st.caption("💡 当前模型不支持文件上传，如需上传附件请切换至支持的模型")
    
    with col2:
        feedback = st.text_area(
            "修改意见（可选）",
            height=200,
            placeholder="请输入您的修改意见或关注点...",
            key="feedback_input"
        )
        
        max_iterations = st.number_input(
            "迭代轮次",
            min_value=1,
            max_value=10,
            value=3,
            help="设置Reflection循环的迭代次数（1-10轮）"
        )
    
    # 初始化状态
    if "optimize_stage" not in st.session_state:
        st.session_state.optimize_stage = "idle"
    if "initial_fixed_prd" not in st.session_state:
        st.session_state.initial_fixed_prd = ""
    if "saved_old_prd" not in st.session_state:
        st.session_state.saved_old_prd = ""
    if "saved_feedback" not in st.session_state:
        st.session_state.saved_feedback = ""
    if "saved_max_iterations" not in st.session_state:
        st.session_state.saved_max_iterations = 3
    if "optimized_check_result" not in st.session_state:
        st.session_state.optimized_check_result = ""
    
    if st.button("🔄 开始优化", type="primary", disabled=st.session_state.is_processing):
        if not old_prd.strip():
            st.error("请输入原策划案！")
        else:
            st.session_state.is_processing = True
            st.session_state.should_stop = False
            st.session_state.last_error = ""
            st.session_state.optimized_prd = ""
            st.session_state.optimized_check_result = ""
            st.session_state.initial_fixed_prd = ""
            st.session_state.saved_old_prd = old_prd
            st.session_state.saved_feedback = feedback
            st.session_state.saved_max_iterations = max_iterations
            st.session_state.optimize_saved_to_history = False
            st.session_state.saved_optimize_attachment = st.session_state.get("uploaded_file_content", "")
            st.session_state.saved_optimize_attachment_name = st.session_state.get("uploaded_file_name", "")
            st.session_state.optimize_stage = "initial"
            st.rerun()
    
    # 处理各阶段
    if st.session_state.is_processing and st.session_state.optimize_stage == "initial":
        _handle_optimize_initial()
    elif st.session_state.is_processing and st.session_state.optimize_stage == "reflection":
        _handle_optimize_reflection()
    elif st.session_state.is_processing and st.session_state.optimize_stage == "checking":
        _handle_optimize_checking()
    
    # 显示结果
    if st.session_state.optimized_prd and not st.session_state.is_processing:
        _display_optimized_prd()


def _handle_optimize_initial():
    """处理优化策划案初始修正阶段"""
    st.markdown("### 📌 Step 1: 初始修正")
    
    optimize_attachment = st.session_state.get("saved_optimize_attachment", "")
    optimize_attachment_name = st.session_state.get("saved_optimize_attachment_name", "")
    if optimize_attachment:
        st.info(f"📎 参考附件: {optimize_attachment_name}")
    
    col_status, col_stop = st.columns([4, 1])
    with col_status:
        st.markdown("**✏️ 正在进行初始修正...**")
    with col_stop:
        if st.button("⏹️ 中止", key="stop_initial", type="secondary"):
            st.session_state.should_stop = True
            st.warning("正在中止...")
    
    thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
    with thinking_expander:
        thinking_container = st.empty()
    
    status_container = st.empty()
    
    final_feedback = st.session_state.saved_feedback
    if optimize_attachment:
        final_feedback = f"""{st.session_state.saved_feedback if st.session_state.saved_feedback else "无特别意见"}

【附件内容参考】（文件名: {optimize_attachment_name}）
{optimize_attachment}"""
    
    initial_container = st.empty()
    initial_fixed, success, error = optimize_prd_initial(
        st.session_state.saved_old_prd, 
        final_feedback,
        use_stream=True, 
        container=initial_container,
        thinking_container=thinking_container,
        status_container=status_container
    )
    
    if success and initial_fixed:
        st.session_state.initial_fixed_prd = initial_fixed
        st.success("初始修正完成！")
        st.session_state.optimize_stage = "reflection"
        st.rerun()
    elif error:
        st.error(f"❌ 初始修正失败: {error}")
        st.session_state.is_processing = False
        st.session_state.optimize_stage = "idle"
    elif st.session_state.should_stop:
        st.warning("⏹️ 已中止")
        st.session_state.is_processing = False
        st.session_state.optimize_stage = "idle"
        st.session_state.should_stop = False
    else:
        st.error("初始修正失败，请重试")
        st.session_state.is_processing = False
        st.session_state.optimize_stage = "idle"


def _handle_optimize_reflection():
    """处理优化策划案Reflection循环阶段"""
    st.markdown("### 📌 Step 1: 初始修正")
    with st.expander("查看初始修正结果", expanded=False):
        st.markdown(st.session_state.initial_fixed_prd)
    st.success("初始修正完成！")
    st.markdown("---")
    
    st.markdown("### 🔁 Step 2: Reflection 循环优化")
    final_prd, was_stopped = reflection_loop(
        st.session_state.initial_fixed_prd, 
        st.session_state.saved_max_iterations
    )
    
    st.session_state.optimized_prd = final_prd
    
    if was_stopped:
        st.warning("⏹️ 迭代已中止，将使用当前版本进行复检")
        st.session_state.should_stop = False
    
    st.session_state.optimize_stage = "checking"
    st.rerun()


def _handle_optimize_checking():
    """处理优化策划案检查阶段"""
    st.markdown("### 📌 Step 1: 初始修正")
    st.success("初始修正完成！")
    st.markdown("---")
    
    st.markdown("### 🔁 Step 2: Reflection 循环优化")
    st.success(f"完成 {st.session_state.saved_max_iterations} 轮迭代优化！")
    st.markdown("---")
    
    st.markdown("### 🔍 Step 3: AI复检清单检查")
    
    col_status, col_stop = st.columns([4, 1])
    with col_status:
        st.markdown("**🔍 AI正在进行最终复检清单检查...**")
    with col_stop:
        if st.button("⏹️ 中止检查", key="stop_final_check", type="secondary"):
            st.session_state.should_stop = True
            st.warning("正在中止...")
    
    thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
    with thinking_expander:
        thinking_container = st.empty()
    
    status_container = st.empty()
    check_container = st.empty()
    
    check_result, success, error = ai_self_check(
        st.session_state.optimized_prd, 
        use_stream=True, 
        container=check_container,
        thinking_container=thinking_container,
        status_container=status_container
    )
    
    if success and check_result:
        st.session_state.optimized_check_result = check_result
        st.success("✅ 复检完成！")
    elif error:
        st.error(f"❌ 复检失败: {error}")
        st.session_state.optimized_check_result = ""
    else:
        st.session_state.optimized_check_result = ""
    
    st.session_state.is_processing = False
    st.session_state.optimize_stage = "done"
    st.session_state.should_stop = False
    st.success("✅ 策划案优化完成！")
    st.rerun()


def _display_optimized_prd():
    """显示优化后的策划案"""
    st.markdown("### 📄 最终优化后的策划案")
    st.markdown(st.session_state.optimized_prd)
    
    if st.session_state.optimized_check_result:
        st.markdown("### 🔍 AI复检清单检查结果")
        with st.expander("查看详细检查结果", expanded=True):
            st.markdown(st.session_state.optimized_check_result)
    
    st.markdown(CHECKLIST)
    
    excel_data = create_excel_file(
        st.session_state.optimized_prd,
        st.session_state.optimized_check_result
    )
    
    st.download_button(
        label="📥 下载优化后的策划案 (Excel)",
        data=excel_data,
        file_name="优化后的策划案.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    if st.session_state.get("optimize_stage") == "done" and not st.session_state.get("optimize_saved_to_history"):
        add_to_history(
            function_type="优化策划案",
            input_data={
                "原策划案": st.session_state.get("saved_old_prd", "")[:200] + "...",
                "修改意见": st.session_state.get("saved_feedback", ""),
                "迭代轮次": st.session_state.get("saved_max_iterations", 3)
            },
            output_data=st.session_state.optimized_prd,
            download_data=excel_data,
            download_filename="优化后的策划案.xlsx",
            download_mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.session_state.optimize_saved_to_history = True
    
    # 多轮对话区域
    _render_optimize_chat()


def _render_optimize_chat():
    """渲染优化策划案的多轮对话区域"""
    st.markdown("---")
    st.markdown("### 💬 继续对话")
    st.caption("您可以继续追问或要求修改，AI将基于优化后的策划案进行回答。")
    
    chat_key = "optimize_prd_chat"
    init_chat_history(chat_key)
    
    chat_history = get_chat_history(chat_key)
    if chat_history:
        for msg in chat_history:
            if msg["role"] == "user":
                st.markdown(f"**🧑 用户** _{msg['timestamp']}_")
                st.info(msg["content"])
            else:
                st.markdown(f"**🤖 助手** _{msg['timestamp']}_")
                st.markdown(msg["content"])
    
    opt_chat_col1, opt_chat_col2, opt_chat_col3 = st.columns([6, 1, 1])
    with opt_chat_col1:
        opt_chat_input = st.text_input(
            "追问或修改要求",
            placeholder="例如：请补充技术依赖部分的细节...",
            key="optimize_chat_input",
            label_visibility="collapsed"
        )
    with opt_chat_col2:
        opt_chat_send = st.button("发送", key="optimize_chat_send", type="primary", use_container_width=True)
    with opt_chat_col3:
        if st.button("清空", key="optimize_chat_clear", use_container_width=True):
            clear_chat_history(chat_key)
            st.rerun()
    
    if opt_chat_send and opt_chat_input.strip():
        add_chat_message(chat_key, "user", opt_chat_input)
        
        function_context = f"""【优化后的策划案】
{st.session_state.optimized_prd}"""
        
        history_context = build_chat_context(chat_key, INITIAL_FIX_SYSTEM_PROMPT)
        full_prompt = f"""{function_context}

{history_context}

【当前用户输入】
{opt_chat_input}

请基于以上策划案和对话历史，回答用户的问题或按要求进行修改。如果用户要求修改策划案，请输出修改后的完整内容。"""
        
        with st.spinner("正在思考..."):
            response_container = st.empty()
            full_response = ""
            for chunk in call_gemini_stream(full_prompt, INITIAL_FIX_SYSTEM_PROMPT):
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


def main():
    """主函数"""
    # 页面配置
    st.set_page_config(
        page_title="游戏策划Agent（酸奶）",
        page_icon="🎮",
        layout="wide"
    )
    
    # 初始化session_state
    init_session_state()
    
    # 渲染侧边栏
    render_sidebar()
    
    # 主界面标题
    st.title("🎮 游戏策划Agent（酸奶）")
    st.markdown("*基于Gemini API的智能策划辅助工具*")
    st.markdown("---")
    
    # 检查API Key
    if not st.session_state.api_key:
        render_api_key_warning()
        st.stop()
    
    # 渲染历史详情
    render_history_detail()
    
    # 功能选择
    function_mode = st.selectbox(
        "🔧 功能选择",
        options=["生成策划案", "优化策划案", "汇报助手", "周报助手", "白皮书助手"],
        help="选择要使用的功能"
    )
    
    # 根据功能模式渲染对应页面
    if function_mode == "生成策划案":
        render_generate_prd_page()
    elif function_mode == "优化策划案":
        render_optimize_prd_page()
    elif function_mode == "汇报助手":
        render_report_assistant()
    elif function_mode == "周报助手":
        render_weekly_report()
    elif function_mode == "白皮书助手":
        render_whitepaper_assistant()
    
    # 渲染页脚
    render_footer()


if __name__ == "__main__":
    main()
