# 论文辅助研读助手

一个面向个人使用的英文论文精读工具。目标体验是：

- 左侧按段展示英文原文和中文翻译；
- 右侧按语义区块展示默认展开的深度 AI 解读；
- 划选原文、译文或解读后，通过右键进入 AI 问答；
- 用户主动收藏词汇，并在全文中持续高亮；
- 原始 PDF、解析结果、阅读进度和个人数据保存在本地。

## 当前状态

第一版阶段 0–6 已完成：

- PDF 后台导入、文件去重和原生文本层解析；
- 扫描页的 PaddleOCR PP-StructureV3 可选解析路径；
- 原文下方逐段中文翻译及本地结果缓存；
- 按语义块组织的默认深度解读和左右联动；
- 主动划词收藏、语境释义、掌握状态和全文多色高亮；
- 选中文本右键进入 AI 问答，自动组合相邻段落和全文相关内容；
- 论文证据定位、连续对话、阅读进度恢复和失败重试。

详细计划见：

- [产品开发计划.md](./产品开发计划.md)
- [开源模块调研.md](./开源模块调研.md)

## 技术栈

- 前端：React、TypeScript、Vite
- 后端：FastAPI、SQLAlchemy、SQLite
- PDF/OCR：PaddleOCR PP-StructureV3
- 原始 PDF 查看：PDF.js
- LLM：Qwen，使用阿里云百炼 OpenAI 兼容接口

## 本地启动

### 1. 配置环境变量

```powershell
Copy-Item .env.example .env
```

在 `.env` 中填写 `DASHSCOPE_API_KEY`。没有 Key 时也可以启动应用，只是 AI 功能不可用。

### 2. 安装后端

项目锁定 Python 3.12，由 uv 管理：

```powershell
uv sync --project backend --python 3.12
```

需要识别扫描 PDF 时安装 PaddleOCR 可选依赖：

```powershell
uv sync --project backend --python 3.12 --extra ocr
```

PaddleOCR 第一次运行会下载模型。只阅读带文本层的 PDF 时可以不安装该可选依赖。

### 3. 启动后端

```powershell
uv run --project backend uvicorn app.main:app --app-dir backend --reload
```

后端地址：`http://127.0.0.1:8000`

### 4. 启动前端

```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```

前端地址：`http://localhost:5173`

## 测试

```powershell
uv run --project backend pytest backend/tests
uv run --project backend ruff check backend
npm run test --prefix frontend
npm run build --prefix frontend
```

## 数据与密钥

- `.env` 不会提交到 Git。
- 本地数据库默认保存在 `data/paper_reader.db`。
- 原始论文和后续 OCR 缓存均保存在本地忽略目录。
- 仓库只保留 `.env.example` 作为配置说明。

## Qwen 配置

默认使用阿里云百炼北京地域的 OpenAI 兼容接口。模型可在 `.env` 中分别配置：

- `QWEN_TRANSLATION_MODEL`：逐段翻译；
- `QWEN_ANALYSIS_MODEL`：深度解读；
- `QWEN_CHAT_MODEL`：论文问答。

修改 `.env` 后需要重启后端。应用不会把 API Key 返回给前端。
