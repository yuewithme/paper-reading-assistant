# 论文辅助研读助手

一个面向个人使用的英文论文精读工具。目标体验是：

- 左侧按段展示英文原文和中文翻译；
- 右侧按语义区块展示默认展开的深度 AI 解读；
- 划选原文、译文或解读后，通过右键进入 AI 问答；
- 用户主动收藏词汇，并在全文中持续高亮；
- 原始 PDF、解析结果、阅读进度和个人数据保存在本地。

## 当前状态

第一版阶段 0–8 已完成：

- PDF 后台导入、文件去重和 PaddleOCR PP-StructureV3 全量解析；
- 无论 PDF 是否带文本层，都统一执行 OCR、版面分析和阅读顺序恢复；
- OCR 完成后自动生成逐段中文翻译并缓存；
- 自动生成按语义块组织的默认深度解读和左右联动；
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

项目根目录已经准备好被 Git 忽略的 `.env`，只需填写：

```dotenv
DASHSCOPE_API_KEY=你的百炼Key
```

没有 Key 时仍可完成 OCR；自动翻译和解读会暂停，填好 Key、重启后端后在论文列表点击“重试”即可继续，不会重复 OCR。

### 2. 安装后端

项目锁定 Python 3.12，由 uv 管理：

```powershell
uv sync --project backend --python 3.12
```

PaddleOCR 和 CPU 版 PaddlePaddle 已是必需依赖，上述命令会一起安装。第一次导入会从百度 BOS 下载 PP-StructureV3 所需模型，因此明显慢于后续导入。

项目固定使用 `paddlepaddle==3.2.2`，以避开 Windows CPU 环境中 3.3.x 的 oneDNN/PIR 推理兼容问题。云服务器部署时也应以锁文件为准。

当前 `.env` 默认使用 `OCR_DEVICE=cpu`。部署到带 NVIDIA GPU 的 Linux 云服务器时，需要根据服务器 CUDA 版本安装对应的 `paddlepaddle-gpu`，再将其改为 `gpu:0`。

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

## 使用流程

1. 填写 `.env` 中的 `DASHSCOPE_API_KEY` 并启动前后端。
2. 点击“导入 PDF”。
3. 后端依次执行 PaddleOCR、逐段翻译和语义块深度解读。
4. 状态变为“就绪”后直接阅读；不需要再点击“生成翻译”或“生成深度解读”。

PP-StructureV3 会恢复多栏阅读顺序，并识别标题、正文、表格、图片说明和公式区域，同时保留页面号与区域坐标。它能显著改善复杂版面，但 OCR 与公式识别仍可能出错，尤其是低分辨率扫描、手写内容和非常规公式排版。

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

- `QWEN_TRANSLATION_MODEL`：逐段翻译，默认使用面向学术论文的 `qwen-mt-plus`；
- `QWEN_ANALYSIS_MODEL`：深度解读；
- `QWEN_CHAT_MODEL`：论文问答。

修改 `.env` 后需要重启后端。应用不会把 API Key 返回给前端。
