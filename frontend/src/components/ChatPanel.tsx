import { useEffect, useRef, useState } from "react";

import {
  fetchConversation,
  sendChatMessage,
  type Conversation,
} from "../api";

export type ChatAnchor = {
  selectedText: string | null;
  paragraphId: string | null;
};

export function ChatPanel({
  paperId,
  anchor,
  open,
  onClose,
}: {
  paperId: string;
  anchor: ChatAnchor;
  open: boolean;
  onClose: () => void;
}) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    fetchConversation(paperId)
      .then(setConversation)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "读取问答记录失败"));
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open, paperId]);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ block: "end" });
  }, [conversation?.messages.length]);

  if (!open) return null;

  const submit = async () => {
    const value = question.trim();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await sendChatMessage(
        paperId,
        value,
        anchor.selectedText,
        anchor.paragraphId,
      );
      setConversation(result.conversation);
      setQuestion("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "提问失败");
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  };

  return (
    <aside className="chat-panel" aria-label="AI 问答">
      <header>
        <div><p className="eyebrow">PAPER Q&A</p><h2>问 AI</h2></div>
        <button className="icon-button" aria-label="关闭 AI 问答" onClick={onClose}>×</button>
      </header>
      {anchor.selectedText && (
        <blockquote className="chat-anchor">
          “{anchor.selectedText.slice(0, 180)}{anchor.selectedText.length > 180 ? "…" : ""}”
        </blockquote>
      )}
      <div className="chat-messages">
        {conversation?.messages.map((message) => (
          <article className={`chat-message chat-message--${message.role}`} key={message.id}>
            <span>{message.role === "user" ? "你" : "AI"}</span>
            <p>{message.content}</p>
            {message.citations.length > 0 && (
              <div className="chat-citations">
                {message.citations.map((citation) => (
                  <button
                    key={`${message.id}-${citation.paragraph_id}`}
                    onClick={() => {
                      document.getElementById(`paragraph-${citation.paragraph_id}`)?.scrollIntoView({
                        behavior: "smooth",
                        block: "center",
                      });
                    }}
                  >
                    第 {citation.page_number} 页 · {citation.quote.slice(0, 48)}…
                  </button>
                ))}
              </div>
            )}
          </article>
        ))}
        {!conversation?.messages.length && (
          <div className="chat-empty">直接提问即可。上下文会由系统自动选择，无需手动配置范围。</div>
        )}
        <div ref={messagesEnd} />
      </div>
      <div className="chat-composer">
        {error && <p className="chat-error">{error}</p>}
        <textarea
          ref={inputRef}
          value={question}
          placeholder="这个方法为什么这样设计？"
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit();
            }
          }}
        />
        <button className="primary-button" disabled={busy || !question.trim()} onClick={() => void submit()}>
          {busy ? "思考中…" : "发送"}
        </button>
      </div>
    </aside>
  );
}
