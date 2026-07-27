# 论文辅助研读助手

一个面向个人使用的英文论文精读工具。目标体验是：

- 左侧按段展示英文原文和中文翻译；
- 右侧按语义区块展示默认展开的深度 AI 解读；
- 划选原文、译文或解读后，通过右键进入 AI 问答；
- 用户主动收藏词汇，并在全文中持续高亮；
- 原始 PDF、解析结果、阅读进度和个人数据保存在本地。

## 当前状态

项目正在按阶段开发。

- 阶段 0：工程基础
- 阶段 0.5：PaddleOCR PP-StructureV3 解析验证
- 阶段 1：PDF 导入与结构化
- 阶段 2：双语阅读
- 阶段 3：语义分组与深度解读
- 阶段 4：个人词汇
- 阶段 5：AI 问答

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

### 2. 启动后端

项目锁定 Python 3.12，由 uv 管理：

```powershell
uv sync --project backend --python 3.12
uv run --project backend uvicorn app.main:app --app-dir backend --reload
```

后端地址：`http://127.0.0.1:8000`

### 3. 启动前端

```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```

前端地址：`http://localhost:5173`

## 测试

```powershell
uv run --project backend pytest backend/tests
npm run test --prefix frontend
```

## 数据与密钥

- `.env` 不会提交到 Git。
- 本地数据库默认保存在 `data/paper_reader.db`。
- 原始论文和后续 OCR 缓存均保存在本地忽略目录。
- 仓库只保留 `.env.example` 作为配置说明。

