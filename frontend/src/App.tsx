import { useEffect, useRef, useState } from "react";

import {
  deletePaper,
  fetchHealth,
  fetchPaper,
  fetchPapers,
  importPaper,
  type HealthStatus,
  type PaperDetail,
  type PaperSummary,
} from "./api";
import { PaperReader } from "./components/PaperReader";
import "./styles.css";

type LoadState = "loading" | "ready" | "offline";

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<PaperDetail | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

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

  const handleImport = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setNotice("正在保存并解析 PDF…");
    try {
      const paper = await importPaper(file);
      await refreshPapers();
      setSelectedPaper(await fetchPaper(paper.id));
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
      setSelectedPaper(await fetchPaper(paper.id));
      setNotice(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "读取论文失败");
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
                  <span><strong>{paper.title}</strong><small>{paper.page_count} 页 · {paper.paragraph_count} 段</small></span>
                </button>
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
              <span className="stage-label">阶段 1 · PDF 导入与结构化</span>
              <h2>把 PDF 变成<br />可以精读的内容。</h2>
              <p>优先读取原生文本层；扫描页自动转入 PaddleOCR。页码、阅读顺序和定位信息会一起保存。</p>
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
    </div>
  );
}
