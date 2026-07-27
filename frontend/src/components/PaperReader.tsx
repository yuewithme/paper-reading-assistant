import { useEffect, useMemo, useState } from "react";

import {
  fetchSemanticGroups,
  generateAnalysis,
  translatePaper,
  type PaperDetail,
  type Paragraph,
  type SemanticGroup,
} from "../api";

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
  const [groups, setGroups] = useState<SemanticGroup[]>([]);
  const [busyTask, setBusyTask] = useState<"translation" | "analysis" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [hoveredGroup, setHoveredGroup] = useState<string | null>(null);
  const translated = useMemo(
    () => paper.paragraphs.filter((paragraph) => paragraph.translated_text).length,
    [paper.paragraphs],
  );
  const paragraphMap = useMemo(
    () => new Map(paper.paragraphs.map((paragraph) => [paragraph.id, paragraph])),
    [paper.paragraphs],
  );

  useEffect(() => {
    let active = true;
    fetchSemanticGroups(paper.id)
      .then((result) => active && setGroups(result))
      .catch((error) => active && setNotice(error instanceof Error ? error.message : "分组失败"));
    return () => {
      active = false;
    };
  }, [paper.id]);

  const generateTranslations = async () => {
    setBusyTask("translation");
    setNotice(null);
    try {
      const result = await translatePaper(paper.id);
      const byId = new Map(result.paragraphs.map((paragraph) => [paragraph.id, paragraph]));
      onPaperChange({
        ...paper,
        paragraphs: paper.paragraphs.map((paragraph) => byId.get(paragraph.id) ?? paragraph),
      });
      setNotice(result.translated_count ? `已生成 ${result.translated_count} 段译文` : "译文已从缓存读取");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "翻译失败");
    } finally {
      setBusyTask(null);
    }
  };

  const generateDeepAnalysis = async () => {
    setBusyTask("analysis");
    setNotice(null);
    try {
      const result = await generateAnalysis(paper.id);
      const byId = new Map(result.groups.map((group) => [group.id, group]));
      setGroups((current) => current.map((group) => byId.get(group.id) ?? group));
      setNotice(result.generated_count ? `已生成 ${result.generated_count} 个语义块解读` : "深度解读已从缓存读取");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "深度解读失败");
    } finally {
      setBusyTask(null);
    }
  };

  return (
    <section className="reader-shell">
      <header className="paper-header reader-header">
        <div>
          <p className="eyebrow">BILINGUAL READER + DEEP ANALYSIS</p>
          <h1>{paper.title}</h1>
          <div className="reader-meta">
            <span>{paper.page_count} 页</span><span>{paper.paragraph_count} 段</span>
            <span>{translated}/{paper.paragraph_count} 已翻译</span><span>{groups.length} 个语义块</span>
          </div>
        </div>
        <div className="reader-actions">
          <a className="ghost-button" href={`/api/papers/${paper.id}/file`} target="_blank" rel="noreferrer">原始 PDF</a>
          <button className="ghost-button action-button" onClick={() => void generateTranslations()} disabled={busyTask !== null}>
            {busyTask === "translation" ? "翻译中…" : translated ? "补全译文" : "生成翻译"}
          </button>
          <button className="primary-button" onClick={() => void generateDeepAnalysis()} disabled={busyTask !== null}>
            {busyTask === "analysis" ? "解读中…" : "生成深度解读"}
          </button>
        </div>
      </header>
      {!llmConfigured && <div className="inline-warning reader-warning">请在 `.env` 填写 DASHSCOPE_API_KEY，翻译和深度解读结果会自动缓存。</div>}
      {notice && <div className="reader-notice">{notice}</div>}

      <div className="aligned-reader-grid">
        <div className="column-label column-label--left">原文 + 中文翻译</div>
        <div className="column-divider" />
        <div className="column-label column-label--right">深度 AI 解读</div>
        {groups.map((group) => {
          const paragraphs = group.paragraph_ids
            .map((id) => paragraphMap.get(id))
            .filter((item): item is Paragraph => Boolean(item));
          const active = hoveredGroup === group.id;
          return (
            <div className="semantic-group-row" key={group.id}>
              <section
                className={`semantic-source ${active ? "is-linked" : ""}`}
                onMouseEnter={() => setHoveredGroup(group.id)}
                onMouseLeave={() => setHoveredGroup(null)}
              >
                {paragraphs.map((paragraph) => (
                  <BilingualParagraph key={paragraph.id} paperId={paper.id} paragraph={paragraph} />
                ))}
              </section>
              <div className="column-divider" />
              <aside
                className={`semantic-analysis ${active ? "is-linked" : ""}`}
                onMouseEnter={() => setHoveredGroup(group.id)}
                onMouseLeave={() => setHoveredGroup(null)}
              >
                <span className="group-number">GROUP {group.group_index + 1}</span>
                {group.analysis_text ? (
                  <p>{group.analysis_text}</p>
                ) : (
                  <p className="analysis-empty">等待生成深度解读。一个解读可对应左侧多个自然段。</p>
                )}
              </aside>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function BilingualParagraph({ paperId, paragraph }: { paperId: string; paragraph: Paragraph }) {
  return (
    <article className="bilingual-paragraph" id={`paragraph-${paragraph.id}`}>
      <div className="paragraph-location">
        <a href={`/api/papers/${paperId}/file#page=${paragraph.page_number}`} target="_blank" rel="noreferrer">
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
