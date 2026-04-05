# EchoSub

开源视频字幕翻译工具。上传视频，自动语音识别、智能分句、AI翻译，生成多语言字幕文件。

## 快速开始

### 环境要求

- Docker + Docker Compose
- 一个 OpenAI 兼容的 LLM API（OpenAI / Gemini / DeepSeek 等）
- 一个 Whisper 兼容的语音识别 API

### 一键启动

```bash
git clone https://github.com/airhao3/echosub-open.git
cd echosub-open
docker-compose up -d
```

等待容器构建完成后，打开浏览器访问 `http://localhost:8080`。

### 配置 API

首次使用需要配置 API 密钥：

1. 进入「系统设置」页面
2. 填写翻译大模型配置：
   - 接口地址（如 `https://api.openai.com/v1`）
   - API 密钥
   - 点击「测试连接」，从返回的模型列表中选择模型
3. 填写语音识别配置：
   - Whisper 接口地址
   - API 密钥（部分服务可留空）
   - 模型名称
   - 点击「测试连接」确认可用
4. 点击「保存设置」

### 使用流程

1. 进入「新建任务」页面
2. 上传视频文件（支持 MP4 / MOV / AVI / MKV / WebM）
3. 填写任务标题
4. 选择源语言和目标语言
5. 点击「创建视频任务」
6. 等待处理完成（可在处理页面查看进度）
7. 完成后进入预览页面查看结果

### 导出字幕

处理完成后，在预览页面的字幕编辑器中点击「下载文件」按钮，可导出以下格式：

- SRT 字幕文件
- VTT 字幕文件

导出的字幕文件包含原文和翻译两个版本。

> 当前版本不支持字幕烧录到视频中。如需烧录，可使用导出的 SRT/VTT 文件配合 FFmpeg 或其他视频编辑工具完成。

## 本地开发

如不使用 Docker，可以本地运行：

```bash
# 安装 Redis
brew install redis && brew services start redis   # macOS
# 或 apt install redis-server && systemctl start redis  # Linux

# 后端
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements_lightweight.txt
pip install email-validator json-repair openai httpx
python manage.py runall    # 同时启动 API 服务和 Worker

# 前端（另开终端）
cd frontend
npm install
npm start                  # 访问 http://localhost:3000
```

## 可调参数

在「系统设置」页面可以调整：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 分割触发时长 | 超过此时长的片段会被分割 | 2.5s |
| 分割触发词数 | 超过此词数的片段会被分割 | 8 |
| 停顿分割阈值 | 词间停顿超过此值时分割 | 0.3s |
| 每行最大词数 | 单行字幕的词数上限 | 7 |
| 逗号分割 | 是否在逗号处额外分割 | 开启 |

## 技术栈

- 后端：Python / FastAPI / Celery / SQLite / Redis
- 前端：React / TypeScript / MUI
- 语音识别：OpenAI Whisper 兼容 API
- 翻译：OpenAI 兼容 LLM API

## 许可证

MIT
