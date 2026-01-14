"""
文件解析模块
支持PDF、Word、TXT、MD文件的文本提取
"""

import io
import PyPDF2
import docx


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
