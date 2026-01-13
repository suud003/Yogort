# 🎮 游戏策划Agent（酸奶）

一个基于 Gemini API 的智能策划辅助工具，具备生成标准化策划案和基于 Reflection 架构优化策划案的功能。

## ✨ 功能特性

### 1. 生成策划案
- 根据用户输入的功能描述，自动生成包含 10 个标准章节的策划案
- 严格遵循中文输出规范，无英文标题
- 使用数字层级格式（1、2、3... 或 1.1、1.2...）
- 自动进行 AI 复检清单检查

### 2. 优化策划案（Reflection 架构）
- **Step 1**: 基于复检清单对旧策划案进行初始修正
- **Step 2**: 多轮 Reflection 循环优化
  - 开发人员角色：提出尖锐问题和技术挑战
  - 策划角色：针对问题进行修改完善
- **Step 3**: AI 自动进行最终复检清单检查
- 支持自定义迭代轮次（1-10轮）

### 3. 标准化输出结构
策划案包含以下 10 个章节：
1. 功能概述
2. 战略定位
3. 用户场景
4. 功能规格
5. AI处理逻辑
6. 容错设计
7. 验收标准
8. 能力边界
9. 技术依赖
10. 版本规划

### 4. AI 复检清单
每次输出策划案时，AI 会自动检查：
- ✅ 通过 / ⚠️ 部分满足 / ❌ 缺失
- 提供具体改进建议
- 给出总体评价

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

#### 方式一：网页界面配置（推荐本地使用）
直接在网页左侧侧边栏输入您的 Gemini API Key 即可使用。

#### 方式二：Secrets 配置（推荐云端部署）
1. 本地开发时，在项目根目录创建 `.streamlit/secrets.toml` 文件：
```toml
GOOGLE_API_KEY = "your-api-key-here"
```

2. Streamlit Cloud 部署时，在 Settings → Secrets 中添加：
```toml
GOOGLE_API_KEY = "your-api-key-here"
```

### 3. 运行应用

```bash
streamlit run app.py
```

应用将在浏览器中自动打开，默认地址：`http://localhost:8501`

## ☁️ 云端部署（Streamlit Cloud）

### 部署步骤

1. **准备 GitHub 仓库**
   - 确保仓库包含 `app.py` 和 `requirements.txt`
   - 不要将 `.streamlit/secrets.toml` 提交到仓库

2. **注册 Streamlit Cloud**
   - 访问 [share.streamlit.io](https://share.streamlit.io/)
   - 使用 GitHub 账号登录

3. **部署应用**
   - 点击 "New app"
   - 选择仓库、分支和主文件（app.py）
   - 点击 "Deploy!"

4. **配置 Secrets**
   - 部署后进入应用设置
   - 在 Settings → Secrets 中添加：
   ```toml
   GOOGLE_API_KEY = "your-api-key-here"
   ```

### 支持的 Secrets 变量
- `GOOGLE_API_KEY` - Google Gemini API 密钥
- `GEMINI_API_KEY` - 备选名称（二选一）

## 📋 使用说明

### 生成策划案
1. 在功能选择中选择 "生成策划案"
2. 在文本框中输入功能描述
3. 点击 "🚀 生成策划案" 按钮
4. 等待生成完成，查看策划案和 AI 复检结果
5. 可下载 Markdown 格式的策划案

### 优化策划案
1. 在功能选择中选择 "优化策划案"
2. 在"原策划案"文本框中粘贴需要优化的策划案
3. 在"修改意见"文本框中输入优化方向
4. 设置迭代轮次（默认 3 轮）
5. 点击 "🔄 开始优化" 按钮
6. 观察每轮的开发人员提问和策划优化过程
7. 查看最终优化结果和 AI 复检结果

## 📁 项目结构

```
project agent/
├── app.py                              # 主应用文件
├── requirements.txt                    # 依赖列表
├── README.md                           # 项目说明
└── .streamlit/
    └── secrets.toml.example            # Secrets 配置示例
```

## 🔧 技术栈

- **前端框架**: Streamlit
- **AI 模型**: Google Gemini 3 pro
- **SDK**: google-genai

## 📦 依赖

```
streamlit>=1.28.0
google-genai>=1.0.0
```

## ⚠️ 注意事项

1. 请确保已正确配置 Gemini API Key
2. API 调用需要网络连接
3. 优化策划案功能会进行多轮 API 调用，请注意 API 配额
4. 建议在稳定的网络环境下使用

## 📝 许可证

MIT License
