import { useMemo, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";

import { translatePaper, type PaperDetail, type Paragraph } from "../api";

type PaperReaderProps = {
  paper: PaperDetail;
  llmConfigured: boolean;
  onPaperChange: (paper: PaperDetail) => void;
};

export function PaperReader({
  paper,
  llmConfigured,
  onPaperChange,
}: PaperReaderProps) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const translated = useMemo(
    () => paper.paragraphs.filter((paragraph) => paragraph.translated_text).length,
    [paper.paragraphs],
  );

  const generateTranslations = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const result = await translatePaper(paper.id);
      const byId = new Map(result.paragraphs.map((paragraph) => [paragraph.id, paragraph]));
      onPaperChange({
        ...paper,
        paragraphs: paper.paragraphs.map(
          (paragraph) => byId.get(paragraph.id) ?? paragraph,
        ),
      });
      setNotice(
        result.translated_count
          ? `已生成 ${result.translated_count} 段译文`
          : "译文已从本地缓存读取",
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "翻译失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="reader-shell">
      <header className="paper-header reader-header">
        <div>
          <p className="eyebrow">BILINGUAL READER</p>
          <h1>{paper.title}</h1>
          <div className="reader-meta">
            <span>{paper.page_count} 页</span>
            <span>{paper.paragraph_count} 段</span>
            <span>{translated}/{paper.paragraph_count} 已翻译</span>
          </div>
        </div>
        <div className="reader-actions">
          <a className="ghost-button" href={`/api/papers/${paper.id}/file`} target="_blank" rel="noreferrer">原始 PDF</a>
          <button className="primary-button" onClick={() => void generateTranslations()} disabled={busy}>
            {busy ? "翻译中…" : translated ? "补全译文" : "生成全文翻译"}
          </button>
        </div>
      </header>

      {!llmConfigured && (
        <div className="inline-warning">
          翻译功能已接好。请在根目录 `.env` 填写 DASHSCOPE_API_KEY 后生成译文。
        </div>
      )}
      {notice && <div className="reader-notice">{notice}</div>}

      <PanelGroup direction="horizontal" className="reader-panels" autoSaveId="paper-reader-layout">
        <Panel defaultSize={64} minSize={46}>
          <div className="bilingual-stream">
            {paper.paragraphs.map((paragraph) => (
              <BilingualParagraph
                key={paragraph.id}
                paperId={paper.id}
                paragraph={paragraph}
              />
            ))}
          </div>
        </Panel>
        <PanelResizeHandle className="resize-handle" />
        <Panel defaultSize={36} minSize={25}>
          <aside className="analysis-placeholder">
            <p className="eyebrow">DEEP ANALYSIS</p>
            <strong>深度解读将在下一阶段接入</strong>
            <p>右栏会按语义块对应左侧一个或多个自然段，内容默认完整展开。</p>
          </aside>
        </Panel>
      </PanelGroup>
    </section>
  );
}

function BilingualParagraph({
  paperId,
  paragraph,
}: {
  paperId: string;
  paragraph: Paragraph;
}) {
  return (
    <article className="bilingual-paragraph" id={`paragraph-${paragraph.id}`}>
      <div className="paragraph-location">
        <a
          href={`/api/papers/${paperId}/file#page=${paragraph.page_number}`}
          target="_blank"
          rel="noreferrer"
        >
          PAGE {paragraph.page_number}
        </a>
        <span>¶ {paragraph.paragraph_index + 1}</span>
      </div>
      <p className="source-text">{paragraph.source_text}</p>
      <p className={`translated-text ${paragraph.translated_text ? "" : "is-empty"}`}>
        {paragraph.translated_text ?? "等待生成中文翻译"}
      </p>
    </article>
  );
}
