import { useEffect, useRef, useState } from "react";

import {
  deletePaper,
  enrichPaper,
  fetchHealth,
  fetchPaper,
  fetchPapers,
  importPaper,
  reparsePaper,
  waitForPaper,
  type HealthStatus,
  type PaperDetail,
  type PaperSummary,
} from "./api";
import { PaperReader } from "./components/PaperReader";
import "./styles.css";

type LoadState = "loading" | "ready" | "offline";
const ACTIVE_PAPER_STATUSES = ["queued", "processing", "ocr_complete", "enriching"];

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<PaperDetail | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const hasActivePaper = papers.some((paper) => ACTIVE_PAPER_STATUSES.includes(paper.status));

  const refreshPapers = async () => setPapers(await fetchPapers());

  useEffect(() => {
    let active = true;
    Promise.all([fetchHealth(), fetchPapers()])
      .then(([healthResult, paperResult]) => {
        if (!active) return;
        setHealth(healthResult);
        setPapers(paperResult);
        setLoadState("ready");
      })
      .catch(() => active && setLoadState("offline"));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!hasActivePaper) return;
    const timer = window.setInterval(() => {
      void fetchPapers().then(setPapers).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [hasActivePaper]);

  const handleImport = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setNotice("正在保存并解析 PDF…");
    try {
      const paper = await importPaper(file);
      await refreshPapers();
      setSelectedPaper(await waitForPaper(paper.id));
      await refreshPapers();
      setNotice(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "导入失败");
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const openPaper = async (paper: PaperSummary) => {
    setBusy(true);
    try {
      setSelectedPaper(
        ACTIVE_PAPER_STATUSES.includes(paper.status)
          ? await waitForPaper(paper.id)
          : await fetchPaper(paper.id),
      );
      setNotice(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "读取论文失败");
    } finally {
      setBusy(false);
    }
  };

  const retryPaper = async (paper: PaperSummary, forceOcr = false) => {
    setBusy(true);
    const retryAi = ["ai_failed", "ai_configuration_required"].includes(paper.status);
    setNotice(retryAi ? "正在继续生成翻译与深度解读…" : "正在使用 PaddleOCR 重新解析…");
    try {
      if (retryAi) {
        await enrichPaper(paper.id);
      } else {
        await reparsePaper(paper.id, forceOcr);
      }
      setSelectedPaper(await waitForPaper(paper.id));
      await refreshPapers();
      setNotice(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "重新解析失败");
    } finally {
      setBusy(false);
    }
  };

  const removePaper = async (paper: PaperSummary) => {
    if (!window.confirm(`删除《${paper.title}》及其本地数据？`)) return;
    await deletePaper(paper.id);
    if (selectedPaper?.id === paper.id) setSelectedPaper(null);
    await refreshPapers();
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand brand-button" onClick={() => setSelectedPaper(null)}>
          <span className="brand-mark" aria-hidden="true">研</span>
          <span>
            <span className="eyebrow">PAPER READING STUDIO</span>
            <h1>论文辅助研读助手</h1>
          </span>
        </button>
        <div className="topbar-actions">
          <span className={`service-state service-state--${loadState}`}>
            <span className="service-dot" />
            {loadState === "ready" ? "本地服务在线" : loadState === "offline" ? "后端未连接" : "正在连接"}
          </span>
          <button className="ghost-button action-button" onClick={() => setSettingsOpen(true)}>设置</button>
          <label className={`primary-button ${busy ? "is-disabled" : ""}`}>
            {busy ? "处理中…" : "导入 PDF"}
            <input
              ref={fileInput}
              className="visually-hidden"
              type="file"
              accept="application/pdf,.pdf"
              disabled={busy}
              onChange={(event) => void handleImport(event.target.files?.[0])}
            />
          </label>
        </div>
      </header>

      <main className="workspace">
        <aside className="library-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">LIBRARY</p><h2>我的论文</h2></div>
            <span className="paper-count">{papers.length}</span>
          </div>
          <div className="paper-list" aria-label="论文列表">
            {papers.map((paper) => (
              <div className={`paper-item ${selectedPaper?.id === paper.id ? "is-active" : ""}`} key={paper.id}>
                <button className="paper-open" onClick={() => void openPaper(paper)}>
                  <span className="paper-file-badge">PDF</span>
                  <span>
                    <strong>{paper.title}</strong>
                    <small>
                      {ACTIVE_PAPER_STATUSES.includes(paper.status)
                        ? paper.status === "enriching"
                          ? `自动生成中 · ${paper.translations_completed}/${paper.paragraph_count} 段 · ${paper.analysis_groups_completed}/${paper.analysis_group_count || "?"} 组`
                          : `PaddleOCR · ${paper.pages_processed}/${paper.page_count || "?"} 页`
                        : `${paper.page_count} 页 · ${paper.paragraph_count} 段 · ${Math.round(paper.read_progress * 100)}%`}
                    </small>
                  </span>
                </button>
                {["failed", "ai_failed", "ai_configuration_required"].includes(paper.status) && (
                  <button className="retry-button" onClick={() => void retryPaper(paper)}>重试</button>
                )}
                <button className="icon-button" aria-label={`删除 ${paper.title}`} onClick={() => void removePaper(paper)}>×</button>
              </div>
            ))}
            {papers.length === 0 && (
              <div className="library-empty"><span>01</span><p>导入英文 PDF，论文和解析结果会保存在本地。</p></div>
            )}
          </div>
          <div className="config-card">
            <p>Qwen</p>
            <strong>{health?.llm_configured ? "已配置" : "等待 API Key"}</strong>
            <small>密钥只从本地 .env 读取</small>
          </div>
        </aside>

        {selectedPaper ? (
          <PaperReader
            paper={selectedPaper}
            llmConfigured={Boolean(health?.llm_configured)}
            onPaperChange={setSelectedPaper}
          />
        ) : (
          <section className="welcome-panel">
            <div className="welcome-copy">
              <span className="stage-label">1.0 · LOCAL PAPER READING STUDIO</span>
              <h2>读懂论文，<br />不止是翻译论文。</h2>
              <p>导入 PDF 后，原文、译文、深度解读、主动词汇与 AI 问答会保存在同一个本地阅读工作台。</p>
              {notice && <div className="inline-warning">{notice}</div>}
            </div>
            <div className="reader-preview" aria-label="PDF 结构化预览">
              <div className="preview-column preview-column--paper">
                <span className="preview-kicker">PDF → DOCUMENT BLOCKS</span>
                <div className="preview-line preview-line--long" />
                <div className="preview-line preview-line--medium" />
                <div className="preview-translation"><div className="preview-line preview-line--long" /><div className="preview-line preview-line--short" /></div>
              </div>
              <div className="preview-column preview-column--analysis">
                <span className="preview-kicker">PAGE + POSITION</span>
                <div className="analysis-block"><strong>可定位内容</strong><div className="preview-line preview-line--long" /><div className="preview-line preview-line--medium" /></div>
              </div>
            </div>
          </section>
        )}
      </main>
      {notice && selectedPaper && <div className="toast">{notice}</div>}
      {settingsOpen && (
        <div className="modal-backdrop" onMouseDown={() => setSettingsOpen(false)}>
          <section className="settings-modal" onMouseDown={(event) => event.stopPropagation()}>
            <header>
              <div><p className="eyebrow">LOCAL SETTINGS</p><h2>运行设置</h2></div>
              <button className="icon-button" aria-label="关闭设置" onClick={() => setSettingsOpen(false)}>×</button>
            </header>
            <dl>
              <div><dt>本地 API</dt><dd>{loadState === "ready" ? "运行正常" : "未连接"}</dd></div>
              <div><dt>Qwen</dt><dd>{health?.llm_configured ? "API Key 已加载" : "等待 DASHSCOPE_API_KEY"}</dd></div>
              <div><dt>数据位置</dt><dd>项目根目录 / data</dd></div>
              <div><dt>OCR</dt><dd>PaddleOCR PP-StructureV3（所有 PDF 统一使用）</dd></div>
            </dl>
            <div className="settings-code">
              <span>在根目录创建 `.env`，填写：</span>
              <code>DASHSCOPE_API_KEY=你的Key</code>
            </div>
            <p>修改 `.env` 后重启后端即可。密钥不会显示在页面，也不会提交到 Git。</p>
          </section>
        </div>
      )}
    </div>
  );
}
