import { useEffect, useState } from "react";

import { fetchHealth, fetchPapers, type HealthStatus, type PaperSummary } from "./api";
import "./styles.css";

type LoadState = "loading" | "ready" | "offline";

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  useEffect(() => {
    let active = true;

    Promise.all([fetchHealth(), fetchPapers()])
      .then(([healthResult, paperResult]) => {
        if (!active) return;
        setHealth(healthResult);
        setPapers(paperResult);
        setLoadState("ready");
      })
      .catch(() => {
        if (!active) return;
        setLoadState("offline");
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            研
          </span>
          <div>
            <p className="eyebrow">PAPER READING STUDIO</p>
            <h1>论文辅助研读助手</h1>
          </div>
        </div>

        <div className="topbar-actions">
          <span className={`service-state service-state--${loadState}`}>
            <span className="service-dot" />
            {loadState === "ready" ? "本地服务在线" : loadState === "offline" ? "后端未连接" : "正在连接"}
          </span>
          <button className="primary-button" disabled title="将在 PDF 导入阶段开放">
            导入 PDF
          </button>
        </div>
      </header>

      <main className="workspace">
        <aside className="library-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">LIBRARY</p>
              <h2>我的论文</h2>
            </div>
            <span className="paper-count">{papers.length}</span>
          </div>

          {papers.length > 0 ? (
            <ul className="paper-list">
              {papers.map((paper) => (
                <li key={paper.id} className="paper-item">
                  <span className="paper-file-badge">PDF</span>
                  <div>
                    <strong>{paper.title}</strong>
                    <small>{paper.file_name}</small>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="library-empty">
              <span>01</span>
              <p>论文会保存在本地，并自动恢复上次阅读位置。</p>
            </div>
          )}

          <div className="config-card">
            <p>Qwen</p>
            <strong>{health?.llm_configured ? "已配置" : "等待 API Key"}</strong>
            <small>密钥只从本地 .env 读取</small>
          </div>
        </aside>

        <section className="welcome-panel">
          <div className="welcome-copy">
            <span className="stage-label">阶段 0 · 工程基础</span>
            <h2>
              读懂论文，
              <br />
              不止是翻译论文。
            </h2>
            <p>
              原文、翻译与深度 AI 解读将在同一阅读流中按语义对齐。划选任何内容，即可直接进入问答。
            </p>
          </div>

          <div className="reader-preview" aria-label="双栏阅读布局预览">
            <div className="preview-column preview-column--paper">
              <span className="preview-kicker">ORIGINAL + TRANSLATION</span>
              <div className="preview-line preview-line--long" />
              <div className="preview-line preview-line--medium" />
              <div className="preview-translation">
                <div className="preview-line preview-line--long" />
                <div className="preview-line preview-line--short" />
              </div>
              <div className="preview-line preview-line--medium" />
            </div>
            <div className="preview-column preview-column--analysis">
              <span className="preview-kicker">DEEP ANALYSIS</span>
              <div className="analysis-block">
                <strong>语义解读</strong>
                <div className="preview-line preview-line--long" />
                <div className="preview-line preview-line--medium" />
                <div className="preview-line preview-line--short" />
              </div>
            </div>
          </div>

          <footer className="workspace-footer">
            <span>本地优先</span>
            <span>PaddleOCR</span>
            <span>Qwen</span>
          </footer>
        </section>
      </main>
    </div>
  );
}

