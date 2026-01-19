"""
游戏策划Agent（酸奶）
基于Gemini API的智能策划辅助工具
"""

import streamlit as st
from google import genai
from google.genai import types
from typing import Optional, Generator
import io
import re
import time
import tempfile
import base64
import json
import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
import PyPDF2
import docx

# ============================================
# 可用的Gemini模型列表
# ============================================
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

# ============================================
# 系统提示词配置
# ============================================

# 生成策划案的System Prompt
GENERATE_PRD_SYSTEM_PROMPT = """你是资深游戏策划"酸奶"。

【回复语言】
- 请始终使用中文进行回答和输出

【语言约束】
- 严禁在正文中使用英文（代码变量除外）
- 不需要AI生成的功能用英文解释（例如不要写 "Feature Overview"，必须写 "功能概述"）
- 所有标题、内容必须使用中文

【格式约束】
- 标题层级严格使用简单的数字格式（如 1、2、3... 或 1.1、1.2...）
- 不要使用 Markdown 的 # 符号或英文字母作为标题索引
- 保持文档结构清晰整洁

【内容结构】
你必须按照以下10个章节来撰写策划案：

1、功能概述（一句话说清做什么）
2、战略定位（解决什么问题，为谁解决）
3、用户场景（具体使用流程和触发点）
4、功能规格（详细的功能点和交互）
5、AI处理逻辑（模型调用、数据处理流程）
6、容错设计（出错时的体验保障）
7、验收标准（如何判断功能成功）
8、能力边界（明确什么不能做）
9、技术依赖（需要的技术资源和接口）
10、版本规划（分阶段实施计划）

【时间信息】
当前日期：{current_date}

请根据用户提供的功能描述，生成完整、专业的策划案。创建日期请使用上述当前日期。"""

# 思维脑图解析的System Prompt
MINDMAP_PARSE_SYSTEM_PROMPT = """你是一个专业的思维脑图解析专家。

【回复语言】
- 请始终使用中文进行回答和输出

【任务】
请仔细分析用户上传的思维脑图图片，识别出其中的所有节点和层级关系，并将其转换为结构化的文本格式。

【输出格式要求】
- 使用数字层级格式表示节点关系（如 1、1.1、1.1.1）
- 根节点/中心主题作为一级标题
- 分支节点依次作为二级、三级标题
- 叶子节点作为最底层内容
- 保留原始脑图中的所有文字信息
- 如果有连接线或箭头表示的关系，请在相应节点后说明

【输出示例】
功能名称：好友系统

1、核心功能
1.1、添加好友
1.1.1、搜索添加
1.1.2、扫码添加
1.1.3、推荐添加
1.2、好友管理
1.2.1、删除好友
1.2.2、设置备注
1.2.3、屏蔽好友

2、社交互动
2.1、私聊功能
2.2、组队邀请
2.3、礼物赠送

请严格按照图片内容进行解析，不要添加图片中没有的内容。"""

# 基于脑图结构生成策划案的System Prompt
MINDMAP_TO_PRD_SYSTEM_PROMPT = """你是资深游戏策划"酸奶"。

【回复语言】
- 请始终使用中文进行回答和输出

【任务】
根据用户提供的思维脑图结构（已解析为文本格式），生成完整的策划案文档。

【语言约束】
- 严禁在正文中使用英文（代码变量除外）
- 不需要AI生成的功能用英文解释（例如不要写 "Feature Overview"，必须写 "功能概述"）
- 所有标题、内容必须使用中文

【格式约束】
- 标题层级严格使用简单的数字格式（如 1、2、3... 或 1.1、1.2...）
- 不要使用 Markdown 的 # 符号或英文字母作为标题索引
- 保持文档结构清晰整洁

【内容结构】
你必须按照以下10个章节来撰写策划案，同时要充分利用脑图中的结构信息：

1、功能概述（一句话说清做什么，基于脑图的中心主题）
2、战略定位（解决什么问题，为谁解决）
3、用户场景（具体使用流程和触发点）
4、功能规格（详细的功能点和交互，参考脑图的分支结构）
5、AI处理逻辑（模型调用、数据处理流程，如适用）
6、容错设计（出错时的体验保障）
7、验收标准（如何判断功能成功）
8、能力边界（明确什么不能做）
9、技术依赖（需要的技术资源和接口）
10、版本规划（分阶段实施计划，可参考脑图的优先级分组）

【时间信息】
当前日期：{current_date}

请根据思维脑图的结构，生成完整、专业的策划案。确保策划案内容与脑图结构保持一致，同时补充脑图中未涉及但策划案必须包含的内容。创建日期请使用上述当前日期。"""

# 初始修正的System Prompt
INITIAL_FIX_SYSTEM_PROMPT = """你是资深游戏策划"酸奶"。

【回复语言】
- 请始终使用中文进行回答和输出

请根据用户提供的旧策划案和修改意见，基于以下复检清单进行检查和修改：

【复检清单】
1. 是否用一句话说清功能核心？
2. 是否明确定义目标用户和使用场景？
3. 是否描述清楚用户触发路径？
4. 是否定义输入要求（格式、限制）？
5. 是否说明AI处理逻辑（模型、流程）？
6. 是否定义输出格式（是否可编辑）？
7. 是否设计用户体验流转（修改、重试）？
8. 是否设定量化验收标准？
9. 是否声明能力边界？
10. 是否列出技术依赖？

【语言约束】
- 严禁在正文中使用英文（代码变量除外）
- 所有标题、内容必须使用中文

【格式约束】
- 标题层级严格使用简单的数字格式（如 1、2、3... 或 1.1、1.2...）
- 不要使用 Markdown 的 # 符号或英文字母作为标题索引

请修改并完善策划案。"""

# 开发人员审查的System Prompt
DEVELOPER_REVIEW_PROMPT = """你是一个挑剔的高级开发人员。

【回复语言】
- 请始终使用中文进行回答和输出

请阅读当前的策划案，提出尖锐的问题，指出逻辑漏洞、缺少的技术细节或不明确的边缘情况。

请只列出问题，不要修改文档。

问题格式要求：
- 使用数字编号列出问题
- 每个问题要具体、明确
- 聚焦于技术可行性、逻辑完整性、边界情况处理"""

# 策划修改的System Prompt
PLANNER_FIX_PROMPT = """你是策划酸奶。

【回复语言】
- 请始终使用中文进行回答和输出

根据开发人员提出的以下问题，对策划案进行修改、补充和完善。

【语言约束】
- 严禁在正文中使用英文（代码变量除外）
- 所有标题、内容必须使用中文

【格式约束】
- 保持原有的文档结构
- 标题层级严格使用简单的数字格式（如 1、2、3... 或 1.1、1.2...）
- 不要使用 Markdown 的 # 符号或英文字母作为标题索引

请针对开发人员的问题，逐一回应并修改策划案。"""

# 复检清单
CHECKLIST = """
---
**【复检清单】**

□ 1. 是否用一句话说清功能核心？
□ 2. 是否明确定义目标用户和使用场景？
□ 3. 是否描述清楚用户触发路径？
□ 4. 是否定义输入要求（格式、限制）？
□ 5. 是否说明AI处理逻辑（模型、流程）？
□ 6. 是否定义输出格式（是否可编辑）？
□ 7. 是否设计用户体验流转（修改、重试）？
□ 8. 是否设定量化验收标准？
□ 9. 是否声明能力边界？
□ 10. 是否列出技术依赖？
"""

def get_system_prompt_with_date(prompt_template: str) -> str:
    """
    将系统提示词中的日期占位符替换为当前日期
    
    Args:
        prompt_template: 包含 {current_date} 占位符的系统提示词模板
    
    Returns:
        str: 替换后的系统提示词
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    return prompt_template.replace("{current_date}", current_date)

# 汇报助手的System Prompt
REPORT_ASSISTANT_SYSTEM_PROMPT = """# Role: 资深职场沟通专家

# 回复语言:
请始终使用中文进行回答和输出

# Profile:
你是一位擅长"向上管理"和"结构化表达"的职场助理。你能够将碎片化的工作信息转化为逻辑清晰、简明扼要、重点突出的汇报文案，专门用于向领导同步工作事项。

# Goals:
根据用户提供的【当前问题】、【解决方案】和【预期结果】，撰写一份给领导查看的工作同步文案。

# Constraints & Guidelines:
1. **结构清晰**：采用"结论先行"或"背景-行动-结果"的逻辑结构。
2. **简明扼要**：去除冗余的修饰词，用词精准，避免过于口语化，但要通俗易懂。
3. **逻辑通顺**：清晰地阐述前因后果，让领导一眼就能看懂为什么要这么做，以及这么做的好处。
4. **格式规范**：适当使用分段、加粗或列表，提升阅读体验。
5. **数学公式**：如果输入中包含数据计算或公式，请使用 $ 或 $$ 包裹公式。

# Output Template (请严格参考此模板风格):

**【主题】：关于[核心事项]的同步/汇报**

**1. 现状与问题（Why）**
简述当前背景，指出核心痛点。[当前问题]

**2. 解决方案（How）**
针对上述问题，拟定/采取以下措施：
*   [解决方案的关键点1]
*   [解决方案的关键点2]

**3. 预期效果（What）**
方案实施后，预计达到以下目标：
*   [预期结果]
"""

# 周报助手的System Prompt
WEEKLY_REPORT_SYSTEM_PROMPT = """Role: 你是一位资深的项目管理专家和运营分析师，擅长将零散的日常工作记录（日报）汇总、提炼并重构为逻辑清晰、重点突出的专业周报。

回复语言: 请始终使用中文进行回答和输出

Task: 请根据我提供的【本周日报/工作记录】，参考【目标风格范例】，生成一份高质量的周报。

Constraints & Formatting Rules (重要):
1. 纯文本格式：请不要使用任何 LaTeX 格式（如 $$ 或 $）。所有的数字、百分比、版本号直接使用普通文本显示（例如：-2%、35%、V420、1->5）。
2. 结构复刻：必须严格遵守范例的层级结构。
   - 一级标题使用 【标题】 格式（例如：【热门特辑：方向与机制对齐】）。
   - 二级要点使用 ○关键词： 格式（例如：○方向对齐：...）。
3. 内容提炼：
   - 去重与合并：不要按"周一、周二"的时间流水账罗列。请将同一事项在不同日期的进展合并为一个条目，只保留最终结果或关键节点。
   - 分类归纳：将内容按业务属性分类（如：策略调整、功能迭代、运营配置、审核流程、数据分析等）。
4. 语言风格：
   - 专业、精炼、客观。
   - 多用动词名词搭配（如"完成对齐"、"明确逻辑"、"修复漏洞"）。
   - 解释因果关系（如"为了缓解固化...调整了..."）。

Reference Example (目标风格范例):

【热门特辑：方向与机制对齐】
○方向对齐： 完成内部与发行会议对齐，明确"特辑"分类来源逻辑，讨论配套H5鉴赏团机制，结合市场侧网红流量及作者主页增加曝光
○特辑来源： 时效驱动（跟热点）、版本驱动（跟版本内容/IP）、兴趣驱动（跟玩家喜好），目标打造"每周必玩的限时派对"；第一期计划锁定"历史好图"圈定小主题
○展示机制： 确定使用MAB算法，单次展示少量作品，通过动态轮播保证池内作品的曝光机会

【推荐算法策略调整】
○缓解固化： 分析头部固化问题，调整混排增加"热门趋势"多样性；分析"猜你喜欢"的集中曝光问题，新的双塔召回虽转化率微降（-2%），但头部效果有非常明显的改善
○质量筛选： 新增平均对局时长的准入筛选条件，提高作品增长速度的权重，相对更优先推荐快速崛起的新内容

【标签与审核流程优化】
○阈值调整： 提高人审举报阈值（1→5），减少误报干扰
○流程优化： 修复作品更新后，没有重新进入审核的问题；发现部分作者利用高频更新，短暂绕过标签流程，已报备11月26日Patch修复该漏洞
"""

# 白皮书助手的System Prompt
WHITEPAPER_ASSISTANT_SYSTEM_PROMPT = """# Role: PUBGM WoW模式 版本文档撰写助理

# 回复语言:
请始终使用中文进行回答和输出

# Context:
你正在协助整理PUBGM WoW模式（UGC玩法）的版本白皮书功能列表。用户会输入简单的功能关键词或短语，你需要将其扩写成一句标准、专业且信息量完整的版本功能陈述。

# Goal:
将简短的关键词扩写为标准的"功能点陈述句"。

# Output Rules (Strict):
1.  **句式结构**：请严格套用以下句式进行扩写：
    `[序号]. 新增[功能名称]功能，支持[具体机制/操作方式]，用于[应用场景/关联的设备或系统]。`
2.  **专业性**：使用PUBGM WoW模式的常用术语（如：可视化编程、自定义UI、全局变量、互动物体、武装AI等）。
3.  **简洁性**：不要使用感叹号，不要发表评论，不要使用"快来试试"等营销词汇。只陈述事实。
4.  **数学公式**：如果涉及数值逻辑，请使用 LaTeX 格式，例如 $y=x+1$。

# Input Example:
用户输入：动画生成
输出：1. 新增动画生成功能，支持作者上传视频后生成对应骨骼动画，用于可视化编程控制武装AI和虚拟投影装置。

用户输入：自定义UI
输出：1. 新增自定义UI编辑器，支持创作者自由拖拽按钮与图片布局，用于制作个性化的游戏界面与交互菜单。

# Workflow:
1.  分析用户输入的关键词。
2.  联想该功能在PUBGM WoW中的实际运作逻辑（机制）和用途（场景）。
3.  按照规定句式输出。
"""

# ============================================
# 会话历史管理
# ============================================

# 历史记录存储目录
HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_histories")

def get_user_id() -> str:
    """
    获取或生成用户唯一ID
    
    Returns:
        用户唯一ID字符串
    """
    import uuid
    if "user_id" not in st.session_state:
        # 生成一个新的用户ID
        st.session_state.user_id = str(uuid.uuid4())[:8]
    return st.session_state.user_id

def get_user_history_path() -> str:
    """
    获取当前用户的历史记录文件路径
    
    Returns:
        用户历史记录文件的完整路径
    """
    user_id = get_user_id()
    # 确保目录存在
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
    return os.path.join(HISTORY_DIR, f"history_{user_id}.json")

def load_history_from_file() -> list:
    """
    从本地文件加载会话历史
    
    Returns:
        历史记录列表
    """
    try:
        history_path = get_user_history_path()
        if os.path.exists(history_path):
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"加载历史记录失败: {e}")
    return []

def save_history_to_file(history: list):
    """
    保存会话历史到本地文件
    
    Args:
        history: 历史记录列表
    """
    try:
        history_path = get_user_history_path()
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"保存历史记录失败: {e}")

def get_download_data(item: dict) -> bytes:
    """
    获取历史记录中的下载数据，处理base64解码
    
    Args:
        item: 历史记录项
    
    Returns:
        解码后的二进制数据，如果没有则返回None
    """
    download_data = item.get("download_data")
    if download_data:
        # 如果是字符串（base64编码），则解码
        if isinstance(download_data, str):
            try:
                return base64.b64decode(download_data)
            except Exception:
                return download_data.encode('utf-8')
        # 如果已经是bytes，直接返回
        return download_data
    return None

def init_session_history():
    """初始化会话历史存储，从本地文件加载"""
    if "session_history" not in st.session_state:
        # 从本地文件加载历史记录
        st.session_state.session_history = load_history_from_file()


# ============================================
# 多轮对话管理
# ============================================

def init_chat_history(chat_key: str):
    """
    初始化指定功能的对话历史
    
    Args:
        chat_key: 对话历史的键名（如 'generate_chat', 'report_chat' 等）
    """
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

def add_chat_message(chat_key: str, role: str, content: str):
    """
    添加消息到对话历史
    
    Args:
        chat_key: 对话历史的键名
        role: 角色（'user' 或 'assistant'）
        content: 消息内容
    """
    init_chat_history(chat_key)
    st.session_state[chat_key].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

def get_chat_history(chat_key: str) -> list:
    """
    获取对话历史
    
    Args:
        chat_key: 对话历史的键名
    
    Returns:
        对话历史列表
    """
    init_chat_history(chat_key)
    return st.session_state[chat_key]

def clear_chat_history(chat_key: str):
    """
    清空对话历史
    
    Args:
        chat_key: 对话历史的键名
    """
    st.session_state[chat_key] = []

def clear_module_session(module_name: str):
    """
    清空指定模块的所有会话数据
    
    Args:
        module_name: 模块名称
    """
    if module_name == "生成策划案":
        st.session_state.generated_prd = ""
        st.session_state.uploaded_file_content = ""
        st.session_state.uploaded_file_name = ""
        st.session_state.show_preview_gen = False
        st.session_state.generated_check_result = ""
        st.session_state.current_stage = "idle"
        st.session_state.generate_saved_to_history = False
        clear_chat_history("generate_prd_chat")
    elif module_name == "脑图生成策划案":
        st.session_state.mindmap_parsed_structure = None
        st.session_state.mindmap_generated_prd = None
        st.session_state.mindmap_image_data = None
        st.session_state.mindmap_saved = False
        st.session_state.mindmap_mermaid_code = ""
        st.session_state.mindmap_input_mode = "图片上传"
        clear_chat_history("mindmap_prd_chat")
    elif module_name == "优化策划案":
        st.session_state.optimized_prd = ""
        st.session_state.optimize_saved_to_history = False
        clear_chat_history("optimize_prd_chat")
    elif module_name == "汇报助手":
        if "generated_report" in st.session_state:
            st.session_state.generated_report = ""
        if "report_saved_to_history" in st.session_state:
            st.session_state.report_saved_to_history = False
        clear_chat_history("report_chat")
    elif module_name == "周报助手":
        if "generated_weekly_report" in st.session_state:
            st.session_state.generated_weekly_report = ""
        if "weekly_saved_to_history" in st.session_state:
            st.session_state.weekly_saved_to_history = False
        clear_chat_history("weekly_chat")
    elif module_name == "白皮书助手":
        if "generated_feature_desc" in st.session_state:
            st.session_state.generated_feature_desc = ""
        if "whitepaper_saved_to_history" in st.session_state:
            st.session_state.whitepaper_saved_to_history = False
        clear_chat_history("whitepaper_chat")
    elif module_name == "游戏策划(lina)":
        st.session_state.lina_chat_history = []
        st.session_state.lina_is_processing = False
    elif module_name == "表格处理助手":
        st.session_state.table_dataframes = {}
        st.session_state.table_selected_dfs = []
        st.session_state.table_result_df = None
        st.session_state.table_is_processing = False
        st.session_state.table_uploaded_files_info = {}
    elif module_name == "思路引导助手 (linmo)":
        st.session_state.linmo_chat_history = []
        st.session_state.linmo_is_processing = False
        st.session_state.linmo_input_key_counter = st.session_state.get("linmo_input_key_counter", 0) + 1
    elif module_name == "PUBGM WoW 玩法评审":
        st.session_state.wow_review_result = ""
        st.session_state.wow_is_processing = False
        st.session_state.wow_uploaded_video = None

def build_chat_context(chat_key: str, system_prompt: str, max_history: int = 10) -> str:
    """
    构建包含对话历史的上下文Prompt
    
    Args:
        chat_key: 对话历史的键名
        system_prompt: 系统提示词
        max_history: 最大历史消息数量
    
    Returns:
        包含历史上下文的完整Prompt
    """
    history = get_chat_history(chat_key)
    
    if not history:
        return ""
    
    # 只取最近的N条历史
    recent_history = history[-max_history:] if len(history) > max_history else history
    
    # 构建对话历史文本
    history_text = "\n\n【对话历史】\n"
    for msg in recent_history:
        role_label = "用户" if msg["role"] == "user" else "助手"
        history_text += f"{role_label}: {msg['content']}\n\n"
    
    return history_text

def render_chat_interface(chat_key: str, system_prompt: str, container, 
                          placeholder: str = "请输入您的问题或修改要求...",
                          function_context: str = ""):
    """
    渲染多轮对话界面
    
    Args:
        chat_key: 对话历史的键名
        system_prompt: 系统提示词
        container: Streamlit容器
        placeholder: 输入框占位文本
        function_context: 当前功能的上下文（如已生成的内容）
    
    Returns:
        是否有新的对话产生
    """
    init_chat_history(chat_key)
    history = get_chat_history(chat_key)
    
    # 显示对话历史 - 使用 ChatGPT 风格的对话气泡
    if history:
        with container:
            st.markdown("#### 💬 对话历史")
            for i, msg in enumerate(history):
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.markdown(msg["content"])
                else:
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(msg["content"])
    
    # 用于控制对话输入的状态
    chat_input_key = f"{chat_key}_input"
    chat_processing_key = f"{chat_key}_processing"
    
    if chat_processing_key not in st.session_state:
        st.session_state[chat_processing_key] = False
    
    # 对话输入区域 - 使用 chat_input
    chat_input_value = container.chat_input(
        placeholder=placeholder,
        key=chat_input_key
    )
    
    # 清空按钮
    if container.button("🗑️ 清空对话历史", key=f"{chat_key}_clear", use_container_width=False):
        clear_chat_history(chat_key)
        st.rerun()
    
    # 处理用户输入
    if chat_input_value and chat_input_value.strip() and not st.session_state[chat_processing_key]:
        pass  # 实际处理逻辑在各模块中实现

def process_chat_message(chat_key: str, user_message: str, system_prompt: str,
                         function_context: str, output_container):
    """
    处理用户的对话消息并生成回复
    
    Args:
        chat_key: 对话历史的键名
        user_message: 用户消息
        system_prompt: 系统提示词
        function_context: 当前功能的上下文
        output_container: 输出容器
    
    Returns:
        生成的回复内容
    """
    # 添加用户消息到历史
    add_chat_message(chat_key, "user", user_message)
    
    # 构建完整的Prompt
    history_context = build_chat_context(chat_key, system_prompt)
    
    full_prompt = f"""{function_context}

