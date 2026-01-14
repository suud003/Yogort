"""
核心模块
包含API调用、对话管理、会话历史等核心功能
"""

from .api import (
    get_gemini_client,
    get_selected_model,
    fetch_available_models,
    call_gemini,
    call_gemini_stream,
    stream_to_container,
    stream_generator,
    is_file_upload_supported
)

from .chat import (
    init_chat_history,
    add_chat_message,
    get_chat_history,
    clear_chat_history,
    build_chat_context,
    render_chat_interface,
    process_chat_message
)

from .history import (
    init_session_history,
    add_to_history,
    get_history_summary,
    clear_session_history,
    render_history_sidebar
)

__all__ = [
    # API
    "get_gemini_client",
    "get_selected_model",
    "fetch_available_models",
    "call_gemini",
    "call_gemini_stream",
    "stream_to_container",
    "stream_generator",
    "is_file_upload_supported",
    # Chat
    "init_chat_history",
    "add_chat_message",
    "get_chat_history",
    "clear_chat_history",
    "build_chat_context",
    "render_chat_interface",
    "process_chat_message",
    # History
    "init_session_history",
    "add_to_history",
    "get_history_summary",
    "clear_session_history",
    "render_history_sidebar"
]
