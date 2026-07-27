import { Children, type ReactNode } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { VocabularyItem } from "../api";
import { HighlightedText } from "./HighlightedText";

function highlightedChildren(
  children: ReactNode,
  vocabulary: VocabularyItem[],
): ReactNode {
  return Children.map(children, (child) =>
    typeof child === "string" ? (
      <HighlightedText text={child} vocabulary={vocabulary} />
    ) : (
      child
    ),
  );
}

export function AnalysisMarkdown({
  text,
  vocabulary,
}: {
  text: string;
  vocabulary: VocabularyItem[];
}) {
  const components: Components = {
    h1: ({ children }) => <h3>{highlightedChildren(children, vocabulary)}</h3>,
    h2: ({ children }) => <h3>{highlightedChildren(children, vocabulary)}</h3>,
    h3: ({ children }) => <h4>{highlightedChildren(children, vocabulary)}</h4>,
    p: ({ children }) => <p>{highlightedChildren(children, vocabulary)}</p>,
    li: ({ children }) => <li>{highlightedChildren(children, vocabulary)}</li>,
    strong: ({ children }) => (
      <strong>{highlightedChildren(children, vocabulary)}</strong>
    ),
    em: ({ children }) => <em>{highlightedChildren(children, vocabulary)}</em>,
    blockquote: ({ children }) => <blockquote>{children}</blockquote>,
    th: ({ children }) => <th>{highlightedChildren(children, vocabulary)}</th>,
    td: ({ children }) => <td>{highlightedChildren(children, vocabulary)}</td>,
    a: ({ children, href }) => (
      <a href={href} rel="noreferrer noopener" target="_blank">
        {highlightedChildren(children, vocabulary)}
      </a>
    ),
    code: ({ children, className }) => (
      <code className={className}>{children}</code>
    ),
  };

  return (
    <div className="analysis-markdown">
      <Markdown components={components} remarkPlugins={[remarkGfm]}>
        {text}
      </Markdown>
    </div>
  );
}
