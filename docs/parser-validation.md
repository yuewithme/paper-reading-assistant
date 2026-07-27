# 解析引擎验证

应用内部只依赖 `ParsedDocument` 和 `DocumentBlock`，不会直接依赖某个 OCR
供应方的返回结构。无论 PDF 是否带文本层，默认都统一使用 PaddleOCR
PP-StructureV3，避免不同来源的论文产生两套版面行为。PDF 会逐页渲染，每页结果
立即提交数据库；第一页完成后即可进入阅读页。

## 本地安装 PaddleOCR

```powershell
uv sync --project backend --python 3.12
```

PP-StructureV3 首次运行会下载模型，因此模型缓存不会提交到 Git。

## 固定验证矩阵

正式发布前使用下列五类样本执行导入，并检查 JSON 结果、阅读顺序和坐标：

| 样本 | 重点 |
| --- | --- |
| 原生文本论文 | Paddle 结果段落完整 |
| 双栏论文 | 阅读顺序不跨栏 |
| 扫描论文 | 自动进入 PaddleOCR |
| 公式密集论文 | 公式与正文分开 |
| 表格密集论文 | 表格、表题和正文分开 |

自动化测试使用小型合成 PDF 验证路由和统一模型，不把大型模型或第三方论文
提交到仓库。真实样本的输出放入 `data/validation/`，该目录属于本地数据。