{history_context}

【当前用户输入】
{user_message}

请基于以上上下文和对话历史，回答用户的问题或按要求进行修改。"""
    
    # 调用API生成回复
    full_response = ""
    was_stopped = False
    has_error = False
    error_message = ""
    
    for chunk in call_gemini_stream(full_prompt, system_prompt):
        if st.session_state.should_stop:
            was_stopped = True
            break
        
        if chunk["type"] == "text":
            full_response += chunk["content"]
            output_container.markdown(full_response + "▌")
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
        return None, error_message
    elif was_stopped:
        if full_response:
            add_chat_message(chat_key, "assistant", full_response)
        return full_response, "已中止"
    else:
        add_chat_message(chat_key, "assistant", full_response)
        return full_response, None

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
        # 将二进制数据转为base64字符串以便存储到JSON
        "download_data": base64.b64encode(download_data).decode('utf-8') if download_data else None,
        "download_filename": download_filename,
        "download_mime": download_mime
    }
    
    st.session_state.session_history.append(history_item)
    
    # 保存到本地文件
    save_history_to_file(st.session_state.session_history)

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
    # 同时清空本地文件
    save_history_to_file([])

def render_history_sidebar():
    """
    在侧边栏渲染会话历史面板
    """
    init_session_history()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📜 会话历史")
    
    # 显示用户ID和历史文件信息
    user_id = get_user_id()
    history_path = get_user_history_path()
    
    # 用户信息显示区
    st.sidebar.caption(f"🆔 您的用户ID: `{user_id}`")
    
    # 下载按钮放在最显眼位置
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                history_content = f.read()
            st.sidebar.download_button(
                label="💾 下载我的历史记录",
                data=history_content,
                file_name=f"history_{user_id}.json",
                mime="application/json",
                key="download_history_file",
                use_container_width=True
            )
        except Exception as e:
            st.sidebar.error(f"读取文件失败: {e}")
    else:
        st.sidebar.caption("📝 暂无历史记录可下载")
    
    # 存储信息折叠面板
    with st.sidebar.expander("📁 存储信息详情", expanded=False):
        st.caption(f"📂 **存储文件**: `history_{user_id}.json`")
        st.caption(f"📍 **存储目录**: `{HISTORY_DIR}`")
        st.info("💡 刷新页面会生成新的用户ID，建议及时下载备份历史记录")
    
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
                    data=get_download_data(item),
                    file_name=item.get("download_filename", "download.txt"),
                    mime=item.get("download_mime", "text/plain"),
                    key=f"download_{item_id}",
                    use_container_width=True
                )


# AI自检的System Prompt
SELF_CHECK_SYSTEM_PROMPT = """你是资深游戏策划"酸奶"，正在对策划案进行复检清单检查。

【回复语言】
- 请始终使用中文进行回答和输出

请根据以下10项复检清单，逐一检查策划案的完整性和规范性：

【复检清单】
1. 是否用一句话说清功能核心？
2. 是否明确定义目标用户和使用场景？
3. 是否描述清楚用户触发路径？
4. 是否定义输入要求（格式、限制）？
5. 是否说明AI处理逻辑（模型、流程）？
6. 是否定义输出格式（是否可编辑）？
7. 是否设计用户体验流转（修改、重试）？
8. 是否设定量化验收标准？
9. 是否声明能力边界？
10. 是否列出技术依赖？

【输出要求】
请按以下格式输出检查结果：
- 对每一项，先标明检查项编号和名称
- 给出判断：✅ 通过 / ⚠️ 部分满足 / ❌ 缺失
- 如果是"部分满足"或"缺失"，请说明具体缺少什么内容或改进建议
- 最后给出总体评价和优先改进建议

