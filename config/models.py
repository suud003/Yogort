"""
模型配置
定义可用的Gemini模型列表和支持的文件类型
"""

# 可用的Gemini模型列表
AVAILABLE_MODELS = [
    "gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.5-pro-exp-03-25",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-live-001",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.0-pro",
]

# 支持文件上传的模型列表（这些模型支持multimodal输入）
FILE_UPLOAD_SUPPORTED_MODELS = [
    "gemini-3-pro-preview",
    "gemini-2.5-pro-preview-06-05",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.5-pro-exp-03-25",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

# 支持的文件类型
SUPPORTED_FILE_TYPES = ["pdf", "docx", "txt", "md"]
