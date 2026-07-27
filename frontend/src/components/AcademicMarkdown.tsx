import { Children, type ReactNode } from "react";
import katex from "katex";
import rehypeKatex from "rehype-katex";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";

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

function normalizeMathDelimiters(text: string): string {
  const normalized = text
    .replace(/\\\[([\s\S]*?)\\\]/g, (_match, formula: string) => `$$${formula}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_match, formula: string) => `$${formula}$`);
  const withDisplayMath = normalized.replace(
    /\$\$([\s\S]*?)\$\$/g,
    (_match, formula: string) => {
      const repaired = repairLatex(formula.trim());
      return repaired === null
        ? `\n\n\`${formula.trim()}\`\n\n`
        : `\n\n$$\n${repaired}\n$$\n\n`;
    },
  );
  return withDisplayMath.replace(
    /(?<!\$)\$(?!\$)([^\n$]+)(?<!\$)\$(?!\$)/g,
    (_match, formula: string) => {
      const repaired = repairLatex(formula.trim());
      return repaired === null ? `\`${formula.trim()}\`` : `$${repaired}$`;
    },
  );
}

function repairLatex(formula: string): string | null {
  if (canRenderLatex(formula)) {
    return formula;
  }

  const normalizedClosures = formula.replace(/\\}/g, "}");
  if (canRenderLatex(normalizedClosures)) {
    return normalizedClosures;
  }

  const balanced = balanceLatexBraces(normalizedClosures);
  if (canRenderLatex(balanced)) {
    return balanced;
  }

  const withoutMalformedStackrel = balanced.replace(/\\stackrel[\s\S]*$/, "");
  return withoutMalformedStackrel !== balanced &&
    canRenderLatex(withoutMalformedStackrel)
    ? withoutMalformedStackrel
    : null;
}

function canRenderLatex(formula: string): boolean {
  try {
    katex.renderToString(formula, {
      strict: false,
      throwOnError: true,
    });
    return true;
  } catch {
    return false;
  }
}

function balanceLatexBraces(formula: string): string {
  let depth = 0;
  let repaired = "";

  for (let index = 0; index < formula.length; index += 1) {
    const character = formula[index];
    const escaped = index > 0 && formula[index - 1] === "\\";

    if (character === "{" && !escaped) {
      depth += 1;
    } else if (character === "}" && !escaped) {
      if (depth === 0) {
        continue;
      }
      depth -= 1;
    }
    repaired += character;
  }

  return repaired + "}".repeat(depth);
}

export function AcademicMarkdown({
  text,
  vocabulary,
  variant = "paragraph",
}: {
  text: string;
  vocabulary: VocabularyItem[];
  variant?: "analysis" | "paragraph";
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
    <div className={`academic-markdown academic-markdown--${variant}`}>
      <Markdown
        components={components}
        rehypePlugins={[[rehypeKatex, { strict: false, throwOnError: false }]]}
        remarkPlugins={[remarkGfm, remarkMath]}
      >
        {normalizeMathDelimiters(text)}
      </Markdown>
    </div>
  );
}
