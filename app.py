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
import base64
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

请根据用户提供的功能描述，生成完整、专业的策划案。"""

# 初始修正的System Prompt
INITIAL_FIX_SYSTEM_PROMPT = """你是资深游戏策划"酸奶"。

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

请阅读当前的策划案，提出尖锐的问题，指出逻辑漏洞、缺少的技术细节或不明确的边缘情况。

请只列出问题，不要修改文档。

问题格式要求：
- 使用数字编号列出问题
- 每个问题要具体、明确
- 聚焦于技术可行性、逻辑完整性、边界情况处理"""

# 策划修改的System Prompt
PLANNER_FIX_PROMPT = """你是策划酸奶。

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

# AI自检的System Prompt
SELF_CHECK_SYSTEM_PROMPT = """你是资深游戏策划"酸奶"，正在对策划案进行复检清单检查。

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
            
            # 构建配置 - 启用思考过程（如果模型支持）
            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                # 尝试启用思考模式（部分模型支持）
                thinking_config=types.ThinkingConfig(
                    thinking_budget=10000  # 允许的思考token数
                ) if "2.5" in get_selected_model() or "think" in get_selected_model().lower() else None
            )
            
            # 使用流式API
            response_stream = client.models.generate_content_stream(
                model=get_selected_model(),
                contents=prompt,
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
                                # 检查是否是思考内容
                                if hasattr(part, 'thought') and part.thought:
                                    thinking_text = part.text if hasattr(part, 'text') else str(part)
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
        return stream_to_container(prompt, GENERATE_PRD_SYSTEM_PROMPT, container, thinking_container, status_container)
    else:
        result = call_gemini(prompt, GENERATE_PRD_SYSTEM_PROMPT)
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


def main():
    """主函数"""
    # 页面配置
    st.set_page_config(
        page_title="游戏策划Agent（酸奶）",
        page_icon="🎮",
        layout="wide"
    )
    
# 初始化session_state
    if "generated_prd" not in st.session_state:
        st.session_state.generated_prd = ""
    if "optimized_prd" not in st.session_state:
        st.session_state.optimized_prd = ""
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    
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
            """)
        st.stop()
    
    # 功能选择
    function_mode = st.selectbox(
        "🔧 功能选择",
        options=["生成策划案", "优化策划案"],
        help="选择要使用的功能"
    )
    
    # 根据功能模式显示不同的输入界面
    if function_mode == "生成策划案":
        st.markdown("### 📝 生成新策划案")
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
                    st.warning("正在中止...")
            
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
            # 显示已生成的策划案
            st.markdown("### 📄 生成的策划案")
            st.markdown(st.session_state.generated_prd)
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
                    st.warning("正在中止...")
            
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
            st.markdown("### 📄 生成的策划案")
            st.markdown(st.session_state.generated_prd)
            
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
    
    else:  # 优化策划案
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
                    st.warning("正在中止...")
            
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
                    st.warning("正在中止...")
            
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
            st.markdown("### 📄 最终优化后的策划案")
            st.markdown(st.session_state.optimized_prd)
            
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
