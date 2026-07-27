import { type MouseEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  createVocabulary,
  fetchPaper,
  fetchSemanticGroups,
  fetchVocabulary,
  generateAnalysis,
  saveReadingProgress,
  translatePaper,
  type PaperDetail,
  type Paragraph,
  type SemanticGroup,
  type VocabularyItem,
} from "../api";
import { AcademicMarkdown } from "./AcademicMarkdown";
import { AnalysisMarkdown } from "./AnalysisMarkdown";
import { ChatPanel, type ChatAnchor } from "./ChatPanel";
import { VocabularyDrawer } from "./VocabularyDrawer";

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
  const [vocabulary, setVocabulary] = useState<VocabularyItem[]>([]);
  const [vocabularyOpen, setVocabularyOpen] = useState(false);
  const [selection, setSelection] = useState<{
    text: string;
    paragraphId: string | null;
    x: number;
    y: number;
  } | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatAnchor, setChatAnchor] = useState<ChatAnchor>({
    selectedText: null,
    paragraphId: null,
  });
  const readerRef = useRef<HTMLDivElement>(null);
  const progressTimer = useRef<number | null>(null);
  const restoredPosition = useRef(false);
  const ocrInProgress = ["queued", "processing"].includes(paper.status);
  const pipelineActive = [
    "queued",
    "processing",
    "ocr_complete",
    "enriching",
  ].includes(paper.status);
  const translated = useMemo(
    () => paper.paragraphs.filter((paragraph) => paragraph.translated_text).length,
    [paper.paragraphs],
  );
  const analysisBlockCount = useMemo(
    () => groups.filter((group) => group.analysis_status !== "skipped").length,
    [groups],
  );
  const paragraphMap = useMemo(
    () => new Map(paper.paragraphs.map((paragraph) => [paragraph.id, paragraph])),
    [paper.paragraphs],
  );
  const visibleGroups = useMemo<SemanticGroup[]>(
    () =>
      groups.length
        ? groups
        : paper.paragraphs.map((paragraph, index) => ({
            id: `pending-${paragraph.id}`,
            group_index: index,
            paragraph_ids: [paragraph.id],
            analysis_text: null,
            analysis_status: "pending",
          })),
    [groups, paper.paragraphs],
  );

  useEffect(() => {
    let active = true;
    setGroups([]);
    const groupRequest = ocrInProgress
      ? Promise.resolve<SemanticGroup[]>([])
      : fetchSemanticGroups(paper.id);
    Promise.all([groupRequest, fetchVocabulary(paper.id)])
      .then(([groupResult, vocabularyResult]) => {
        if (!active) return;
        setGroups(groupResult);
        setVocabulary(vocabularyResult);
      })
      .catch((error) => active && setNotice(error instanceof Error ? error.message : "分组失败"));
    return () => {
      active = false;
    };
  }, [paper.id, ocrInProgress]);

  useEffect(() => {
    if (!pipelineActive) return;
    let active = true;
    let refreshing = false;
    const refresh = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        const nextPaper = await fetchPaper(paper.id);
        if (!active) return;
        onPaperChange(nextPaper);
        if (!["queued", "processing"].includes(nextPaper.status)) {
          const nextGroups = await fetchSemanticGroups(paper.id);
          if (active) setGroups(nextGroups);
        }
      } catch (error) {
        if (active) {
          setNotice(error instanceof Error ? error.message : "刷新处理进度失败");
        }
      } finally {
        refreshing = false;
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [onPaperChange, paper.id, pipelineActive]);

  useEffect(() => {
    if (restoredPosition.current || !groups.length || !paper.last_read_position) return;
    restoredPosition.current = true;
    window.setTimeout(() => {
      document.getElementById(`paragraph-${paper.last_read_position}`)?.scrollIntoView({
        block: "center",
      });
    }, 0);
  }, [groups.length, paper.last_read_position]);

  useEffect(
    () => () => {
      if (progressTimer.current) window.clearTimeout(progressTimer.current);
    },
    [],
  );

  const trackReadingProgress = () => {
    const container = readerRef.current;
    if (!container) return;
    const denominator = Math.max(1, container.scrollHeight - container.clientHeight);
    const progress = Math.min(1, Math.max(0, container.scrollTop / denominator));
    const paragraphs = Array.from(
      container.querySelectorAll<HTMLElement>("[data-paragraph-id]"),
    );
    const position = [...paragraphs]
      .reverse()
      .find((element) => element.offsetTop <= container.scrollTop + 180)
      ?.dataset.paragraphId ?? null;
    if (progressTimer.current) window.clearTimeout(progressTimer.current);
    progressTimer.current = window.setTimeout(() => {
      void saveReadingProgress(paper.id, progress, position);
    }, 600);
  };

  useEffect(() => {
    const close = () => setSelection(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  const openSelectionMenu = (event: MouseEvent<HTMLElement>) => {
    const text = window.getSelection()?.toString().trim().slice(0, 500);
    if (!text) return;
    event.preventDefault();
    const element = event.target as HTMLElement;
    const paragraphId = element.closest<HTMLElement>("[data-paragraph-id]")?.dataset.paragraphId ?? null;
    setSelection({ text, paragraphId, x: event.clientX, y: event.clientY });
  };

  const saveSelection = async () => {
    if (!selection) return;
    setBusyTask("translation");
    try {
      const item = await createVocabulary(paper.id, selection.text, selection.paragraphId);
      setVocabulary((current) =>
        current.some((candidate) => candidate.id === item.id) ? current : [item, ...current],
      );
      setVocabularyOpen(true);
      setNotice(`已收藏“${item.display_text}”`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "收藏失败");
    } finally {
      setBusyTask(null);
      setSelection(null);
    }
  };

  const askAboutSelection = () => {
    if (!selection) return;
    setChatAnchor({
      selectedText: selection.text,
      paragraphId: selection.paragraphId,
    });
    setChatOpen(true);
    setSelection(null);
  };

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
            <span>
              {ocrInProgress
                ? `${paper.pages_processed}/${paper.page_count || "?"} 页`
                : `${paper.page_count} 页`}
            </span><span>{paper.paragraph_count} 段</span>
            <span>{translated}/{paper.paragraph_count} 已翻译</span><span>{analysisBlockCount} 个解读块</span>
          </div>
        </div>
        <div className="reader-actions">
          <a className="ghost-button" href={`/api/papers/${paper.id}/file`} target="_blank" rel="noreferrer">原始 PDF</a>
          <button className="ghost-button action-button" onClick={() => void generateTranslations()} disabled={busyTask !== null || pipelineActive}>
            {busyTask === "translation" ? "翻译中…" : translated ? "补全译文" : "生成翻译"}
          </button>
          <button className="ghost-button action-button" onClick={() => setVocabularyOpen(true)}>
            词汇 {vocabulary.length}
          </button>
          <button
            className="ghost-button action-button"
            onClick={() => {
              setChatAnchor({ selectedText: null, paragraphId: null });
              setChatOpen(true);
            }}
          >
            问 AI
          </button>
          <button className="primary-button" onClick={() => void generateDeepAnalysis()} disabled={busyTask !== null || pipelineActive}>
            {busyTask === "analysis" ? "解读中…" : "生成深度解读"}
          </button>
        </div>
      </header>
      {!llmConfigured && <div className="inline-warning reader-warning">请在 `.env` 填写 DASHSCOPE_API_KEY，翻译和深度解读结果会自动缓存。</div>}
      {pipelineActive && (
        <div className="reader-notice">
          {ocrInProgress
            ? `PaddleOCR 正在逐页识别：已完成 ${paper.pages_processed}/${paper.page_count || "?"} 页，当前 ${paper.paragraph_count} 段可阅读。`
            : `Qwen 正在后台生成：译文 ${translated}/${paper.paragraph_count}，深度解读 ${paper.analysis_groups_completed}/${paper.analysis_group_count || "?"}。`}
        </div>
      )}
      {notice && <div className="reader-notice">{notice}</div>}

      <div
        ref={readerRef}
        className="aligned-reader-grid"
        onContextMenu={openSelectionMenu}
        onScroll={trackReadingProgress}
      >
        <div className="column-label column-label--left">原文 + 中文翻译</div>
        <div className="column-divider" />
        <div className="column-label column-label--right">深度 AI 解读</div>
        {visibleGroups.map((group) => {
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
                  <BilingualParagraph
                    key={paragraph.id}
                    paperId={paper.id}
                    paragraph={paragraph}
                    vocabulary={vocabulary}
                  />
                ))}
              </section>
              <div className="column-divider" />
              <aside
                data-paragraph-id={group.paragraph_ids[0]}
                className={`semantic-analysis ${active ? "is-linked" : ""}`}
                onMouseEnter={() => setHoveredGroup(group.id)}
                onMouseLeave={() => setHoveredGroup(null)}
              >
                <span className="group-number">GROUP {group.group_index + 1}</span>
                {group.analysis_text ? (
                  <AnalysisMarkdown text={group.analysis_text} vocabulary={vocabulary} />
                ) : group.analysis_status === "skipped" ? (
                  <p className="analysis-skipped">结构信息，无需单独解读。</p>
                ) : (
                  <p className="analysis-empty">
                    {ocrInProgress
                      ? "本页原文已可阅读；全文 OCR 完成后会自动生成译文和深度解读。"
                      : "正在生成深度解读。一个解读可对应左侧多个自然段。"}
                  </p>
                )}
              </aside>
            </div>
          );
        })}
      </div>
      {selection && (
        <div
          className="selection-menu"
          style={{ left: selection.x, top: selection.y }}
          onClick={(event) => event.stopPropagation()}
        >
          <span>“{selection.text.slice(0, 40)}{selection.text.length > 40 ? "…" : ""}”</span>
          <button onClick={() => void saveSelection()}>翻译并收藏词汇</button>
          <button onClick={askAboutSelection}>问 AI</button>
        </div>
      )}
      <VocabularyDrawer
        items={vocabulary}
        open={vocabularyOpen}
        onClose={() => setVocabularyOpen(false)}
        onChange={setVocabulary}
      />
      <ChatPanel
        paperId={paper.id}
        anchor={chatAnchor}
        open={chatOpen}
        onClose={() => setChatOpen(false)}
      />
    </section>
  );
}

function BilingualParagraph({
  paperId,
  paragraph,
  vocabulary,
}: {
  paperId: string;
  paragraph: Paragraph;
  vocabulary: VocabularyItem[];
}) {
  return (
    <article
      className="bilingual-paragraph"
      data-paragraph-id={paragraph.id}
      id={`paragraph-${paragraph.id}`}
    >
      <div className="paragraph-location">
        <a href={`/api/papers/${paperId}/file#page=${paragraph.page_number}`} target="_blank" rel="noreferrer">
          PAGE {paragraph.page_number}
        </a>
        <span>¶ {paragraph.paragraph_index + 1}</span>
      </div>
      <div className="source-text">
        <AcademicMarkdown text={paragraph.source_text} vocabulary={vocabulary} />
      </div>
      <div className={`translated-text ${paragraph.translated_text ? "" : "is-empty"}`}>
        <AcademicMarkdown
          text={paragraph.translated_text ?? "等待生成中文翻译"}
          vocabulary={vocabulary}
        />
      </div>
    </article>
  );
}