请用中文输出，格式清晰易读。"""


def parse_prd_to_excel_data(prd_content: str) -> list:
    """
    解析策划案文本，转换为Excel数据格式
    按标题层级分配到不同列：
    - 一级标题（如 1、xxx）在第1列
    - 二级标题（如 1.1、xxx）在第2列
    - 三级标题（如 1.1.1、xxx）在第3列
    - 普通内容在最近标题的下一列
    
    Returns:
        list: [(row_data, level), ...] 每行数据和其层级
    """
    lines = prd_content.strip().split('\n')
    excel_data = []
    current_level = 0
    
    # 匹配各级标题的正则表达式
    # 一级标题: 1、 或 1. 或 1  开头（纯数字）
    level1_pattern = re.compile(r'^(\d+)[、\.．]\s*(.+)$')
    # 二级标题: 1.1、 或 1.1. 或 1.1 开头
    level2_pattern = re.compile(r'^(\d+\.\d+)[、\.．]?\s*(.+)$')
    # 三级标题: 1.1.1、 或 1.1.1. 或 1.1.1 开头
    level3_pattern = re.compile(r'^(\d+\.\d+\.\d+)[、\.．]?\s*(.+)$')
    # 四级标题: 1.1.1.1 开头
    level4_pattern = re.compile(r'^(\d+\.\d+\.\d+\.\d+)[、\.．]?\s*(.+)$')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 检查是否是标题行，从高级别往低级别检查
        level4_match = level4_pattern.match(line)
        level3_match = level3_pattern.match(line)
        level2_match = level2_pattern.match(line)
        level1_match = level1_pattern.match(line)
        
        if level4_match:
            # 四级标题 -> 第4列
            current_level = 4
            excel_data.append((line, 4))
        elif level3_match:
            # 三级标题 -> 第3列
            current_level = 3
            excel_data.append((line, 3))
        elif level2_match:
            # 二级标题 -> 第2列
            current_level = 2
            excel_data.append((line, 2))
        elif level1_match:
            # 一级标题 -> 第1列
            current_level = 1
            excel_data.append((line, 1))
        else:
            # 普通内容 -> 当前标题的下一列，至少在第2列
            content_level = max(current_level + 1, 2) if current_level > 0 else 1
            excel_data.append((line, content_level))
    
    return excel_data


def create_excel_file(prd_content: str, check_result: str = "") -> bytes:
    """
    创建Excel文件
    
    Args:
        prd_content: 策划案内容
        check_result: AI复检结果（可选）
    
    Returns:
        bytes: Excel文件的二进制数据
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "策划案"
    
    # 定义样式
    header_font = Font(bold=True, size=14, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    level1_font = Font(bold=True, size=12, color="1F4E79")
    level2_font = Font(bold=True, size=11, color="2E75B6")
    level3_font = Font(bold=False, size=10, color="5B9BD5")
    normal_font = Font(size=10)
    
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    wrap_alignment = Alignment(wrap_text=True, vertical='top')
    
    # 设置列宽
    ws.column_dimensions['A'].width = 35
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 45
    ws.column_dimensions['D'].width = 50
    ws.column_dimensions['E'].width = 50
    
    # 添加表头
    headers = ["一级标题", "二级标题/内容", "三级标题/详情", "四级标题/说明", "详细内容"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border
    
    # 解析并填充策划案内容
    excel_data = parse_prd_to_excel_data(prd_content)
    
    row_num = 2
    for content, level in excel_data:
        # 将内容放到对应层级的列
        cell = ws.cell(row=row_num, column=level, value=content)
        cell.alignment = wrap_alignment
        cell.border = thin_border
        
        # 根据层级设置字体样式
        if level == 1:
            cell.font = level1_font
        elif level == 2:
            cell.font = level2_font
        elif level == 3:
            cell.font = level3_font
        else:
            cell.font = normal_font
        
        # 为该行的所有列添加边框
        for col in range(1, 6):
            if col != level:
                empty_cell = ws.cell(row=row_num, column=col, value="")
                empty_cell.border = thin_border
        
        row_num += 1
    
    # 如果有复检结果，添加到新的sheet
    if check_result:
        ws_check = wb.create_sheet(title="AI复检结果")
        ws_check.column_dimensions['A'].width = 100
        
        # 添加标题
        title_cell = ws_check.cell(row=1, column=1, value="AI复检清单检查结果")
        title_cell.font = header_font
        title_cell.fill = header_fill
        title_cell.alignment = Alignment(horizontal='center')
        
        # 解析复检结果
        check_lines = check_result.strip().split('\n')
        for idx, line in enumerate(check_lines, 2):
            cell = ws_check.cell(row=idx, column=1, value=line)
            cell.alignment = wrap_alignment
            
            # 根据内容设置样式
            if '✅' in line:
                cell.font = Font(color="228B22")  # 绿色
            elif '⚠️' in line:
                cell.font = Font(color="FF8C00")  # 橙色
            elif '❌' in line:
                cell.font = Font(color="DC143C")  # 红色
    
    # 保存到内存
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return output.getvalue()


def extract_text_from_pdf(file_content: bytes) -> str:
    """从PDF文件提取文本"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        return f"[PDF解析失败: {str(e)}]"


def extract_text_from_docx(file_content: bytes) -> str:
    """从Word文档提取文本"""
    try:
        doc = docx.Document(io.BytesIO(file_content))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        return f"[Word文档解析失败: {str(e)}]"


def extract_text_from_file(uploaded_file) -> str:
    """
    从上传的文件中提取文本内容
    
    Args:
        uploaded_file: Streamlit上传的文件对象
    
    Returns:
        str: 提取的文本内容
    """
    if uploaded_file is None:
        return ""
    
    file_name = uploaded_file.name.lower()
    file_content = uploaded_file.read()
    
    # 重置文件指针，以便后续可能的重复读取
    uploaded_file.seek(0)
    
    if file_name.endswith('.pdf'):
        return extract_text_from_pdf(file_content)
    elif file_name.endswith('.docx'):
        return extract_text_from_docx(file_content)
    elif file_name.endswith('.txt') or file_name.endswith('.md'):
        # 尝试多种编码
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                return file_content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return "[文本文件解码失败]"
    else:
        return "[不支持的文件类型]"


def format_prd_content(content: str) -> str:
    """
    格式化策划案内容，增强Markdown显示效果
    将数字标题转换为更美观的格式
    
    Args:
        content: 原始策划案内容
    
    Returns:
        str: 格式化后的Markdown内容
    """
    import re
    
    # 处理内容，增强格式
    lines = content.split('\n')
    formatted_lines = []
    
    # 用于判断是否在列表上下文中
    in_list_context = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # 跳过空行
        if not stripped:
            formatted_lines.append(line)
            in_list_context = False
            continue
        
        # 清理标题中的 ** 符号
        clean_line = re.sub(r'\*\*', '', stripped)
        
        # 匹配三级标题：1.1.1、xxx 或 1.1.1 xxx（优先匹配更长的模式）
        level3_match = re.match(r'^(\d+\.\d+\.\d+)[、\.．]?\s*(.+)$', clean_line)
        # 匹配二级标题：1.1、xxx 或 1.1 xxx
        level2_match = re.match(r'^(\d+\.\d+)[、\.．]?\s*(.+)$', clean_line)
        # 匹配一级标题：仅行首为单个数字 + 顿号/点号 + 标题文字（不含冒号结尾，避免匹配列表）
        level1_match = re.match(r'^(\d+)[、\.．]\s*([^：:]+)$', clean_line)
        
        # 检查是否是列表项（在特定上下文中的数字开头行）
        # 列表项特征：前面有 - 或 * 开头，或者在流程/步骤描述中
        is_list_item = False
        
        # 检查前一行是否暗示这是列表
        if i > 0:
            prev_line = lines[i-1].strip() if i > 0 else ""
            # 如果前一行以冒号结尾，或包含"流程"、"步骤"等词，后续的数字行可能是列表
            if prev_line.endswith('：') or prev_line.endswith(':') or \
               '流程' in prev_line or '步骤' in prev_line or in_list_context:
                # 检查当前行是否看起来像列表项（较长的描述性文字）
                if level1_match and len(clean_line) > 20:
                    is_list_item = True
                    in_list_context = True
        
        # 检查是否是以 - 或 * 开头的列表项
        if stripped.startswith('-') or stripped.startswith('*'):
            # 保持原样，只清理多余的 **
            formatted_lines.append(re.sub(r'\*\*([^*]+)\*\*', r'**\1**', line))
            in_list_context = True
            continue
        
        if level3_match:
            num, title = level3_match.groups()
            title = title.strip()
            formatted_lines.append(f'\n#### {num} {title}\n')
            in_list_context = False
        elif level2_match:
            num, title = level2_match.groups()
            title = title.strip()
            formatted_lines.append(f'\n### {num} {title}\n')
            in_list_context = False
        elif level1_match and not is_list_item:
            num, title = level1_match.groups()
            title = title.strip()
            # 一级标题使用特殊样式
            formatted_lines.append(f'\n## {num}、{title}\n')
            in_list_context = False
        else:
            # 对于普通行，保持原样但清理格式
            # 处理列表项格式，确保 **xxx** 格式正确
            processed_line = line
            # 如果是数字开头的列表项，转换为有序列表格式
            list_item_match = re.match(r'^(\d+)[、\.．]\s*(.+)$', clean_line)
            if list_item_match and is_list_item:
                num, text = list_item_match.groups()
                processed_line = f'{num}. {text}'
            formatted_lines.append(processed_line)
    
    return '\n'.join(formatted_lines)


def render_prd_document(content: str, title: str = "策划案"):
    """
    以美观的文档格式渲染策划案内容
    
    Args:
        content: 策划案内容
        title: 文档标题
    """
    import re
    
    # 格式化内容
    formatted_content = format_prd_content(content)
    
    # 将Markdown转换为HTML以便在自定义容器中正确显示
    # 处理标题
    html_content = formatted_content
    
    # 转换 ## 标题为 h2
    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    # 转换 ### 标题为 h3
    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
    # 转换 #### 标题为 h4
    html_content = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html_content, flags=re.MULTILINE)
    
    # 转换加粗文本
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    
    # 转换列表项 (- 开头)
    html_content = re.sub(r'^- (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    
    # 转换有序列表项 (1. 开头)
    html_content = re.sub(r'^(\d+)\. (.+)$', r'<li>\2</li>', html_content, flags=re.MULTILINE)
    
    # 将连续的 <li> 包裹在 <ul> 中
    html_content = re.sub(r'((?:<li>.*?</li>\s*)+)', r'<ul>\1</ul>', html_content, flags=re.DOTALL)
    
    # 转换段落（非空行且不是HTML标签开头的行）
    lines = html_content.split('\n')
    processed_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('<') and not stripped.startswith('#'):
            processed_lines.append(f'<p>{stripped}</p>')
        else:
            processed_lines.append(line)
    html_content = '\n'.join(processed_lines)
    
    # 清理多余的空行
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    
    # 使用Streamlit渲染整个文档（包括标题和内容）在同一个容器中
    st.markdown(f"""
    <div class="prd-document">
        <div style="text-align: center; margin-bottom: 25px;">
            <h1 style="color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; display: inline-block; margin: 0;">
                📄 {title}
            </h1>
        </div>
        <div class="prd-content">
            {html_content}
        </div>
        <hr style="border: none; border-top: 1px dashed #ccc; margin-top: 30px;">
    </div>
    """, unsafe_allow_html=True)


def is_file_upload_supported() -> bool:
    """检查当前选择的模型是否支持文件上传"""
    current_model = get_selected_model()
    # 检查模型名称是否在支持列表中（部分匹配）
    for supported_model in FILE_UPLOAD_SUPPORTED_MODELS:
        if supported_model in current_model or current_model in supported_model:
            return True
    return False


def get_gemini_client():
    """获取Gemini客户端实例"""
    api_key = st.session_state.get("api_key", "")
    if not api_key:
        st.error("⚠️ 请先在侧边栏配置 API Key")
        return None
    try:
        client = genai.Client(api_key=api_key)
        return client
    except Exception as e:
        st.error(f"API初始化失败: {str(e)}")
        return None


def get_selected_model():
    """获取当前选择的模型"""
    return st.session_state.get("selected_model", AVAILABLE_MODELS[0])


def fetch_available_models():
    """从API获取可用的模型列表"""
    api_key = st.session_state.get("api_key", "")
    if not api_key:
        return []
    try:
        client = genai.Client(api_key=api_key)
        models = []
        for model in client.models.list():
            # 只获取支持generateContent的模型
            if hasattr(model, 'supported_actions') and 'generateContent' in model.supported_actions:
                models.append(model.name.replace("models/", ""))
            elif not hasattr(model, 'supported_actions'):
                # 如果没有supported_actions属性，也添加（兼容性处理）
                model_name = model.name.replace("models/", "")
                if 'gemini' in model_name.lower():
                    models.append(model_name)
        return sorted(models) if models else AVAILABLE_MODELS
    except Exception as e:
        st.sidebar.warning(f"获取模型列表失败，使用默认列表: {str(e)}")
        return AVAILABLE_MODELS


def call_gemini(prompt: str, system_prompt: str = "") -> Optional[str]:
    """
    调用Gemini API（非流式，用于内部处理）
    
    Args:
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
    
    Returns:
        API返回的文本内容，失败返回None
    """
    try:
        client = get_gemini_client()
        if client is None:
            return None
        
        # 构建配置
        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None
        )
        
        response = client.models.generate_content(
            model=get_selected_model(),
            contents=prompt,
            config=config
        )
        return response.text
    except Exception as e:
        st.error(f"API调用失败: {str(e)}")
        return None


def call_gemini_with_image(image_data: bytes, prompt: str, system_prompt: str = "", mime_type: str = "image/png") -> Optional[str]:
    """
    调用Gemini API处理图片（非流式）
    
    Args:
        image_data: 图片的字节数据
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
        mime_type: 图片的MIME类型（image/png, image/jpeg, application/pdf）
    
    Returns:
        API返回的文本内容，失败返回None
    """
    try:
        client = get_gemini_client()
        if client is None:
            return None
        
        # 构建配置
        config = types.GenerateContentConfig(
            system_instruction=system_prompt if system_prompt else None
        )
        
        # 构建包含图片的内容
        contents = [
            types.Part.from_bytes(data=image_data, mime_type=mime_type),
            prompt
        ]
        
        response = client.models.generate_content(
            model=get_selected_model(),
            contents=contents,
            config=config
        )
        return response.text
    except Exception as e:
        st.error(f"图片处理API调用失败: {str(e)}")
        st.session_state.last_error = str(e)
        return None


def call_gemini_with_image_stream(image_data: bytes, prompt: str, system_prompt: str = "", mime_type: str = "image/png", thinking_container=None) -> Generator[dict, None, None]:
    """
    流式调用Gemini API处理图片，支持中止、错误展示和自动重试
    
    Args:
        image_data: 图片的字节数据
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
        mime_type: 图片的MIME类型
        thinking_container: 用于显示思考过程的容器（可选）
    
    Yields:
        dict: {"type": "text"|"thinking"|"error"|"retry", "content": str}
    """
    # 清空之前的错误
    st.session_state.last_error = ""
    st.session_state.thinking_content = ""
    
    # 重试配置
    max_retries = 3
    retry_delay = 5
    retryable_errors = ["503", "429", "overloaded", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "rate limit"]
    
    for attempt in range(max_retries):
        try:
            client = get_gemini_client()
            if client is None:
                yield {"type": "error", "content": "API客户端初始化失败，请检查API Key"}
                return
            
            # 构建配置
            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=10000
                ) if "2.5" in get_selected_model() or "think" in get_selected_model().lower() else None
            )
            
            # 构建包含图片的内容
            contents = [
                types.Part.from_bytes(data=image_data, mime_type=mime_type),
                prompt
            ]
            
            # 使用流式API
            response_stream = client.models.generate_content_stream(
                model=get_selected_model(),
                contents=contents,
                config=config
            )
            
            for chunk in response_stream:
                # 检查是否需要中止
                if st.session_state.should_stop:
                    yield {"type": "stopped", "content": "用户已中止生成"}
                    st.session_state.should_stop = False
                    return
                
                # 处理思考过程（如果有）
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'content') and candidate.content:
                            for part in candidate.content.parts:
                                # 检查是否是思考内容 - thought 属性直接包含思考文本
                                thinking_text = ""
                                
                                # thought 属性直接包含思考文本
                                if hasattr(part, 'thought') and part.thought:
                                    thinking_text = part.thought
                                
                                if thinking_text:
                                    st.session_state.thinking_content += thinking_text
                                    yield {"type": "thinking", "content": thinking_text}
                                elif hasattr(part, 'text') and part.text:
                                    yield {"type": "text", "content": part.text}
                elif chunk.text:
                    yield {"type": "text", "content": chunk.text}
            
            return
                    
        except Exception as e:
            error_msg = str(e)
            st.session_state.last_error = error_msg
            
            is_retryable = any(err_key in error_msg for err_key in retryable_errors)
            
            if is_retryable and attempt < max_retries - 1:
                remaining = max_retries - attempt - 1
                yield {
                    "type": "retry", 
                    "content": f"⚠️ 服务暂时不可用 ({error_msg[:50]}...)，{retry_delay}秒后自动重试（剩余{remaining}次）..."
                }
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)
                continue
            else:
                yield {"type": "error", "content": error_msg}
                return


def call_gemini_stream(prompt: str, system_prompt: str = "", thinking_container=None) -> Generator[dict, None, None]:
    """
    流式调用Gemini API，支持中止、错误展示、思考过程和自动重试
    
    Args:
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
        thinking_container: 用于显示思考过程的容器（可选）
    
    Yields:
        dict: {"type": "text"|"thinking"|"error"|"retry", "content": str}
    """
    # 清空之前的错误
    st.session_state.last_error = ""
    st.session_state.thinking_content = ""
    
    # 重试配置
    max_retries = 3
    retry_delay = 5  # 秒
    retryable_errors = ["503", "429", "overloaded", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "rate limit"]
    
    for attempt in range(max_retries):
        try:
            client = get_gemini_client()
            if client is None:
                yield {"type": "error", "content": "API客户端初始化失败，请检查API Key"}
                return
            
            # 获取当前选择的模型
            selected_model = get_selected_model()
            
            # 判断是否启用思考模式
            enable_thinking = "2.5" in selected_model or "think" in selected_model.lower()
            print(f"[DEBUG] Selected model: {selected_model}")
            print(f"[DEBUG] Enable thinking: {enable_thinking}")
            
            # 构建配置 - 启用思考过程（如果模型支持）
            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                # 尝试启用思考模式（部分模型支持）
                thinking_config=types.ThinkingConfig(
                    thinking_budget=10000  # 允许的思考token数
                ) if enable_thinking else None
            )
            
            print(f"[DEBUG] Config thinking_config: {config.thinking_config}")
            
            # 使用流式API
            response_stream = client.models.generate_content_stream(
                model=get_selected_model(),
                contents=prompt,
                config=config
            )
            
            # 调试标记，只打印一次
            debug_printed = False
            
            for chunk in response_stream:
                # 检查是否需要中止
                if st.session_state.should_stop:
                    yield {"type": "stopped", "content": "用户已中止生成"}
                    st.session_state.should_stop = False
                    return
                
                # 处理思考过程（如果有）
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'content') and candidate.content:
                            for part in candidate.content.parts:
                                # 获取 part 的类型名（用于调试和检测）
                                part_type = type(part).__name__
                                
                                # 调试：打印 part 的所有属性（仅首次）
                                if not debug_printed:
                                    part_attrs = [attr for attr in dir(part) if not attr.startswith('_')]
                                    print(f"[DEBUG call_gemini_stream] Part type: {part_type}")
                                    print(f"[DEBUG call_gemini_stream] Part attributes: {part_attrs}")
                                    # 打印一些关键属性的值
                                    for attr in ['thought', 'thinking', 'text']:
                                        if hasattr(part, attr):
                                            val = getattr(part, attr)
                                            print(f"[DEBUG call_gemini_stream] part.{attr} = {repr(val)[:100] if val else None}")
                                    debug_printed = True
                                
                                # 检查是否是思考内容 - thought 属性直接包含思考文本
                                thinking_text = ""
                                
                                # 方式1: 检查 thought 属性（直接包含思考文本）
                                if hasattr(part, 'thought') and part.thought:
                                    thinking_text = part.thought
                                    print(f"[DEBUG] Found thinking content: {thinking_text[:50]}...")
                                
                                if thinking_text:
                                    st.session_state.thinking_content += thinking_text
                                    yield {"type": "thinking", "content": thinking_text}
                                elif hasattr(part, 'text') and part.text:
                                    yield {"type": "text", "content": part.text}
                elif chunk.text:
                    yield {"type": "text", "content": chunk.text}
            
            # 成功完成，退出重试循环
            return
                    
        except Exception as e:
            error_msg = str(e)
            st.session_state.last_error = error_msg
            
            # 检查是否是可重试的错误
            is_retryable = any(err_key in error_msg for err_key in retryable_errors)
            
            if is_retryable and attempt < max_retries - 1:
                # 通知用户正在重试
                remaining = max_retries - attempt - 1
                yield {
                    "type": "retry", 
                    "content": f"⚠️ 服务暂时不可用 ({error_msg[:50]}...)，{retry_delay}秒后自动重试（剩余{remaining}次）..."
                }
                time.sleep(retry_delay)
                # 增加下次重试的等待时间（指数退避）
                retry_delay = min(retry_delay * 2, 30)
                continue
            else:
                # 不可重试或已用完重试次数
                yield {"type": "error", "content": error_msg}
                return


def stream_to_container(prompt: str, system_prompt: str, container, thinking_container=None, status_container=None) -> tuple:
    """
    流式输出到Streamlit容器，实时显示打字效果，支持中止、错误展示和思考过程
    
    Args:
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
        container: Streamlit容器对象（如st.empty()或st.container()）
        thinking_container: 用于显示思考过程的容器（可选）
        status_container: 用于显示状态信息的容器（可选）
    
    Returns:
        tuple: (完整的响应文本, 是否成功, 错误信息)
    """
    full_response = ""
    thinking_text = ""
    error_msg = ""
    was_stopped = False
    
    # 使用生成器进行流式输出
    for chunk_data in call_gemini_stream(prompt, system_prompt, thinking_container):
        chunk_type = chunk_data.get("type", "text")
        chunk_content = chunk_data.get("content", "")
        
        if chunk_type == "text":
            full_response += chunk_content
            # 实时更新显示内容，添加光标效果
            container.markdown(full_response + " ▌")
        elif chunk_type == "thinking":
            thinking_text += chunk_content
            # 显示思考过程
            if thinking_container:
                thinking_container.markdown(f"💭 **模型思考中...**\n\n{thinking_text}")
        elif chunk_type == "retry":
            # 显示重试状态
            if status_container:
                status_container.warning(chunk_content)
            else:
                st.warning(chunk_content)
        elif chunk_type == "error":
            error_msg = chunk_content
            if status_container:
                status_container.error(f"❌ API调用失败: {error_msg}")
            else:
                st.error(f"❌ API调用失败: {error_msg}")
            break
        elif chunk_type == "stopped":
            was_stopped = True
            if status_container:
                status_container.warning("⏹️ 生成已中止")
            break
        
        # 强制刷新显示
        time.sleep(0.01)
    
    # 移除光标，显示最终结果
    if full_response:
        container.markdown(full_response)
    
    # 判断是否成功
    success = bool(full_response) and not error_msg and not was_stopped
    
    return (full_response, success, error_msg)


def stream_generator(prompt: str, system_prompt: str):
    """
    创建流式输出生成器，配合st.write_stream使用
    
    Args:
        prompt: 用户输入的提示词
        system_prompt: 系统提示词
    
    Yields:
        文本片段
    """
    for chunk_data in call_gemini_stream(prompt, system_prompt):
        if chunk_data.get("type") == "text":
            yield chunk_data.get("content", "")


def generate_prd(user_input: str, use_stream: bool = False, container=None, thinking_container=None, status_container=None) -> tuple:
    """
    功能模块1：生成策划案（支持流式输出）
    
    Args:
        user_input: 用户输入的功能描述
        use_stream: 是否使用流式输出
        container: Streamlit容器对象，用于流式显示
        thinking_container: 用于显示思考过程的容器
        status_container: 用于显示状态信息的容器
    
    Returns:
        tuple: (生成的策划案文本, 是否成功, 错误信息)
    """
    prompt = f"请根据以下功能描述生成完整的策划案：\n\n{user_input}"
    
    if use_stream and container:
        return stream_to_container(prompt, get_system_prompt_with_date(GENERATE_PRD_SYSTEM_PROMPT), container, thinking_container, status_container)
    else:
        result = call_gemini(prompt, get_system_prompt_with_date(GENERATE_PRD_SYSTEM_PROMPT))
        return (result, result is not None, st.session_state.last_error if not result else "")


def ai_self_check(prd_content: str, use_stream: bool = False, container=None, thinking_container=None, status_container=None) -> tuple:
    """
    AI自检功能：对策划案进行复检清单检查（支持流式输出）
    
    Args:
        prd_content: 策划案内容
        use_stream: 是否使用流式输出
        container: Streamlit容器对象，用于流式显示
        thinking_container: 用于显示思考过程的容器
        status_container: 用于显示状态信息的容器
    
    Returns:
        tuple: (检查结果报告, 是否成功, 错误信息)
    """
    prompt = f"""请对以下策划案进行复检清单检查：

{prd_content}

请逐一检查每一项，给出详细的检查结果。"""
    
    if use_stream and container:
        return stream_to_container(prompt, SELF_CHECK_SYSTEM_PROMPT, container, thinking_container, status_container)
    else:
        result = call_gemini(prompt, SELF_CHECK_SYSTEM_PROMPT)
        return (result, result is not None, st.session_state.last_error if not result else "")


def optimize_prd_initial(old_prd: str, feedback: str, use_stream: bool = False, container=None, thinking_container=None, status_container=None) -> tuple:
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
        return stream_to_container(prompt, INITIAL_FIX_SYSTEM_PROMPT, container, thinking_container, status_container)
    else:
        result = call_gemini(prompt, INITIAL_FIX_SYSTEM_PROMPT)
        return (result, result is not None, st.session_state.last_error if not result else "")


def developer_review(current_prd: str, use_stream: bool = False, container=None, thinking_container=None, status_container=None) -> tuple:
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
        return stream_to_container(prompt, DEVELOPER_REVIEW_PROMPT, container, thinking_container, status_container)
    else:
        result = call_gemini(prompt, DEVELOPER_REVIEW_PROMPT)
        return (result, result is not None, st.session_state.last_error if not result else "")


def planner_fix(current_prd: str, dev_questions: str, use_stream: bool = False, container=None, thinking_container=None, status_container=None) -> tuple:
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
        return stream_to_container(prompt, PLANNER_FIX_PROMPT, container, thinking_container, status_container)
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
                was_stopped = True
                st.warning("⏹️ 迭代已中止")
                return (current_prd, True)
        
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


def main():
    """主函数"""
    # 页面配置
    st.set_page_config(
        page_title="游戏策划Agent（酸奶）",
        page_icon="🎮",
        layout="wide"
    )
    
    # 自定义CSS样式 - 优化文档显示效果
    st.markdown("""
    <style>
    /* 策划案文档容器样式 */
    .prd-document {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 30px 40px;
        margin: 20px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        line-height: 1.8;
        font-size: 15px;
    }
    
    /* 深色模式适配 */
    @media (prefers-color-scheme: dark) {
        .prd-document {
            background-color: #1e1e1e;
            border-color: #3a3a3a;
        }
    }
    
    /* 标题样式 */
    .prd-document h1 {
        font-size: 24px;
        color: #1a73e8;
        border-bottom: 2px solid #1a73e8;
        padding-bottom: 10px;
        margin: 30px 0 20px 0;
    }
    
    .prd-document h2 {
        font-size: 20px;
        color: #1a73e8;
        border-left: 4px solid #1a73e8;
        padding-left: 12px;
        margin: 25px 0 15px 0;
    }
    
    .prd-document h3 {
        font-size: 17px;
        color: #333;
        margin: 20px 0 12px 0;
    }
    
    .prd-document h4 {
        font-size: 15px;
        color: #555;
        margin: 15px 0 10px 0;
        font-weight: 600;
    }
    
    /* 内容区域 */
    .prd-content {
        padding: 10px 0;
    }
    
    /* 段落样式 */
    .prd-document p {
        margin: 12px 0;
        text-align: justify;
        line-height: 1.8;
    }
    
    /* 列表样式 */
    .prd-document ul, .prd-document ol {
        margin: 15px 0;
        padding-left: 25px;
    }
    
    .prd-document li {
        margin: 8px 0;
        line-height: 1.7;
    }
    
    /* 加粗文本高亮 */
    .prd-document strong {
        color: #d93025;
        font-weight: 600;
    }
    
    /* 代码块样式 */
    .prd-document code {
        background-color: #f5f5f5;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Consolas', monospace;
    }
    
    /* 分隔线 */
    .prd-document hr {
        border: none;
        border-top: 1px dashed #ccc;
        margin: 25px 0;
    }
    
    /* 一级章节标题（数字开头如 1、功能概述）*/
    .prd-section-title {
        font-size: 18px;
        font-weight: bold;
        color: #1a73e8;
        background: linear-gradient(90deg, #e8f0fe 0%, transparent 100%);
        padding: 10px 15px;
        margin: 25px 0 15px 0;
        border-left: 4px solid #1a73e8;
        border-radius: 0 6px 6px 0;
    }
    
    /* 二级标题 */
    .prd-subsection-title {
        font-size: 16px;
        font-weight: 600;
        color: #333;
        margin: 18px 0 10px 0;
        padding-left: 10px;
        border-left: 3px solid #4285f4;
    }
    
    /* 内容块 */
    .prd-content-block {
        padding: 10px 15px;
        margin: 10px 0;
        background-color: #fafafa;
        border-radius: 6px;
    }
    
    /* Streamlit默认markdown增强 */
    .stMarkdown {
        line-height: 1.8;
    }
    
    .stMarkdown p {
        margin-bottom: 12px;
    }
    
    /* 统一标题样式 - 清晰的层级区分，去除红色主题 */
    .stMarkdown h1 {
        font-size: 1.75em;
        font-weight: 700;
        color: #1f2937 !important;
        border-bottom: 2px solid #e5e7eb;
        padding-bottom: 8px;
        margin-top: 28px;
        margin-bottom: 16px;
    }
    
    .stMarkdown h2 {
        font-size: 1.4em;
        font-weight: 600;
        color: #374151 !important;
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 6px;
        margin-top: 24px;
        margin-bottom: 14px;
    }
    
    .stMarkdown h3 {
        font-size: 1.2em;
        font-weight: 600;
        color: #4b5563 !important;
        margin-top: 20px;
        margin-bottom: 12px;
    }
    
    .stMarkdown h4 {
        font-size: 1.1em;
        font-weight: 600;
        color: #6b7280 !important;
        margin-top: 16px;
        margin-bottom: 10px;
    }
    
    .stMarkdown h5, .stMarkdown h6 {
        font-size: 1em;
        font-weight: 600;
        color: #6b7280 !important;
        margin-top: 14px;
        margin-bottom: 8px;
    }
    
    /* 深色模式标题适配 */
    @media (prefers-color-scheme: dark) {
        .stMarkdown h1 {
            color: #f3f4f6 !important;
            border-bottom-color: #4b5563;
        }
        .stMarkdown h2 {
            color: #e5e7eb !important;
            border-bottom-color: #4b5563;
        }
        .stMarkdown h3 {
            color: #d1d5db !important;
        }
        .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
            color: #9ca3af !important;
        }
    }
    
    .stMarkdown ul, .stMarkdown ol {
        margin: 12px 0;
        padding-left: 24px;
    }
    
    .stMarkdown li {
        margin: 6px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 初始化session_state
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
        # 本地运行时可能没有 secrets 文件
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
    # 自动验证标志
    if "auto_validate_api_key" not in st.session_state:
        st.session_state.auto_validate_api_key = False
    # 中止控制
    if "should_stop" not in st.session_state:
        st.session_state.should_stop = False
    # 错误信息
    if "last_error" not in st.session_state:
        st.session_state.last_error = ""
    # 思考过程
    if "thinking_content" not in st.session_state:
        st.session_state.thinking_content = ""
    
    # ========== 侧边栏 - API配置 ==========
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
                if custom_api_key and custom_api_key != st.session_state.api_key:
                    st.session_state.api_key = custom_api_key
                    st.session_state.secrets_api_key_loaded = False
                    st.session_state.api_key_validated = False
                    # 自动触发验证
                    st.session_state.auto_validate_api_key = True
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
            
            # 检测API Key变化 - 自动触发验证
            if api_key_input != st.session_state.api_key:
                st.session_state.api_key = api_key_input
                st.session_state.api_key_validated = False
                st.session_state.models_list = AVAILABLE_MODELS
                # 如果新的API Key非空，自动触发验证
                if api_key_input:
                    st.session_state.auto_validate_api_key = True
                    st.rerun()
        
        # 自动验证API Key（当检测到需要自动验证时）
        if st.session_state.get('auto_validate_api_key', False) and api_key_input:
            st.session_state.auto_validate_api_key = False
            with st.spinner("正在自动验证API Key并获取模型列表..."):
                models = fetch_available_models()
                if models:
                    st.session_state.models_list = models
                    st.session_state.api_key_validated = True
                    st.success(f"✅ 验证成功！获取到 {len(models)} 个可用模型")
                else:
                    st.error("❌ API Key 无效或无法获取模型列表")
                    st.session_state.api_key_validated = False
        
        # 验证并获取模型列表按钮（手动刷新）
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 刷新模型列表", disabled=not api_key_input):
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
    
    # ========== 主界面 ==========
    # 标题
    st.title("🎮 游戏策划Agent（酸奶）")
    st.markdown("*基于Gemini API的智能策划辅助工具*")
    st.markdown("---")
    
    # 检查API Key
    if not st.session_state.api_key:
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
        st.stop()
    
    # ========== 历史详情查看区域 ==========
    if st.session_state.get("show_history_detail") and st.session_state.get("viewing_history_id"):
        history_id = st.session_state.viewing_history_id
        # 查找对应的历史记录
        history_item = None
        for item in st.session_state.session_history:
            if item.get("id") == history_id:
                history_item = item
                break
        
        if history_item:
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
                    data=get_download_data(history_item),
                    file_name=history_item.get("download_filename", "download.txt"),
                    mime=history_item.get("download_mime", "text/plain"),
                    key=f"history_download_{history_id}"
                )
            
            st.markdown("---")
    
    # 初始化功能选择的session state
    if "selected_function" not in st.session_state:
        st.session_state.selected_function = "生成策划案"
    
    # 功能选项列表
    function_options = ["生成策划案", "脑图生成策划案", "优化策划案", "汇报助手", "周报助手", "白皮书助手", "游戏策划(lina)", "表格处理助手", "思路引导助手 (linmo)", "PUBGM WoW 玩法评审"]
    
    # 获取当前选中的索引
    current_index = function_options.index(st.session_state.selected_function) if st.session_state.selected_function in function_options else 0
    
    # 功能选择
    function_mode = st.selectbox(
        "🔧 功能选择",
        options=function_options,
        index=current_index,
        help="选择要使用的功能",
        key="function_selectbox"
    )
    
    # 更新session state
    st.session_state.selected_function = function_mode
    
    # 根据功能模式显示不同的输入界面
    if function_mode == "生成策划案":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 📝 生成新策划案")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_generate_session", use_container_width=True):
                clear_module_session("生成策划案")
                st.rerun()
        st.markdown("请输入功能描述，AI将为您生成完整的策划案。")
        
        user_input = st.text_area(
            "功能描述",
            height=300,
            placeholder="请详细描述您要设计的游戏功能...\n\n例如：\n设计一个游戏内的好友系统，包括添加好友、删除好友、好友列表展示、在线状态显示等功能...",
            key="generate_input"
        )
        
        # ========== 文件上传区域（输入框右下方）==========
        if is_file_upload_supported():
            # 创建布局：左边是空的占位，右边是文件上传
            upload_col1, upload_col2 = st.columns([2, 1])
            
            with upload_col2:
                uploaded_file = st.file_uploader(
                    "📎 上传附件",
                    type=SUPPORTED_FILE_TYPES,
                    help="上传参考文档供AI参考（PDF/Word/TXT/MD）",
                    key="generate_file_uploader"
                )
                
                # 处理上传的文件
                if uploaded_file is not None:
                    if "uploaded_file_content" not in st.session_state or \
                       st.session_state.get("uploaded_file_name") != uploaded_file.name:
                        with st.spinner("解析中..."):
                            file_text = extract_text_from_file(uploaded_file)
                            st.session_state.uploaded_file_content = file_text
                            st.session_state.uploaded_file_name = uploaded_file.name
                    
                    # 显示文件信息和操作
                    st.caption(f"✅ {uploaded_file.name}")
                    
                    # 预览和清除按钮放在一行
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("�️ 预览", key="preview_gen", use_container_width=True):
                            st.session_state.show_preview_gen = not st.session_state.get("show_preview_gen", False)
                    with btn_col2:
                        if st.button("🗑️ 清除", key="clear_gen", use_container_width=True):
                            st.session_state.uploaded_file_content = ""
                            st.session_state.uploaded_file_name = ""
                            st.session_state.show_preview_gen = False
                            st.rerun()
                    
                    # 预览内容
                    if st.session_state.get("show_preview_gen", False):
                        with st.expander("📄 文件内容预览", expanded=True):
                            preview_text = st.session_state.uploaded_file_content
                            if len(preview_text) > 500:
                                st.text(preview_text[:500] + "\n\n... [已截断] ...")
                            else:
                                st.text(preview_text)
                else:
                    # 清除之前的文件内容
                    if "uploaded_file_content" in st.session_state and st.session_state.uploaded_file_content:
                        pass  # 保留已上传的内容，除非用户手动清除
            
            with upload_col1:
                # 显示附件状态提示
                if st.session_state.get("uploaded_file_content"):
                    st.info(f"📎 已添加附件: **{st.session_state.get('uploaded_file_name', '未知文件')}**")
        else:
            # 模型不支持文件上传时显示提示
            st.caption("💡 当前模型不支持文件上传，如需上传附件请切换至支持的模型")
        
        # 初始化自检结果的session_state
        if "generated_check_result" not in st.session_state:
            st.session_state.generated_check_result = ""
        
        # 使用session_state跟踪当前处理阶段
        if "current_stage" not in st.session_state:
            st.session_state.current_stage = "idle"  # idle, generating, checking, done
        
        if st.button("🚀 生成策划案", type="primary", disabled=st.session_state.is_processing):
            if not user_input.strip():
                st.error("请输入功能描述！")
            else:
                st.session_state.is_processing = True
                st.session_state.should_stop = False  # 重置中止标志
                st.session_state.generated_check_result = ""  # 清空之前的检查结果
                st.session_state.generated_prd = ""  # 清空之前的结果
                st.session_state.last_error = ""  # 清空错误
                st.session_state.current_stage = "generating"
                st.session_state.generate_saved_to_history = False  # 重置历史保存标记
                # 保存用户输入和附件内容到session_state
                st.session_state.saved_user_input = user_input
                st.session_state.saved_attachment_content = st.session_state.get("uploaded_file_content", "")
                st.session_state.saved_attachment_name = st.session_state.get("uploaded_file_name", "")
                st.rerun()  # 触发重新渲染
        
        # 处理生成阶段
        if st.session_state.is_processing and st.session_state.current_stage == "generating":
            # 从session_state获取保存的输入
            user_input_saved = st.session_state.get("saved_user_input", user_input)
            attachment_content = st.session_state.get("saved_attachment_content", "")
            attachment_name = st.session_state.get("saved_attachment_name", "")
            
            # 流式生成策划案
            st.markdown("### 📄 生成的策划案")
            
            # 显示中止按钮和状态
            col_status, col_stop = st.columns([4, 1])
            with col_status:
                st.markdown("**✍️ 策划酸奶正在撰写策划案...**")
            with col_stop:
                if st.button("⏹️ 中止生成", key="stop_generate", type="secondary"):
                    st.session_state.should_stop = True
                    st.session_state.is_processing = False
                    st.session_state.current_stage = "idle"
                    st.warning("⏹️ 生成已中止")
                    st.rerun()
            
            # 思考过程展示区域（可折叠）
            thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
            with thinking_expander:
                thinking_container = st.empty()
            
            # 状态和错误显示容器
            status_container = st.empty()
            
            # 构建最终的输入（包含附件内容）
            final_input = user_input_saved
            if attachment_content:
                final_input = f"""【用户功能描述】
{user_input_saved}

【附件内容】（文件名: {attachment_name}）
{attachment_content}

请参考以上功能描述和附件内容，生成完整的策划案。"""
                st.info(f"📎 已包含附件: {attachment_name}")
            
            # 创建容器用于流式显示
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
                st.rerun()  # 进入下一阶段
            elif error:
                st.error(f"❌ 生成失败: {error}")
                st.session_state.is_processing = False
                st.session_state.current_stage = "idle"
            elif st.session_state.should_stop:
                st.warning("⏹️ 生成已中止")
                if result:  # 如果有部分结果，保存它
                    st.session_state.generated_prd = result
                st.session_state.is_processing = False
                st.session_state.current_stage = "idle"
                st.session_state.should_stop = False
            else:
                st.error("生成失败，请重试")
                st.session_state.is_processing = False
                st.session_state.current_stage = "idle"
        
        # 处理检查阶段
        elif st.session_state.is_processing and st.session_state.current_stage == "checking":
            # 显示已生成的策划案（格式化显示）
            render_prd_document(st.session_state.generated_prd, "生成的策划案")
            st.success("✅ 策划案生成完成！")
            
            # AI自检 - 流式输出
            st.markdown("### 🔍 AI复检清单检查结果")
            
            # 显示中止按钮和状态
            col_status, col_stop = st.columns([4, 1])
            with col_status:
                st.markdown("**🔍 AI正在进行复检清单检查...**")
            with col_stop:
                if st.button("⏹️ 中止检查", key="stop_check", type="secondary"):
                    st.session_state.should_stop = True
                    st.session_state.is_processing = False
                    st.session_state.current_stage = "idle"
                    st.warning("⏹️ 检查已中止")
                    st.rerun()
            
            # 思考过程展示区域
            thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
            with thinking_expander:
                thinking_container = st.empty()
            
            # 状态和错误显示容器
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
            st.rerun()  # 刷新以显示最终结果和下载按钮
        
        # 显示已保存的生成结果（非处理中状态）
        if st.session_state.generated_prd and not st.session_state.is_processing:
            # 使用格式化显示函数
            render_prd_document(st.session_state.generated_prd, "生成的策划案")
            
            # 显示AI自检结果
            if st.session_state.generated_check_result:
                st.markdown("### 🔍 AI复检清单检查结果")
                with st.expander("查看详细检查结果", expanded=True):
                    st.markdown(st.session_state.generated_check_result)
            
            st.markdown(CHECKLIST)
            
            # 下载按钮 - Excel格式
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
            
            # 保存到会话历史（仅在首次完成时保存，避免重复）
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
            
            # ========== 多轮对话区域 ==========
            st.markdown("---")
            st.markdown("### 💬 继续对话")
            st.caption("您可以继续追问或要求修改，AI将基于已生成的策划案进行回答。")
            
            # 初始化对话历史
            chat_key = "generate_prd_chat"
            init_chat_history(chat_key)
            
            # 显示对话历史 - 使用 ChatGPT 风格的对话气泡
            chat_history = get_chat_history(chat_key)
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="📝"):
                            st.markdown(msg["content"])
            
            # 对话输入 - 使用 chat_input
            chat_input = st.chat_input(
                placeholder="例如：请详细说明第3章的验收标准...",
                key="generate_chat_input"
            )
            
            # 清空按钮放在单独一行
            if st.button("🗑️ 清空对话历史", key="generate_chat_clear", use_container_width=False):
                clear_chat_history(chat_key)
                st.rerun()
            
            # 处理对话
            if chat_input and chat_input.strip():
                add_chat_message(chat_key, "user", chat_input)
                
                # 构建上下文
                function_context = f"""【已生成的策划案】
{st.session_state.generated_prd}"""
                
                history_context = build_chat_context(chat_key, get_system_prompt_with_date(GENERATE_PRD_SYSTEM_PROMPT))
                full_prompt = f"""{function_context}

{history_context}

【当前用户输入】
{chat_input}

请基于以上策划案和对话历史，回答用户的问题或按要求进行修改。如果用户要求修改策划案，请输出修改后的完整内容。"""
                
                with st.spinner("正在思考..."):
                    response_container = st.empty()
                    full_response = ""
                    for chunk in call_gemini_stream(full_prompt, get_system_prompt_with_date(GENERATE_PRD_SYSTEM_PROMPT)):
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
    
    elif function_mode == "脑图生成策划案":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 🧠 脑图生成策划案")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_mindmap_session", use_container_width=True):
                clear_module_session("脑图生成策划案")
                st.rerun()
        st.markdown("上传思维脑图图片或输入Mermaid代码，AI将识别结构并生成完整的策划案。")
        
        # 初始化脑图相关的session state
        if "mindmap_parsed_structure" not in st.session_state:
            st.session_state.mindmap_parsed_structure = None
        if "mindmap_generated_prd" not in st.session_state:
            st.session_state.mindmap_generated_prd = None
        if "mindmap_image_data" not in st.session_state:
            st.session_state.mindmap_image_data = None
        if "mindmap_saved" not in st.session_state:
            st.session_state.mindmap_saved = False
        if "mindmap_mermaid_code" not in st.session_state:
            st.session_state.mindmap_mermaid_code = ""
        if "mindmap_input_mode" not in st.session_state:
            st.session_state.mindmap_input_mode = "图片上传"
        
        # 检查是否有从linmo模块传入的mermaid代码
        if "linmo_to_mindmap_mermaid" in st.session_state and st.session_state.linmo_to_mindmap_mermaid:
            st.session_state.mindmap_mermaid_code = st.session_state.linmo_to_mindmap_mermaid
            st.session_state.mindmap_input_mode = "Mermaid代码"
            st.session_state.linmo_to_mindmap_mermaid = ""  # 清空传入数据
            st.success("✅ 已从思路引导助手导入Mermaid代码！")
        
        # 输入模式选择
        input_mode = st.radio(
            "选择输入方式",
            ["图片上传", "Mermaid代码"],
            index=0 if st.session_state.mindmap_input_mode == "图片上传" else 1,
            horizontal=True,
            key="mindmap_input_mode_radio"
        )
        st.session_state.mindmap_input_mode = input_mode
        
        st.markdown("---")
        
        if input_mode == "图片上传":
            # 文件上传区域
            uploaded_mindmap = st.file_uploader(
                "📤 上传思维脑图",
                type=["jpg", "jpeg", "png", "pdf"],
                help="支持 JPG、PNG 格式的图片或 PDF 文件",
                key="mindmap_uploader"
            )
            
            # 显示上传的图片预览
            if uploaded_mindmap:
                file_type = uploaded_mindmap.type
                file_data = uploaded_mindmap.read()
                
                # 图片预览
                if file_type in ["image/jpeg", "image/png"]:
                    st.image(file_data, caption="上传的思维脑图", use_container_width=True)
                elif file_type == "application/pdf":
                    st.info("📄 已上传 PDF 文件，AI将尝试解析其中的思维脑图内容")
                
                # 保存图片数据到session state
                st.session_state.mindmap_image_data = {
                    "data": file_data,
                    "mime_type": file_type,
                    "name": uploaded_mindmap.name
                }
        else:
            # Mermaid代码输入区域
            st.markdown("#### 📝 输入Mermaid代码")
            st.markdown("*支持从思路引导助手生成的Mermaid思维导图代码*")
            
            mermaid_code = st.text_area(
                "Mermaid代码",
                value=st.session_state.mindmap_mermaid_code,
                height=250,
                placeholder="""请输入Mermaid格式的思维导图代码，例如：
graph LR
    A[核心功能] --> B(子功能1)
    A --> C(子功能2)
    B --> B1[具体细节]
    C --> C1[具体细节]""",
                key="mindmap_mermaid_input"
            )
            st.session_state.mindmap_mermaid_code = mermaid_code
            
            # 显示Mermaid代码预览提示
            if mermaid_code.strip():
                st.info("💡 提示：您可以将此代码复制到 [Mermaid Live Editor](https://mermaid-live.nodejs.cn/edit) 预览效果")
        
        # 补充说明输入
        additional_info = st.text_area(
            "📝 补充说明（可选）",
            height=100,
            placeholder="如有其他需求或背景信息，请在此输入...\n例如：这是一个MMORPG游戏的社交系统设计",
            key="mindmap_additional_info"
        )
        
        # 操作按钮 - 根据输入模式调整
        if input_mode == "图片上传":
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                parse_btn = st.button(
                    "🔍 解析脑图结构",
                    disabled=not st.session_state.mindmap_image_data,
                    use_container_width=True
                )
            
            with col2:
                generate_btn = st.button(
                    "📝 生成策划案",
                    disabled=not st.session_state.mindmap_parsed_structure,
                    use_container_width=True
                )
            
            with col3:
                clear_btn = st.button(
                    "🗑️ 清空重来",
                    use_container_width=True
                )
            
            # Mermaid模式不需要解析按钮
            mermaid_parse_btn = False
        else:
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                mermaid_parse_btn = st.button(
                    "🔍 解析Mermaid结构",
                    disabled=not st.session_state.mindmap_mermaid_code.strip(),
                    use_container_width=True
                )
                parse_btn = False
            
            with col2:
                generate_btn = st.button(
                    "📝 生成策划案",
                    disabled=not st.session_state.mindmap_parsed_structure,
                    use_container_width=True
                )
            
            with col3:
                clear_btn = st.button(
                    "🗑️ 清空重来",
                    use_container_width=True
                )
        
        if clear_btn:
            st.session_state.mindmap_parsed_structure = None
            st.session_state.mindmap_generated_prd = None
            st.session_state.mindmap_image_data = None
            st.session_state.mindmap_mermaid_code = ""
            st.session_state.mindmap_saved = False
            st.rerun()
        
        # 解析Mermaid代码结构
        if mermaid_parse_btn and st.session_state.mindmap_mermaid_code.strip():
            st.markdown("---")
            st.markdown("#### 🔄 正在解析Mermaid代码结构...")
            
            # 创建显示容器
            thinking_container = st.expander("💭 AI思考过程", expanded=False)
            status_container = st.empty()
            result_container = st.empty()
            
            mermaid_parse_prompt = f"""请分析以下Mermaid格式的思维导图代码，将其转换为结构化的文本格式，便于生成策划案。

【Mermaid代码】
```mermaid
{st.session_state.mindmap_mermaid_code}
```

请识别出：
1. 核心主题/功能
2. 各个分支节点及其层级关系
3. 节点之间的逻辑关系

输出格式要求：使用层级缩进的文本形式展示结构。"""

            if additional_info:
                mermaid_parse_prompt += f"\n\n补充背景信息：{additional_info}"
            
            # 流式解析
            full_response = ""
            thinking_text = ""
            
            for chunk_data in call_gemini_stream(mermaid_parse_prompt, MINDMAP_PARSE_SYSTEM_PROMPT):
                chunk_type = chunk_data.get("type", "text")
                chunk_content = chunk_data.get("content", "")
                
                if chunk_type == "text":
                    full_response += chunk_content
                    result_container.markdown(full_response + " ▌")
                elif chunk_type == "thinking":
                    thinking_text += chunk_content
                    with thinking_container:
                        st.markdown(thinking_text)
                elif chunk_type == "error":
                    status_container.error(f"❌ 解析失败: {chunk_content}")
            
            if full_response:
                result_container.markdown(full_response)
                st.session_state.mindmap_parsed_structure = full_response
                status_container.success('✅ Mermaid结构解析完成！请点击"生成策划案"按钮继续。')
                st.rerun()
        
        # 解析脑图结构
        if parse_btn and st.session_state.mindmap_image_data:
            st.markdown("---")
            st.markdown("#### 🔄 正在解析思维脑图...")
            
            image_info = st.session_state.mindmap_image_data
            
            # 创建显示容器
            thinking_container = st.expander("💭 AI思考过程", expanded=False)
            status_container = st.empty()
            result_container = st.empty()
            
            parse_prompt = "请仔细分析这张思维脑图图片，识别出所有的节点、层级关系和连接，将其转换为结构化的文本格式。"
            
            if additional_info:
                parse_prompt += f"\n\n补充背景信息：{additional_info}"
            
            # 流式解析
            full_response = ""
            thinking_text = ""
            
            for chunk_data in call_gemini_with_image_stream(
                image_info["data"],
                parse_prompt,
                MINDMAP_PARSE_SYSTEM_PROMPT,
                image_info["mime_type"],
                thinking_container
            ):
                chunk_type = chunk_data.get("type", "text")
                chunk_content = chunk_data.get("content", "")
                
                if chunk_type == "text":
                    full_response += chunk_content
                    result_container.markdown(full_response + " ▌")
                elif chunk_type == "thinking":
                    thinking_text += chunk_content
                    with thinking_container:
                        st.markdown(thinking_text)
                elif chunk_type == "retry":
                    status_container.warning(chunk_content)
                elif chunk_type == "error":
                    status_container.error(f"❌ 解析失败: {chunk_content}")
                elif chunk_type == "stopped":
                    status_container.warning("⚠️ 用户已中止")
            
            if full_response:
                result_container.markdown(full_response)
                st.session_state.mindmap_parsed_structure = full_response
                status_container.success('✅ 脑图结构解析完成！请点击"生成策划案"按钮继续。')
                st.rerun()
        
        # 显示已解析的结构
        if st.session_state.mindmap_parsed_structure:
            st.markdown("---")
            st.markdown("#### 📋 解析出的脑图结构")
            with st.expander("查看/编辑解析结果", expanded=True):
                edited_structure = st.text_area(
                    "解析结果（可手动编辑修正）",
                    value=st.session_state.mindmap_parsed_structure,
                    height=300,
                    key="mindmap_structure_editor"
                )
                if edited_structure != st.session_state.mindmap_parsed_structure:
                    st.session_state.mindmap_parsed_structure = edited_structure
        
        # 生成策划案
        if generate_btn and st.session_state.mindmap_parsed_structure:
            st.markdown("---")
            st.markdown("#### 🔄 正在生成策划案...")
            
            # 创建显示容器
            thinking_container = st.expander("💭 AI思考过程", expanded=False)
            status_container = st.empty()
            result_container = st.empty()
            
            generate_prompt = f"""请根据以下思维脑图结构生成完整的策划案：

【思维脑图结构】
{st.session_state.mindmap_parsed_structure}
"""
            
            if additional_info:
                generate_prompt += f"\n【补充说明】\n{additional_info}"
            
            # 流式生成
            full_response = ""
            thinking_text = ""
            
            for chunk_data in call_gemini_stream(generate_prompt, get_system_prompt_with_date(MINDMAP_TO_PRD_SYSTEM_PROMPT), thinking_container):
                chunk_type = chunk_data.get("type", "text")
                chunk_content = chunk_data.get("content", "")
                
                if chunk_type == "text":
                    full_response += chunk_content
                    result_container.markdown(full_response + " ▌")
                elif chunk_type == "thinking":
                    thinking_text += chunk_content
                    with thinking_container:
                        st.markdown(thinking_text)
                elif chunk_type == "retry":
                    status_container.warning(chunk_content)
                elif chunk_type == "error":
                    status_container.error(f"❌ 生成失败: {chunk_content}")
                elif chunk_type == "stopped":
                    status_container.warning("⚠️ 用户已中止")
            
            if full_response:
                result_container.empty()
                st.session_state.mindmap_generated_prd = full_response
                st.session_state.mindmap_saved = False
                status_container.success("✅ 策划案生成完成！")
                st.rerun()
        
        # 显示生成的策划案
        if st.session_state.mindmap_generated_prd:
            st.markdown("---")
            render_prd_document(st.session_state.mindmap_generated_prd, "生成的策划案（基于思维脑图）")
            
            # 保存到历史记录
            if not st.session_state.mindmap_saved:
                mindmap_name = st.session_state.mindmap_image_data.get("name", "思维脑图") if st.session_state.mindmap_image_data else "思维脑图"
                excel_data = create_excel_file(st.session_state.mindmap_generated_prd)
                add_to_history(
                    function_type="脑图生成策划案",
                    input_data={
                        "脑图文件": mindmap_name,
                        "解析结构": st.session_state.mindmap_parsed_structure[:200] + "..." if len(st.session_state.mindmap_parsed_structure) > 200 else st.session_state.mindmap_parsed_structure,
                        "补充说明": additional_info if additional_info else "无"
                    },
                    output_data=st.session_state.mindmap_generated_prd,
                    download_data=excel_data,
                    download_filename=f"脑图策划案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    download_mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.session_state.mindmap_saved = True
            
            # 下载按钮
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 下载策划案 (Excel)",
                    data=create_excel_file(st.session_state.mindmap_generated_prd),
                    file_name=f"脑图策划案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with col2:
                st.download_button(
                    label="📥 下载策划案 (Markdown)",
                    data=st.session_state.mindmap_generated_prd,
                    file_name=f"脑图策划案_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            
            # 多轮对话区域
            st.markdown("---")
            st.markdown("#### 💬 继续对话")
            
            chat_key = "mindmap_prd_chat"
            init_chat_history(chat_key)
            
            # 显示对话历史 - 使用 ChatGPT 风格的对话气泡
            chat_history = get_chat_history(chat_key)
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="🗺️"):
                            st.markdown(msg["content"])
            
            # 对话输入 - 使用 chat_input
            chat_input = st.chat_input(
                placeholder="例如：请补充一下技术实现方案...",
                key="mindmap_chat_input"
            )
            
            # 清空按钮
            if st.button("🗑️ 清空对话历史", key="mindmap_clear_chat", use_container_width=False):
                clear_chat_history(chat_key)
                st.rerun()
            
            if chat_input and chat_input.strip():
                add_chat_message(chat_key, "user", chat_input)
                
                # 构建上下文
                context_prompt = f"""当前策划案内容：

{st.session_state.mindmap_generated_prd}

用户追问：{chat_input}

请根据策划案内容回答用户的问题或进行相应修改。"""
                
                history_context = build_chat_context(chat_key, get_system_prompt_with_date(MINDMAP_TO_PRD_SYSTEM_PROMPT))
                full_prompt = history_context + "\n\n" + context_prompt
                
                response_container = st.empty()
                full_response = ""
                
                for chunk_data in call_gemini_stream(full_prompt, get_system_prompt_with_date(MINDMAP_TO_PRD_SYSTEM_PROMPT)):
                    chunk_type = chunk_data.get("type", "text")
                    chunk_content = chunk_data.get("content", "")
                    
                    if chunk_type == "text":
                        full_response += chunk_content
                        response_container.markdown(f"**🤖 AI：** {full_response} ▌")
                
                if full_response:
                    response_container.markdown(f"**🤖 AI：** {full_response}")
                    add_chat_message(chat_key, "assistant", full_response)
                    st.rerun()
    
    elif function_mode == "优化策划案":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 🔄 优化现有策划案")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_optimize_session", use_container_width=True):
                clear_module_session("优化策划案")
                st.rerun()
        st.markdown("请输入原策划案和修改意见，AI将通过多轮迭代进行优化。")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            old_prd = st.text_area(
                "原策划案",
                height=400,
                placeholder="请粘贴需要优化的策划案内容...",
                key="optimize_input"
            )
            
            # ========== 文件上传区域（输入框右下方）==========
            if is_file_upload_supported():
                # 创建布局：左边是状态提示，右边是文件上传
                opt_upload_col1, opt_upload_col2 = st.columns([2, 1])
                
                with opt_upload_col2:
                    uploaded_file_opt = st.file_uploader(
                        "📎 上传附件",
                        type=SUPPORTED_FILE_TYPES,
                        help="上传参考文档供AI参考（PDF/Word/TXT/MD）",
                        key="optimize_file_uploader"
                    )
                    
                    # 处理上传的文件
                    if uploaded_file_opt is not None:
                        if "uploaded_file_content" not in st.session_state or \
                           st.session_state.get("uploaded_file_name") != uploaded_file_opt.name:
                            with st.spinner("解析中..."):
                                file_text = extract_text_from_file(uploaded_file_opt)
                                st.session_state.uploaded_file_content = file_text
                                st.session_state.uploaded_file_name = uploaded_file_opt.name
                        
                        # 显示文件信息和操作
                        st.caption(f"✅ {uploaded_file_opt.name}")
                        
                        # 预览和清除按钮放在一行
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
                        
                        # 预览内容
                        if st.session_state.get("show_preview_opt", False):
                            with st.expander("📄 文件内容预览", expanded=True):
                                preview_text = st.session_state.uploaded_file_content
                                if len(preview_text) > 500:
                                    st.text(preview_text[:500] + "\n\n... [已截断] ...")
                                else:
                                    st.text(preview_text)
                
                with opt_upload_col1:
                    # 显示附件状态提示
                    if st.session_state.get("uploaded_file_content"):
                        st.info(f"📎 已添加附件: **{st.session_state.get('uploaded_file_name', '未知文件')}**")
            else:
                # 模型不支持文件上传时显示提示
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
        
        # 使用session_state跟踪优化阶段
        if "optimize_stage" not in st.session_state:
            st.session_state.optimize_stage = "idle"  # idle, initial, reflection, checking, done
        if "initial_fixed_prd" not in st.session_state:
            st.session_state.initial_fixed_prd = ""
        if "saved_old_prd" not in st.session_state:
            st.session_state.saved_old_prd = ""
        if "saved_feedback" not in st.session_state:
            st.session_state.saved_feedback = ""
        if "saved_max_iterations" not in st.session_state:
            st.session_state.saved_max_iterations = 3
        
        if st.button("🔄 开始优化", type="primary", disabled=st.session_state.is_processing):
            if not old_prd.strip():
                st.error("请输入原策划案！")
            else:
                st.session_state.is_processing = True
                st.session_state.should_stop = False  # 重置中止标志
                st.session_state.last_error = ""  # 清空错误
                st.session_state.optimized_prd = ""
                st.session_state.optimized_check_result = ""
                st.session_state.initial_fixed_prd = ""
                st.session_state.saved_old_prd = old_prd
                st.session_state.saved_feedback = feedback
                st.session_state.saved_max_iterations = max_iterations
                st.session_state.optimize_saved_to_history = False  # 重置历史保存标记
                # 保存附件内容
                st.session_state.saved_optimize_attachment = st.session_state.get("uploaded_file_content", "")
                st.session_state.saved_optimize_attachment_name = st.session_state.get("uploaded_file_name", "")
                st.session_state.optimize_stage = "initial"
                st.rerun()  # 触发重新渲染
        
        # 处理初始修正阶段
        if st.session_state.is_processing and st.session_state.optimize_stage == "initial":
            st.markdown("### 📌 Step 1: 初始修正")
            
            # 显示附件使用信息
            optimize_attachment = st.session_state.get("saved_optimize_attachment", "")
            optimize_attachment_name = st.session_state.get("saved_optimize_attachment_name", "")
            if optimize_attachment:
                st.info(f"📎 参考附件: {optimize_attachment_name}")
            
            # 显示中止按钮和状态
            col_status, col_stop = st.columns([4, 1])
            with col_status:
                st.markdown("**✏️ 正在进行初始修正...**")
            with col_stop:
                if st.button("⏹️ 中止", key="stop_initial", type="secondary"):
                    st.session_state.should_stop = True
                    st.session_state.optimize_processing = False
                    st.session_state.optimize_stage = "idle"
                    st.warning("⏹️ 优化已中止")
                    st.rerun()
            
            # 思考过程展示区域
            thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
            with thinking_expander:
                thinking_container = st.empty()
            
            # 状态和错误显示容器
            status_container = st.empty()
            
            # 构建包含附件的feedback
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
        
        # 处理Reflection循环阶段
        elif st.session_state.is_processing and st.session_state.optimize_stage == "reflection":
            # 显示已完成的初始修正
            st.markdown("### 📌 Step 1: 初始修正")
            with st.expander("查看初始修正结果", expanded=False):
                st.markdown(st.session_state.initial_fixed_prd)
            st.success("初始修正完成！")
            st.markdown("---")
            
            # Reflection循环
            st.markdown("### 🔁 Step 2: Reflection 循环优化")
            final_prd, was_stopped = reflection_loop(st.session_state.initial_fixed_prd, st.session_state.saved_max_iterations)
            
            st.session_state.optimized_prd = final_prd
            
            if was_stopped:
                st.warning("⏹️ 迭代已中止，将使用当前版本进行复检")
                st.session_state.should_stop = False
            
            st.session_state.optimize_stage = "checking"
            st.rerun()
        
        # 处理最终检查阶段
        elif st.session_state.is_processing and st.session_state.optimize_stage == "checking":
            # 显示之前的步骤
            st.markdown("### 📌 Step 1: 初始修正")
            st.success("初始修正完成！")
            st.markdown("---")
            
            st.markdown("### 🔁 Step 2: Reflection 循环优化")
            st.success(f"完成 {st.session_state.saved_max_iterations} 轮迭代优化！")
            st.markdown("---")
            
            # AI自检 - 流式输出
            st.markdown("### 🔍 Step 3: AI复检清单检查")
            
            # 显示中止按钮和状态
            col_status, col_stop = st.columns([4, 1])
            with col_status:
                st.markdown("**🔍 AI正在进行最终复检清单检查...**")
            with col_stop:
                if st.button("⏹️ 中止检查", key="stop_final_check", type="secondary"):
                    st.session_state.should_stop = True
                    st.session_state.optimize_processing = False
                    st.session_state.optimize_stage = "idle"
                    st.warning("⏹️ 检查已中止")
                    st.rerun()
            
            # 思考过程展示区域
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
            st.rerun()  # 刷新以显示最终结果和下载按钮
        
        # 初始化优化自检结果的session_state
        if "optimized_check_result" not in st.session_state:
            st.session_state.optimized_check_result = ""
        
        # 显示已保存的优化结果（非处理中状态）
        if st.session_state.optimized_prd and not st.session_state.is_processing:
            # 使用格式化显示函数
            render_prd_document(st.session_state.optimized_prd, "优化后的策划案")
            
            # 显示AI自检结果
            if st.session_state.optimized_check_result:
                st.markdown("### 🔍 AI复检清单检查结果")
                with st.expander("查看详细检查结果", expanded=True):
                    st.markdown(st.session_state.optimized_check_result)
            
            st.markdown(CHECKLIST)
            
            # 下载按钮 - Excel格式
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
            
            # 保存到会话历史（仅在首次完成时保存，避免重复）
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
            
            # ========== 多轮对话区域 ==========
            st.markdown("---")
            st.markdown("### 💬 继续对话")
            st.caption("您可以继续追问或要求修改，AI将基于优化后的策划案进行回答。")
            
            # 初始化对话历史
            chat_key = "optimize_prd_chat"
            init_chat_history(chat_key)
            
            # 显示对话历史 - 使用 ChatGPT 风格的对话气泡
            chat_history = get_chat_history(chat_key)
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="✨"):
                            st.markdown(msg["content"])
            
            # 对话输入 - 使用 chat_input
            opt_chat_input = st.chat_input(
                placeholder="例如：请补充技术依赖部分的细节...",
                key="optimize_chat_input"
            )
            
            # 清空按钮
            if st.button("🗑️ 清空对话历史", key="optimize_chat_clear", use_container_width=False):
                clear_chat_history(chat_key)
                st.rerun()
            
            # 处理对话
            if opt_chat_input and opt_chat_input.strip():
                add_chat_message(chat_key, "user", opt_chat_input)
                
                # 构建上下文
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
    
    # ========== 汇报助手功能 ==========
    elif function_mode == "汇报助手":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 📊 汇报助手")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_report_session", use_container_width=True):
                clear_module_session("汇报助手")
                st.rerun()
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
                st.session_state.report_saved_to_history = False  # 重置历史保存标记
                st.rerun()
        
        # 处理生成阶段
        if st.session_state.report_processing:
            # 显示中止按钮和状态
            col_status, col_stop = st.columns([4, 1])
            with col_status:
                st.markdown("**✍️ 正在生成汇报文案...**")
            with col_stop:
                if st.button("⏹️ 中止生成", key="stop_report", type="secondary"):
                    st.session_state.should_stop = True
                    st.session_state.report_processing = False
                    st.warning("⏹️ 生成已中止")
                    st.rerun()
            
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
        
        # 显示已生成的汇报（非处理中状态）
        if st.session_state.generated_report and not st.session_state.report_processing:
            # 使用格式化显示函数
            render_prd_document(st.session_state.generated_report, "汇报文案")
            
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
            
            # 显示对话历史 - 使用 ChatGPT 风格的对话气泡
            chat_history = get_chat_history(chat_key)
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="📊"):
                            st.markdown(msg["content"])
            
            # 对话输入 - 使用 chat_input
            report_chat_input = st.chat_input(
                placeholder="例如：请把解决方案写得更详细一些...",
                key="report_chat_input"
            )
            
            # 清空按钮
            if st.button("🗑️ 清空对话历史", key="report_chat_clear", use_container_width=False):
                clear_chat_history(chat_key)
                st.rerun()
            
            # 处理对话
            if report_chat_input and report_chat_input.strip():
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
    
    # ========== 周报助手功能 ==========
    elif function_mode == "周报助手":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 📅 周报助手")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_weekly_session", use_container_width=True):
                clear_module_session("周报助手")
                st.rerun()
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
                st.session_state.weekly_saved_to_history = False  # 重置历史保存标记
                st.rerun()
        
        # 处理生成阶段
        if st.session_state.weekly_report_processing:
            # 显示中止按钮和状态
            col_status, col_stop = st.columns([4, 1])
            with col_status:
                st.markdown("**✍️ 正在生成周报...**")
            with col_stop:
                if st.button("⏹️ 中止生成", key="stop_weekly", type="secondary"):
                    st.session_state.should_stop = True
                    st.session_state.weekly_report_processing = False
                    st.warning("⏹️ 生成已中止")
                    st.rerun()
            
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
        
        # 显示已生成的周报（非处理中状态）
        if st.session_state.generated_weekly_report and not st.session_state.weekly_report_processing:
            # 使用格式化显示函数
            render_prd_document(st.session_state.generated_weekly_report, "周报")
            
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
            
            # 显示对话历史 - 使用 ChatGPT 风格的对话气泡
            chat_history = get_chat_history(chat_key)
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="📅"):
                            st.markdown(msg["content"])
            
            # 对话输入 - 使用 chat_input
            weekly_chat_input = st.chat_input(
                placeholder="例如：请补充数据分析部分的内容...",
                key="weekly_chat_input"
            )
            
            # 清空按钮
            if st.button("🗑️ 清空对话历史", key="weekly_chat_clear", use_container_width=False):
                clear_chat_history(chat_key)
                st.rerun()
            
            # 处理对话
            if weekly_chat_input and weekly_chat_input.strip():
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
    
    # ========== 白皮书助手功能 ==========
    elif function_mode == "白皮书助手":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 📖 白皮书助手")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_whitepaper_session", use_container_width=True):
                clear_module_session("白皮书助手")
                st.rerun()
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
                st.session_state.whitepaper_saved_to_history = False  # 重置历史保存标记
                st.rerun()
        
        # 处理生成阶段
        if st.session_state.whitepaper_processing:
            # 显示中止按钮和状态
            col_status, col_stop = st.columns([4, 1])
            with col_status:
                st.markdown("**✍️ 正在生成功能描述...**")
            with col_stop:
                if st.button("⏹️ 中止生成", key="stop_whitepaper", type="secondary"):
                    st.session_state.should_stop = True
                    st.session_state.whitepaper_processing = False
                    st.warning("⏹️ 生成已中止")
                    st.rerun()
            
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
        
        # 显示已生成的功能描述（非处理中状态）
        if st.session_state.generated_feature_desc and not st.session_state.whitepaper_processing:
            # 使用格式化显示函数
            render_prd_document(st.session_state.generated_feature_desc, "功能描述")
            
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
            
            # 显示对话历史 - 使用 ChatGPT 风格的对话气泡
            chat_history = get_chat_history(chat_key)
            if chat_history:
                for msg in chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="📖"):
                            st.markdown(msg["content"])
            
            # 对话输入 - 使用 chat_input
            wp_chat_input = st.chat_input(
                placeholder="例如：请再生成一个关于武装AI的功能描述...",
                key="whitepaper_chat_input"
            )
            
            # 清空按钮
            if st.button("🗑️ 清空对话历史", key="whitepaper_chat_clear", use_container_width=False):
                clear_chat_history(chat_key)
                st.rerun()
            
            # 处理对话
            if wp_chat_input and wp_chat_input.strip():
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
    
    # ========== 精英策划案(lina版) 模块 ==========
    elif function_mode == "游戏策划(lina)":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 🎯 游戏策划(lina)")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_lina_session", use_container_width=True):
                clear_module_session("游戏策划(lina)")
                st.rerun()
        st.markdown("与资深游戏策划专家进行多轮讨论，将需求提炼为结构化的功能点列表。")
        
        # Lina模块的System Prompt
        LINA_SYSTEM_PROMPT = """#  step1：精英策划案讨论

## 回复语言
请始终使用中文进行回答和输出。

## 角色定位与核心人设

你是一位在 **PUBG Mobile 项目组** 工作的 **顶级专业游戏策划**，同时也是一位擅长需求分析的顾问。你拥有下文详述的"精英游戏策划能力标准"中列出的全部能力。

**核心人设：** 你是一个极其严苛的专家。你不会迎合我的任何错误观点，也不会对我表示不必要的尊敬或委婉。你的沟通风格直接、犀利，旨在以最高的效率达成最深刻的共识。对于逻辑严密、论据充分的观点，你会予以肯定；对于存在漏洞、思考不周或过于想当然的想法，你必须一针见血地指出问题所在，并引导我进行更深层次的思考。我们的共同目标是产出卓越的设计。

## 核心任务与互动流程

你的核心任务是与我协同工作，将我提出的初步需求或想法，通过严谨的、专家级的讨论，最终提炼成一份逻辑清晰、层级分明、可执行的核心功能点列表。

**互动流程如下：**

1.  **需求接收与审视：** 我会提出一个初步的需求、想法或想要讨论的功能方向。
2.  **精英级研讨与推导 (核心环节):**
    *   **严苛审视：** 你将立即启动分析，分解我的请求，识别其在 PUBG Mobile 生态下的**核心目标 (Why)**、**核心内容 (What)**、限制条件和潜在挑战。
    *   **引用专业能力：** 在讨论中，你**必须主动引用下方"精英游戏策划能力标准"中的相关能力**来支撑你的分析、质疑和建议。例如："基于'用户体验与行为规划'和'核心玩法创新'的原则，我认为你这个想法的入口设计可能会破坏玩家的肌肉记忆，我们需要探讨更优的方案..."。
    *   **引入案例：** 你会**主动引入竞品分析或行业内类似问题的解决方案作为参考**，对比不同方案的优劣，启发更深度的思考。
    *   **聚焦逻辑链：** 我们的讨论将优先确保需求的**"为什么" (Why - 背景与目的)** 和 **"是什么" (What - 核心内容)** 逻辑清晰且论证充分。这个过程是对模糊想法的"压力测试"，目标是达成一个清晰、明确、且经过深思熟虑的共识。
3.  **结构化列表输出：** 在我们对需求的关键点达成共识后，你将基于讨论结果，整理并输出一份符合下方格式和优化原则的功能点列表。

## 输出要求与原则

1.  **结构化的功能点列表 (最终产出):**
    *   这份列表应**聚焦于"是什么" (What)**，即需要实现的核心功能、规则或改动。
    *   列表必须**逻辑清晰、层级分明**，能够清楚地展示不同功能模块及其包含的具体要点。
    *   你应根据讨论和对UGC生态的理解，补充我认为合理但可能遗漏的关联功能点。
    *   **优化原则：**
        *   `逻辑清晰 (Logical Clarity)`: 功能点按模块或流程合理分组。
        *   `层级分明 (Clear Hierarchy)`: 使用清晰的层级结构展示功能间的关系。
        *   `内容精炼 (Conciseness)`: 每个功能点用简洁、明确的语言描述，直击核心。
        *   `重点明确 (Focus)`: 列表需准确反映讨论后确定的核心需求范围。
        *   `具体可行 (Actionable)`: 功能点应描述具体需要实现的内容，而非模糊概念。

2.  **最终输出格式:**
    *   最终输出的功能点列表，请严格按照以下格式（**不要使用Markdown代码块包裹**）：
        *   使用 `【一级功能/模块】` 标记最高层级。
        *   使用 `「二级功能/子模块」` 标记次级层级。
        *   使用 `- ` 开始描述具体的功能点或需求说明。
        *   确保整体结构整齐、美观、易于阅读。

---

## 精英游戏策划能力标准：

### 游戏行业认知与洞察

#### 行业深度洞察
- 深入掌握游戏行业完整发展历史与演变路径，能精确预测未来发展趋势
- 对全球各主要市场的游戏生态系统有系统性理解，包括平台、用户、商业模式和监管环境
- 对各类型游戏（例如MMORPG、MOBA、FPS、开放世界等）的经典作品与创新产品有全面的分析能力
- 能识别市场中的创新机会点，并评估其发展潜力和风险

#### 标杆分析能力
- 精准把握该品类下各代表性产品的优劣势，能准确定位竞品在市场中的位置和策略
- 深入理解行业标杆产品的成功要素和失败案例，能提炼出可复制的方法论
- 能基于标杆分析结果制定正确的战略定位和产品方向
- 拥有独到的行业观察视角，能发现竞品无法察觉的市场机会

#### 行业影响力
- 能在国际游戏会议（如GDC、Devcom等）发表有影响力的演讲和论文
- 其设计理念和方法论被业内广泛采纳和引用
- 能在游戏设计领域引领创新潮流，推动行业发展
- 拥有广泛的行业人脉网络和资源，能迅速整合优质资源解决复杂问题

### 游戏分析与理解

#### 游戏体验拆解与分析
- 能系统化分析任何类型游戏的核心体验元素，理解其设计意图与实现方式
- 能精确识别游戏产品的感官、认知、情感和社交体验设计，并理解其相互作用
- 能根据玩家行为数据和心理动机，反向推导游戏设计决策和效果
- 熟练运用多种体验分析方法，如玩家旅程图、情绪曲线、行为图谱等

#### 玩家行为与心理分析
- 深入理解不同类型玩家的心理模型和动机系统（成就感、社交需求、自我表达等）
- 能精准分析游戏机制对玩家决策行为的影响机制，包括短期和长期行为模式
- 深刻把握玩家在不同游戏阶段的心理状态与需求变化
- 能通过定量与定性分析方法，预测游戏设计变更对玩家行为的影响

#### 框架分析与系统思维
- 能迅速构建任何类型游戏的完整系统框架图，理解各子系统间的关联与平衡
- 理解游戏各子系统的数据流向与信息交互模式，识别潜在瓶颈与优化点
- 能透过表面现象看到游戏设计的本质结构和核心矛盾
- 具备将复杂游戏系统抽象为简明模型的能力，并能基于此模型进行创新设计

### 玩法与关卡设计

#### 3C设计精通
- 掌握多类型游戏的顶级3C设计理念与实现方法（角色控制、摄像机、碰撞检测）
- 能针对不同平台（PC、主机、移动设备等）优化3C体验，创造流畅直观的操作感
- 精通角色状态机设计，能创造行云流水的角色动作过渡与反馈系统
- 能有效融合游戏的核心玩法和3C系统，创造独特的游戏体验基础

#### 核心玩法创新
- 能创造在业界具有开创性的核心玩法机制，引领游戏品类的发展方向
- 精通多种思考模式的游戏设计（战略思考、反应能力、解谜推理、社交博弈等）
- 能将不同类型游戏的优秀机制进行创新性融合，创造全新游戏体验
- 具备将抽象创意转化为可实现游戏机制的能力，并能预见其平衡性与可扩展性

#### 流程体验与空间设计
- 掌握顶级游戏关卡和流程设计方法，能精确控制玩家情绪曲线和挑战梯度
- 精通空间叙事与环境讲故事技巧，能通过环境设计传递故事和引导玩家行为
- 能创造具有教科书级别的游戏空间结构，成为行业参考标准
- 熟练应用各种空间引导手法（光影、色彩、音效、地形等）创造直观且深层次的体验

#### 玩法整合与系统设计
- 能将宏观系统、核心玩法、叙事元素、美术表现完美融合为统一的游戏体验
- 能在复杂的游戏系统中创造多层次的玩家成长路径和自由度
- 掌握多种游戏平衡技术，能在自由度和引导性之间找到最佳平衡点
- 能设计支持长期运营的玩法系统架构，具备可持续扩展和迭代能力

### 系统设计

#### 宏观系统架构
- 掌握多种类型游戏的系统架构设计方法论，能创建高度内聚、松耦合的系统结构
- 能在系统设计中平衡产品目标、用户体验、技术实现和商业模式的多重需求
- 精通游戏系统的分层设计，能创建灵活适应不同玩家群体的多层次系统
- 能预见系统扩展和迭代中的潜在问题，并在设计中预留合理的解决方案

#### 核心规则与机制设计
- 能设计具有深度、平衡且具备创新性的游戏核心规则系统
- 精通各类战斗、策略、收集、建造等核心系统的设计原理与最佳实践
- 能将复杂规则简化为直观机制，平衡游戏的深度和可接受度
- 能创建教科书级别的规则设计，被行业广泛参考和学习

#### 用户体验与行为规划
- 精通分层用户体验设计，能为不同熟练度、不同动机的用户提供差异化体验
- 能设计精确引导玩家成长的系统路径，控制技能学习曲线和挑战升级节奏
- 深刻理解并能设计针对不同情感需求的系统反馈机制
- 能通过系统设计巧妙引导玩家行为，实现产品战略和商业目标

#### 创新系统构建
- 能基于深刻的游戏理解创造全新的系统设计范式，引领行业发展方向
- 能将其他领域（如经济学、社会学、心理学等）的模型创新性地应用于游戏系统
- 能设计高度适应不同文化和市场的弹性系统架构
- 掌握系统复杂度管理方法，能在保持系统深度的同时确保可理解性和可维护性

### 数值设计

#### 数值模型架构
- 掌握多种游戏类型的数值架构设计方法，能建立完整、自洽的数值体系
- 精通数值系统的分层设计，能创建支持多种策略与玩法的丰富数值结构
- 能将抽象设计理念精确转化为可量化的数值系统
- 能设计具有高度扩展性和可维护性的数值架构，支持长期运营和内容更新

#### 数据分析与平衡调优
- 精通游戏数据的收集、分析和应用，能从海量数据中提取关键洞察
- 熟练使用各类统计和数学工具进行数值模拟和预测
- 能基于玩家行为数据进行精确的数值调整，优化游戏体验
- 掌握自动化数值测试和平衡技术，提高数值调优效率和精确度

#### 数值体系创新
- 能将现实经济学模型创新应用于游戏设计，创造独特的经济系统
- 能设计支持多样化游戏策略的平衡数值系统，创造深度的策略空间
- 精通游戏中的概率系统设计，能创造公平且有趣的随机机制
- 能预测游戏数值系统的长期演化趋势，设计可持续发展的数值生态

#### 跨系统数值整合
- 能协调整合战斗、成长、经济等多系统的数值关系，确保整体平衡和体验连贯
- 精通不同系统间的资源流转设计，创建健康的游戏经济循环
- 能设计支持多种变现模式的数值系统，平衡游戏体验和商业目标
- 掌握多维度数值指标的平衡艺术，创造多样化且均衡的游戏体验

### 叙事设计

#### 世界观构建
- 能创造具有高度原创性和内部一致性的游戏世界观体系
- 精通不同类型游戏的世界观设计方法（奇幻、科幻、历史、现代等）
- 能将世界观元素无缝融入游戏机制和视觉表现，创造沉浸式体验
- 设计具有扩展潜力的世界体系，支持IP长期发展和跨媒体延伸

#### 角色与情感设计
- 能创造具有深度、独特性和成长弧的游戏角色，引发玩家情感共鸣
- 精通不同类型游戏中的角色功能与叙事功能的平衡设计
- 能设计多层次的角色关系网络，创造丰富的社交和叙事可能性
- 掌握角色通过对话、行为和环境互动展现性格的技巧

#### 叙事结构与表达
- 掌握互动叙事的高级设计技巧，能根据不同游戏类型选择最佳叙事结构
- 精通环境叙事、程序叙事、隐性叙事等多种叙事手法
- 能将叙事元素与游戏机制和玩家行为紧密结合，创造真正的互动叙事体验
- 能设计支持多重结局和玩家选择的分支叙事系统，确保各路径均有价值

#### IP打造与跨媒体延展
- 具备战略性IP规划能力，能设计支持长期发展的IP核心架构
- 精通IP在不同媒介间的延展规则，确保跨媒体内容的一致性和互补性
- 能将IP元素转化为可识别的视觉符号、音乐语言和核心理念
- 能制定IP内容更新和演化策略，保持IP的生命力和市场吸引力

### 项目管理与团队协作

#### 设计领导力
- 能提供清晰的创意愿景和设计方向，激发团队创造力
- 精通设计目标的分解和任务分配，确保高效且高质量的设计实现
- 具备在保持创意完整性的同时灵活适应资源和技术约束的能力
- 能有效协调跨职能团队合作，确保设计理念在各环节的准确传达

#### 设计沟通与文档
- 能创建清晰、系统、易于理解的设计文档，有效传达设计意图
- 精通各类设计工具和可视化方法，能直观展示复杂设计概念
- 具备将抽象概念转化为具体原型的能力，快速验证设计想法
- 能根据不同受众（团队成员、管理层、投资者等）调整设计沟通方式

#### 项目风险管理
- 能准确评估设计决策对项目进度、资源和质量的影响
- 具备识别设计中潜在问题的前瞻性思维，制定预防和应对策略
- 精通范围控制和优先级管理，确保核心设计目标的实现
- 能在保持设计质量的前提下灵活调整计划，应对不确定性

#### 团队培养与文化建设
- 能系统化提升团队的设计能力，培养跨领域的游戏设计人才
- 具备将个人经验和方法论转化为团队知识的能力
- 能营造鼓励创新和实验的团队文化，平衡创意自由和项目目标
- 精通设计评审和反馈机制，促进团队成员的持续成长

### 用户洞察与市场理解

#### 用户研究与数据分析
- 精通各类用户研究方法（焦点小组、可用性测试、行为数据分析等）
- 能从用户反馈和行为数据中提取有价值的设计洞察
- 具备建立用户画像和行为模型的能力，指导针对性设计
- 能预测设计变更对用户行为和体验的影响

#### 市场趋势与竞品分析
- 能准确把握全球游戏市场趋势和用户偏好变化
- 精通竞品分析方法，能深入理解竞争产品的优劣势和策略
- 具备识别市场空白和机会的敏锐洞察力
- 能将市场分析转化为具体的产品策略和设计决策

#### 商业模式与变现设计
- 深入理解各类游戏商业模式的原理和最佳实践
- 能设计与游戏体验和用户心理自然融合的变现系统
- 精通不同市场和用户群体的消费心理和支付习惯
- 能平衡短期收益和长期用户价值，设计可持续的商业系统

#### 全球化与本地化策略
- 精通不同文化背景下的游戏设计适配原则
- 能设计支持全球化和深度本地化的游戏架构
- 理解不同地区的法规、文化禁忌和用户偏好
- 具备在保持产品核心价值的同时实现文化适配的能力

### 创新与前瞻性思维

#### 前沿技术应用
- 深入了解AI、VR/AR、云游戏等前沿技术及其对游戏设计的影响
- 能将新技术创新性地应用于游戏设计，创造全新体验
- 具备评估新技术可行性和价值的能力，避免技术陷阱
- 能预见技术发展趋势对游戏设计的长期影响

#### 跨领域创新能力
- 能将其他领域（心理学、社会学、文学、电影等）的理念应用于游戏设计
- 具备从不相关领域汲取灵感的能力，创造独特游戏体验
- 精通不同媒介叙事和表达特性，能进行创新性融合
- 能将现实世界系统和模式抽象为有趣的游戏机制

#### 实验设计与原型验证
- 精通快速原型开发和测试方法，能高效验证设计假设
- 具备设计有效实验评估游戏体验的能力
- 能从失败实验中提取有价值的洞察和经验
- 掌握渐进式设计方法，通过迭代改进实现创新

#### 游戏设计思维创新
- 能突破既有游戏设计框架，提出全新设计范式
- 具备重新定义游戏类型或创造全新类型的能力
- 能挑战行业常规，推动游戏媒介的艺术和表达边界
- 掌握游戏设计的基础理论，并能进行创新性发展和应用

---

**互动开始:**

好的，我已经理解并准备就绪。我将以PUBG Mobile精英策划的身份，遵循以上所有要求与你展开讨论。请提出你的初步需求或想法，我们将以最高效、最严谨的方式进行研讨。"""
        
        # 初始化lina模块专用的session state
        if "lina_chat_history" not in st.session_state:
            st.session_state.lina_chat_history = []
        if "lina_max_rounds" not in st.session_state:
            st.session_state.lina_max_rounds = 10
        if "lina_is_processing" not in st.session_state:
            st.session_state.lina_is_processing = False
        
        # 侧边栏设置：最大对话轮次
        with st.sidebar:
            st.markdown("---")
            st.subheader("🎯 Lina对话设置")
            lina_max_rounds = st.number_input(
                "最大对话轮次限制",
                min_value=1,
                max_value=50,
                value=st.session_state.lina_max_rounds,
                step=1,
                help="一轮对话 = 用户发送 + AI回复"
            )
            st.session_state.lina_max_rounds = lina_max_rounds
            
            # 显示当前轮次
            current_rounds = len([m for m in st.session_state.lina_chat_history if m["role"] == "user"])
            st.info(f"当前轮次: {current_rounds} / {lina_max_rounds}")
            
            # 清空对话按钮
            if st.button("🗑️ 清空对话/重新开始", key="lina_clear_chat", use_container_width=True):
                clear_module_session("游戏策划(lina)")
                st.rerun()
        
        # 计算当前轮次（用户消息数）
        current_rounds = len([m for m in st.session_state.lina_chat_history if m["role"] == "user"])
        max_rounds_reached = current_rounds >= st.session_state.lina_max_rounds
        
        # 聊天显示区
        st.markdown("#### 💬 对话区域")
        
        # 显示对话历史
        chat_container = st.container()
        with chat_container:
            if not st.session_state.lina_chat_history:
                st.info("👋 请在下方输入您的初步需求或想法，开始与精英策划专家讨论。")
            else:
                for msg in st.session_state.lina_chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="🎯"):
                            st.markdown(msg["content"])
        
        # 轮次达到上限提示
        if max_rounds_reached:
            st.warning(f'⚠️ 对话轮次已达上限（{st.session_state.lina_max_rounds}轮），请点击侧边栏的"清空对话/重新开始"按钮重新开始。')
        
        # 输入区 - 使用 chat_input，只有按下 Enter 键才会发送
        lina_user_input = st.chat_input(
            placeholder="例如：我想设计一个PUBG Mobile的好友推荐系统...",
            disabled=max_rounds_reached or st.session_state.lina_is_processing,
            key="lina_chat_input"
        )
        
        # chat_input 返回值不为 None 时表示用户按下了 Enter 键发送
        should_send = lina_user_input is not None and lina_user_input.strip() and not max_rounds_reached
        
        # 处理用户输入
        if should_send:
            st.session_state.lina_is_processing = True
            
            # 添加用户消息到历史
            st.session_state.lina_chat_history.append({
                "role": "user",
                "content": lina_user_input.strip()
            })
            
            # 构建完整的对话上下文
            # System Prompt + 历史对话 + 当前输入
            messages_context = ""
            for msg in st.session_state.lina_chat_history:
                if msg["role"] == "user":
                    messages_context += f"\n\n【用户】\n{msg['content']}"
                else:
                    messages_context += f"\n\n【Lina】\n{msg['content']}"
            
            full_prompt = f"""请基于以下对话历史继续讨论：
{messages_context}

请以精英策划专家Lina的身份回复。"""
            
            # 流式生成回复
            st.markdown("#### 🤖 Lina正在思考...")
            
            # 思考过程容器
            thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
            with thinking_expander:
                thinking_container = st.empty()
            
            response_container = st.empty()
            full_response = ""
            thinking_text = ""
            
            for chunk in call_gemini_stream(full_prompt, LINA_SYSTEM_PROMPT):
                if chunk["type"] == "text":
                    full_response += chunk["content"]
                    response_container.markdown(full_response + " ▌")
                elif chunk["type"] == "thinking":
                    thinking_text += chunk["content"]
                    with thinking_expander:
                        thinking_container.markdown(thinking_text)
                elif chunk["type"] == "error":
                    st.error(f"生成失败: {chunk['content']}")
                    break
            
            if full_response:
                response_container.markdown(full_response)
                # 添加AI回复到历史
                st.session_state.lina_chat_history.append({
                    "role": "assistant",
                    "content": full_response
                })
            
            st.session_state.lina_is_processing = False
            st.rerun()
    
    # ========== 表格处理助手模块 ==========
    elif function_mode == "表格处理助手":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 📊 表格处理助手")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_table_session", use_container_width=True):
                clear_module_session("表格处理助手")
                st.rerun()
        st.markdown("上传Excel表格，描述处理逻辑，AI将自动生成代码并执行处理。")
        
        # 表格处理助手的System Prompt（单表格版本）
        TABLE_ASSISTANT_SYSTEM_PROMPT_SINGLE = """Role: 你是一位精通 Python Pandas 库的数据处理专家。

回复语言: 请始终使用中文进行回答和输出。

Task: 你的任务是根据用户提供的【数据列名结构】、【处理逻辑】和【输出要求】，编写一段可执行的 Python 代码来处理数据。

Context (运行环境):
1. 这是一个沙盒环境，已经预置了一个名为 `df` 的 Pandas DataFrame 变量，它包含了用户上传的数据。
2. 你只需要编写处理 `df` 的逻辑代码。
3. **关键约束**：处理完成后的最终结果 DataFrame 必须赋值给变量名 `result_df`。

Input Data:
- 数据列名: {columns}
- 处理逻辑: {processing_logic}
- 输出要求: {output_requirements}

Output Rules (Strict):
1. **只输出 Python 代码**。不要包含 ```python ... ``` 标记，不要包含任何解释性文字，不要包含 print 语句。
2. 确保代码可以直接在 `exec()` 函数中运行。
3. 必须确保最终结果存储在 `result_df` 变量中。
4. 如果需要导入 pandas，请使用 `import pandas as pd`（虽然环境通常已预置，但为了保险）。
5. 不要读取文件（文件已在 `df` 中），不要保存文件（系统会处理保存）。

Example Output:
# 假设用户要求筛选A列大于10
result_df = df[df['A'] > 10].copy()"""
        
        # 表格处理助手的System Prompt（多表格版本）
        TABLE_ASSISTANT_SYSTEM_PROMPT_MULTI = """Role: 你是一位精通 Python Pandas 库的数据处理专家。

回复语言: 请始终使用中文进行回答和输出。

Task: 你的任务是根据用户提供的【多个数据表结构】、【处理逻辑】和【输出要求】，编写一段可执行的 Python 代码来处理数据。

Context (运行环境):
1. 这是一个沙盒环境，已经预置了多个 Pandas DataFrame 变量，变量名为 df_1, df_2, df_3... 分别对应用户上传的多个表格数据。
2. 你需要编写处理这些 DataFrame 的逻辑代码，可能涉及合并、关联、对比等操作。
3. **关键约束**：处理完成后的最终结果 DataFrame 必须赋值给变量名 `result_df`。

Input Data:
{tables_info}
- 处理逻辑: {processing_logic}
- 输出要求: {output_requirements}

Output Rules (Strict):
1. **只输出 Python 代码**。不要包含 ```python ... ``` 标记，不要包含任何解释性文字，不要包含 print 语句。
2. 确保代码可以直接在 `exec()` 函数中运行。
3. 必须确保最终结果存储在 `result_df` 变量中。
4. 如果需要导入 pandas，请使用 `import pandas as pd`（虽然环境通常已预置，但为了保险）。
5. 不要读取文件（文件已在对应的 df_N 变量中），不要保存文件（系统会处理保存）。
6. 使用正确的变量名引用各个表格（df_1, df_2, df_3...）。

Example Output:
# 假设用户要求将df_1和df_2按照ID列合并
result_df = pd.merge(df_1, df_2, on='ID', how='inner')"""
        
        # 初始化Session State
        if "table_dataframes" not in st.session_state:
            st.session_state.table_dataframes = {}  # {"文件名_sheet名": df}
        if "table_selected_dfs" not in st.session_state:
            st.session_state.table_selected_dfs = []  # 用户选择的df列表
        if "table_result_df" not in st.session_state:
            st.session_state.table_result_df = None
        if "table_is_processing" not in st.session_state:
            st.session_state.table_is_processing = False
        if "table_uploaded_files_info" not in st.session_state:
            st.session_state.table_uploaded_files_info = {}  # {文件名: [sheet列表]}
        
        # 文件上传区
        st.markdown("#### 📁 文件上传")
        uploaded_files = st.file_uploader(
            "上传表格文件（支持多文件）",
            type=['xlsx', 'xls', 'csv'],
            key="table_file_uploader",
            help="支持 .xlsx、.xls 格式的Excel文件和 .csv 格式的CSV文件，可同时上传多个文件",
            accept_multiple_files=True
        )
        
        import pandas as pd
        
        # 读取上传的文件
        if uploaded_files:
            new_dataframes = {}
            new_files_info = {}
            
            for uploaded_file in uploaded_files:
                file_name = uploaded_file.name
                file_ext = file_name.lower().split('.')[-1]
                try:
                    if file_ext == 'csv':
                        # CSV文件只有一个数据表
                        df = pd.read_csv(uploaded_file)
                        df_key = file_name
                        new_dataframes[df_key] = df
                        new_files_info[file_name] = ['CSV数据']
                    else:
                        # Excel文件可能有多个sheet
                        excel_file = pd.ExcelFile(uploaded_file)
                        sheet_names = excel_file.sheet_names
                        new_files_info[file_name] = sheet_names
                        
                        # 读取每个sheet
                        for sheet_name in sheet_names:
                            df_key = f"{file_name} - {sheet_name}"
                            df = pd.read_excel(excel_file, sheet_name=sheet_name)
                            new_dataframes[df_key] = df
                    
                except Exception as e:
                    st.error(f"❌ 文件 {file_name} 读取失败: {e}")
            
            # 更新session state
            st.session_state.table_dataframes = new_dataframes
            st.session_state.table_uploaded_files_info = new_files_info
            
            if new_dataframes:
                st.success(f"✅ 成功读取 {len(uploaded_files)} 个文件，共 {len(new_dataframes)} 个数据表")
        else:
            # 清空数据
            st.session_state.table_dataframes = {}
            st.session_state.table_uploaded_files_info = {}
            st.session_state.table_selected_dfs = []
        
        # 显示已上传的表格信息和选择器
        if st.session_state.table_dataframes:
            st.markdown("#### 📋 选择要处理的数据表")
            
            # 多选框选择要使用的表格
            available_tables = list(st.session_state.table_dataframes.keys())
            selected_tables = st.multiselect(
                "选择要处理的数据表（可多选）",
                options=available_tables,
                default=available_tables[:1] if available_tables else [],
                key="table_selector",
                help="选择一个或多个数据表进行处理。多个表格时，AI可以进行合并、关联等操作。"
            )
            st.session_state.table_selected_dfs = selected_tables
            
            # 显示选中表格的信息
            if selected_tables:
                for idx, table_key in enumerate(selected_tables, 1):
                    df = st.session_state.table_dataframes[table_key]
                    with st.expander(f"📊 表格{idx}: {table_key} ({len(df)}行, {len(df.columns)}列)", expanded=(idx==1)):
                        st.write(f"**变量名：** `df_{idx}`")
                        st.write(f"**列名列表：** {', '.join(df.columns.tolist())}")
                        st.dataframe(df.head(5))
        
        # 需求输入区
        st.markdown("#### ✏️ 处理需求")
        
        processing_logic = st.text_area(
            "请输入数据处理逻辑",
            placeholder="例如：将A列和B列相加生成C列；筛选出D列大于100的数据；按E列分组统计F列的平均值...",
            height=120,
            key="table_processing_logic"
        )
        
        output_requirements = st.text_input(
            "请输入输出内容要求",
            placeholder="例如：保留所有列；只保留C列和D列；输出前100行数据...",
            key="table_output_requirements"
        )
        
        # 执行按钮
        col1, col2 = st.columns([1, 4])
        has_selected_tables = len(st.session_state.table_selected_dfs) > 0
        with col1:
            process_btn = st.button(
                "🚀 开始处理并生成结果",
                disabled=st.session_state.table_is_processing or not has_selected_tables,
                type="primary"
            )
        
        # 处理逻辑
        if process_btn and has_selected_tables:
            if not processing_logic.strip():
                st.warning("⚠️ 请输入数据处理逻辑")
            else:
                st.session_state.table_is_processing = True
                
                selected_tables = st.session_state.table_selected_dfs
                num_tables = len(selected_tables)
                
                # 准备执行环境
                local_vars = {'pd': pd}
                
                if num_tables == 1:
                    # 单表格模式
                    table_key = selected_tables[0]
                    df = st.session_state.table_dataframes[table_key]
                    columns_str = ", ".join(df.columns.tolist())
                    local_vars['df'] = df.copy()
                    
                    # 构建单表格Prompt
                    final_prompt = TABLE_ASSISTANT_SYSTEM_PROMPT_SINGLE.format(
                        columns=columns_str,
                        processing_logic=processing_logic,
                        output_requirements=output_requirements if output_requirements.strip() else "保留所有相关列"
                    )
                else:
                    # 多表格模式
                    tables_info_lines = []
                    for idx, table_key in enumerate(selected_tables, 1):
                        df = st.session_state.table_dataframes[table_key]
                        local_vars[f'df_{idx}'] = df.copy()
                        columns_str = ", ".join(df.columns.tolist())
                        tables_info_lines.append(f"- 表格{idx} (变量名: df_{idx}, 来源: {table_key}): 列名 = [{columns_str}]")
                    
                    tables_info = "\n".join(tables_info_lines)
                    
                    # 构建多表格Prompt
                    final_prompt = TABLE_ASSISTANT_SYSTEM_PROMPT_MULTI.format(
                        tables_info=tables_info,
                        processing_logic=processing_logic,
                        output_requirements=output_requirements if output_requirements.strip() else "保留所有相关列"
                    )
                
                with st.spinner("🤖 AI正在分析需求并生成代码..."):
                    try:
                        # 调用模型生成代码
                        generated_code = call_gemini(final_prompt)
                        
                        if generated_code:
                            # 清洗代码（防止模型带了markdown标记）
                            code_to_run = generated_code.replace("```python", "").replace("```", "").strip()
                            
                            # 显示生成的代码（调试用，可选）
                            with st.expander("🔍 查看生成的代码", expanded=False):
                                st.code(code_to_run, language="python")
                            
                            # 执行代码
                            with st.spinner("⚙️ 正在执行数据处理..."):
                                exec(code_to_run, {}, local_vars)
                            
                            # 提取结果
                            if 'result_df' in local_vars:
                                st.session_state.table_result_df = local_vars['result_df']
                                st.success("✅ 处理完成！")
                            else:
                                st.error("❌ 模型生成的代码未定义 'result_df' 变量，请重试。")
                        else:
                            st.error("❌ AI未能生成有效代码，请重试。")
                    
                    except Exception as e:
                        st.error(f"❌ 代码执行出错: {e}")
                        st.session_state.table_result_df = None
                
                st.session_state.table_is_processing = False
        
        # 结果展示区
        if st.session_state.table_result_df is not None:
            st.markdown("---")
            st.markdown("#### 📊 处理结果")
            
            result_df = st.session_state.table_result_df
            st.info(f"结果数据：共 {len(result_df)} 行，{len(result_df.columns)} 列")
            
            # Markdown预览
            st.markdown("**结果预览（前10行）：**")
            try:
                st.markdown(result_df.head(10).to_markdown(index=False))
            except:
                # 如果to_markdown不可用，使用dataframe显示
                st.dataframe(result_df.head(10))
            
            # Excel下载
            import pandas as pd
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False)
            processed_data = output.getvalue()
            
            st.download_button(
                label="📥 下载处理后的Excel",
                data=processed_data,
                file_name="processed_result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    # ========== 思路引导助手 (linmo) 模块 ==========
    elif function_mode == "思路引导助手 (linmo)":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 🧠 思路引导助手 (Linmo)")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_linmo_session", use_container_width=True):
                clear_module_session("思路引导助手 (linmo)")
                st.rerun()
        st.markdown("通过苏格拉底式提问，帮助您理清思路并生成结构化的思维导图。")
        
        # Mermaid在线编辑器链接
        st.markdown("""
        📎 **Mermaid 在线编辑器**：
        - [Mermaid AI Dashboard](https://mermaid.ai/app/dashboard)
        - [Mermaid Live Editor](https://mermaid-live.nodejs.cn/edit)
        """)
        st.markdown("---")
        
        # Linmo模块的System Prompt
        LINMO_SYSTEM_PROMPT = """Role: 你是 "Linmo" (思路引导助手)，一位擅长结构化思维和苏格拉底式提问的专家。

回复语言: 请始终使用中文进行回答和输出。

Goal: 你的目标是帮助用户理清复杂的问题或想法，将其转化为结构清晰的思维导图。

Process:
1.  **接收输入**：用户会输入一个问题、一种困扰或一些零散的思路。
2.  **分析与构建**：基于用户的信息，构建或更新一个思维导图结构。
3.  **追问引导**：不要直接给出所有答案。你需要发现用户思路中的模糊点、缺失环节或逻辑跳跃，并提出 1-2 个关键的追问，引导用户深入思考。
4.  **循环迭代**：用户回答后，你将新信息整合进思维导图，并再次展示更新后的结构，直到用户满意。

Output Format (Strict):
每次回复必须包含以下三个部分：

**Part 1: 思考与反馈**
简要回应用户的输入，说明你理解了什么，以及你为什么要更新导图的某个部分。

**Part 2: 当前思维导图 (Mermaid)**
请始终使用 Mermaid 语法展示**当前完整**的思维导图结构。
请使用 `graph LR` (从左到右) 或 `graph TD` (从上到下) 结构。
```mermaid
graph LR
    A[核心问题] --> B(分支1)
    A --> C(分支2)
    B --> B1(细节)
```

**Part 3: 引导追问**
基于当前的导图，提出 1-2 个问题，引导用户补充下一层级的信息或澄清模糊点。
(例如："关于分支B，你觉得具体的执行难点在哪里？" 或 "除了目前列出的，还有其他影响因素吗？")

Termination Condition:
当用户明确表示"没有问题了"、"结构很好了"或"生成最终结果"时：
1. 停止追问。
2. 输出一段总结语。
3. 输出最终版本的 Mermaid 代码块，确保语法完美，适合复制。

Tone:
专业、耐心、引导性强、逻辑严密。"""
        
        # 初始化linmo模块专用的session state
        if "linmo_chat_history" not in st.session_state:
            st.session_state.linmo_chat_history = []
        if "linmo_max_rounds" not in st.session_state:
            st.session_state.linmo_max_rounds = 10
        if "linmo_is_processing" not in st.session_state:
            st.session_state.linmo_is_processing = False
        if "linmo_input_key_counter" not in st.session_state:
            st.session_state.linmo_input_key_counter = 0
        
        # 侧边栏设置：最大对话轮次
        with st.sidebar:
            st.markdown("---")
            st.subheader("🧠 Linmo对话设置")
            linmo_max_rounds = st.number_input(
                "最大对话轮次限制",
                min_value=1,
                max_value=50,
                value=st.session_state.linmo_max_rounds,
                step=1,
                help="一轮对话 = 用户发送 + AI回复",
                key="linmo_max_rounds_input"
            )
            st.session_state.linmo_max_rounds = linmo_max_rounds
            
            # 显示当前轮次
            current_rounds = len([m for m in st.session_state.linmo_chat_history if m["role"] == "user"])
            st.info(f"当前轮次: {current_rounds} / {linmo_max_rounds}")
            
            # 清空对话按钮
            if st.button("🗑️ 重新开始引导", key="linmo_clear_chat", use_container_width=True):
                clear_module_session("思路引导助手 (linmo)")
                st.rerun()
        
        # 计算当前轮次（用户消息数）
        current_rounds = len([m for m in st.session_state.linmo_chat_history if m["role"] == "user"])
        max_rounds_reached = current_rounds >= st.session_state.linmo_max_rounds
        
        # 聊天显示区
        st.markdown("#### 💬 对话区域")
        
        # 辅助函数：从文本中提取Mermaid代码
        def extract_mermaid_code(text):
            """从文本中提取Mermaid代码块"""
            import re
            # 匹配 ```mermaid ... ``` 代码块
            pattern = r'```mermaid\s*([\s\S]*?)```'
            matches = re.findall(pattern, text)
            if matches:
                return matches[-1].strip()  # 返回最后一个Mermaid代码块
            return None
        
        # 显示对话历史
        chat_container = st.container()
        with chat_container:
            if not st.session_state.linmo_chat_history:
                # 显示欢迎语
                with st.chat_message("assistant", avatar="🧠"):
                    st.markdown("你好，我是 **Linmo**。请告诉我你现在面临的问题或想要拆解的目标，我来帮你梳理思路。\n\n我会通过提问引导你逐步理清思路，并用思维导图的形式展示结构。")
            else:
                for msg in st.session_state.linmo_chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="🧠"):
                            st.markdown(msg["content"])
        
        # 检测最后一条AI回复是否包含Mermaid代码，显示跳转按钮
        if st.session_state.linmo_chat_history:
            # 获取最后一条AI回复
            ai_messages = [m for m in st.session_state.linmo_chat_history if m["role"] == "assistant"]
            if ai_messages:
                last_ai_message = ai_messages[-1]["content"]
                mermaid_code = extract_mermaid_code(last_ai_message)
                if mermaid_code:
                    st.markdown("---")
                    st.info("🎉 检测到思维导图已生成，您可以将其用于生成完整的策划案！")
                    col_jump, col_copy = st.columns([1, 1])
                    with col_jump:
                        if st.button("🚀 跳转到「脑图生成策划案」", key="linmo_jump_to_mindmap", use_container_width=True):
                            # 将mermaid代码存入session state，供脑图模块使用
                            st.session_state.linmo_to_mindmap_mermaid = mermaid_code
                            st.session_state.selected_function = "脑图生成策划案"
                            st.rerun()
                    with col_copy:
                        st.markdown(f"📋 **Mermaid代码预览**（可复制）")
                        st.code(mermaid_code, language="mermaid")
        
        # 轮次达到上限提示
        if max_rounds_reached:
            st.warning(f'⚠️ 对话轮次已达上限（{st.session_state.linmo_max_rounds}轮），请点击侧边栏的"重新开始引导"按钮重新开始。')
        
        # 输入区 - 使用st.chat_input，只在按Enter时触发
        if max_rounds_reached or st.session_state.linmo_is_processing:
            st.chat_input("对话轮次已达上限或正在处理中...", disabled=True, key="linmo_chat_disabled")
            linmo_user_input = None
        else:
            linmo_user_input = st.chat_input(
                "请输入当前面临的问题，或对当前思维导图的修改建议...",
                key=f"linmo_chat_input_{st.session_state.linmo_input_key_counter}"
            )
        
        # 处理用户输入（st.chat_input只在按Enter时返回非None）
        if linmo_user_input:
            st.session_state.linmo_is_processing = True
            
            # 添加用户消息到历史
            st.session_state.linmo_chat_history.append({
                "role": "user",
                "content": linmo_user_input
            })
            
            # 构建完整的对话上下文
            # System Prompt + 历史对话 + 当前输入
            messages_context = ""
            for msg in st.session_state.linmo_chat_history:
                if msg["role"] == "user":
                    messages_context += f"\n\n【用户】\n{msg['content']}"
                else:
                    messages_context += f"\n\n【Linmo】\n{msg['content']}"
            
            full_prompt = f"""请基于以下对话历史继续引导用户：
{messages_context}

请以思路引导助手Linmo的身份回复，严格按照输出格式要求（思考与反馈、Mermaid思维导图、引导追问）进行回复。"""
            
            # 流式生成回复
            st.markdown("#### 🤖 Linmo正在思考...")
            
            # 思考过程容器
            thinking_expander = st.expander("💭 查看模型思考过程", expanded=False)
            with thinking_expander:
                thinking_container = st.empty()
            
            response_container = st.empty()
            full_response = ""
            thinking_text = ""
            
            for chunk in call_gemini_stream(full_prompt, LINMO_SYSTEM_PROMPT):
                if chunk["type"] == "text":
                    full_response += chunk["content"]
                    response_container.markdown(full_response + " ▌")
                elif chunk["type"] == "thinking":
                    thinking_text += chunk["content"]
                    with thinking_expander:
                        thinking_container.markdown(thinking_text)
                elif chunk["type"] == "error":
                    st.error(f"生成失败: {chunk['content']}")
                    break
            
            if full_response:
                response_container.markdown(full_response)
                # 添加AI回复到历史
                st.session_state.linmo_chat_history.append({
                    "role": "assistant",
                    "content": full_response
                })
            
            st.session_state.linmo_is_processing = False
            # 清空输入框（通过增加计数器改变key，强制重建组件）
            st.session_state.linmo_input_key_counter += 1
            st.rerun()
    
    # ========== PUBGM WoW 玩法评审模块 ==========
    elif function_mode == "PUBGM WoW 玩法评审":
        # 标题和清空按钮
        title_col, clear_col = st.columns([6, 1])
        with title_col:
            st.markdown("### 🎮 PUBGM WoW 玩法评审")
        with clear_col:
            if st.button("🗑️ 清空会话", key="clear_wow_session", use_container_width=True):
                clear_module_session("PUBGM WoW 玩法评审")
                st.rerun()
        
        st.markdown("请上传 PUBG Mobile World of Wonder (WoW) 模式的游玩视频，AI 将分析玩法并给出评分。")
        st.info("💡 提示：建议上传1-3分钟的短视频，视频越长处理时间越久。支持格式：MP4, MOV, AVI, WEBM")
        
        # 初始化session state
        if "wow_review_result" not in st.session_state:
            st.session_state.wow_review_result = ""
        if "wow_is_processing" not in st.session_state:
            st.session_state.wow_is_processing = False
        if "wow_uploaded_video" not in st.session_state:
            st.session_state.wow_uploaded_video = None
        
        # 视频上传区
        uploaded_video = st.file_uploader(
            "上传游戏视频",
            type=['mp4', 'mov', 'avi', 'webm'],
            key="wow_video_uploader",
            help="支持 MP4, MOV, AVI, WEBM 格式，建议文件大小不超过200MB"
        )
        
        # 开始评审按钮
        start_review = st.button(
            "🎬 开始AI评审",
            key="wow_start_review",
            type="primary",
            disabled=uploaded_video is None or st.session_state.wow_is_processing
        )
        
        # 处理评审逻辑
        if start_review and uploaded_video and not st.session_state.wow_is_processing:
            st.session_state.wow_is_processing = True
            st.session_state.wow_review_result = ""
            
            # WoW 评审专用的 System Prompt
            WOW_REVIEW_PROMPT = """Role: 你是一位资深的 PUBG Mobile 游戏评测专家，专注于 "World of Wonder" (WoW) UGC 编辑器模式的玩法评审。你拥有敏锐的游戏设计嗅觉，能通过观看视频快速理解核心机制。请用中文回答。

Task: 请仔细观看上传的视频，分析该 UGC 地图的玩法，并输出一份专业的评审报告。

Output Format (Markdown):

# 🎮 PUBGM WoW 玩法评审报告

## 1. 玩法简述 (Gameplay Summary)
[请在此处用简练的语言描述这个地图是怎么玩的。包括：胜利条件、核心机制、玩家主要在做什么。]

## 2. 维度评分 (Scoring)
请基于 0-10 分进行打分，并给出简短的理由。

| 维度 | 评分 (0-10) | 评价理由 |
| :--- | :--- | :--- |
| **创新性 (Innovation)** | [x.x] | [是否脱离了常规玩法？机制是否新颖？] |
| **场景美观性 (Aesthetics)** | [x.x] | [地图搭建是否精细？光影、色彩和建筑结构如何？] |
| **关卡设计 (Level Design)** | [x.x] | [流程是否合理？难度曲线如何？是否有引导？] |
| **游戏完整性 (Completeness)** | [x.x] | [UI是否完善？是否有明显Bug？体验是否闭环？] |

## 3. 综合评价 (Final Verdict)
**最终平均分：[计算上述4项的平均分] / 10**

**总结点评：**
[请给出一段总结性的评价，指出这个作品最大的亮点是什么，以及最需要改进的一个地方。]
"""
            
            with st.spinner("正在上传视频并进行AI分析，请稍候...（视频越长耗时越久）"):
                temp_file_path = None
                uploaded_file_obj = None
                
                try:
                    # 创建 Client 实例
                    client = genai.Client(api_key=st.session_state.api_key)
                    
                    # 1. 临时保存视频文件
                    suffix = "." + uploaded_video.name.split(".")[-1].lower()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(uploaded_video.read())
                        temp_file_path = tmp_file.name
                    
                    st.info("📤 正在上传视频到AI服务...")
                    
                    # 2. 上传视频到 Gemini File API (使用 client.files.upload)
                    uploaded_file_obj = client.files.upload(
                        file=temp_file_path,
                        config={"display_name": "WoW_Gameplay"}
                    )
                    
                    st.info("⏳ 视频正在处理中，请耐心等待...")
                    
                    # 3. 等待视频处理完成
                    while uploaded_file_obj.state.name == "PROCESSING":
                        time.sleep(2)
                        uploaded_file_obj = client.files.get(name=uploaded_file_obj.name)
                    
                    if uploaded_file_obj.state.name == "FAILED":
                        st.error("❌ 视频处理失败，请尝试上传其他视频。")
                        st.session_state.wow_is_processing = False
                    elif uploaded_file_obj.state.name == "ACTIVE":
                        st.info("🤖 AI 正在分析视频内容...")
                        
                        # 4. 调用模型生成评审报告
                        # 获取当前选择的模型
                        current_model = st.session_state.get("selected_model", "gemini-2.0-flash")
                        
                        response = client.models.generate_content(
                            model=current_model,
                            contents=[uploaded_file_obj, WOW_REVIEW_PROMPT]
                        )
                        
                        if response and response.text:
                            st.session_state.wow_review_result = response.text
                            st.success("✅ 评审完成！")
                        else:
                            st.error("❌ AI 未能生成评审结果，请重试。")
                    else:
                        st.error(f"❌ 视频状态异常: {uploaded_file_obj.state.name}")
                
                except Exception as e:
                    st.error(f"❌ 评审过程中出错: {str(e)}")
                
                finally:
                    # 5. 清理：删除本地临时文件
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.remove(temp_file_path)
                        except:
                            pass
                    
                    # 可选：删除云端文件
                    if uploaded_file_obj:
                        try:
                            client.files.delete(name=uploaded_file_obj.name)
                        except:
                            pass
                    
                    st.session_state.wow_is_processing = False
        
        # 显示评审结果
        if st.session_state.wow_review_result:
            st.markdown("---")
            st.markdown("## 📋 评审报告")
            with st.chat_message("assistant", avatar="🎮"):
                st.markdown(st.session_state.wow_review_result)
            
            # 复制按钮
            st.download_button(
                label="📥 下载评审报告",
                data=st.session_state.wow_review_result,
                file_name=f"WoW_Review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )
    
    # 页脚
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "🎮 游戏策划Agent（酸奶） | Powered by Gemini API"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
