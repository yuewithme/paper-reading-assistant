import type { ReactNode } from "react";

import type { VocabularyItem } from "../api";

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalize(value: string) {
  let compact = value.trim().toLocaleLowerCase();
  if (compact.includes(" ") || compact.length <= 3) return compact;
  if (compact.endsWith("ies") && compact.length > 4) return `${compact.slice(0, -3)}y`;
  if (compact.endsWith("ing") && compact.length > 5) {
    compact = compact.slice(0, -3);
    if (compact.at(-1) === compact.at(-2)) compact = compact.slice(0, -1);
    return compact;
  }
  if (compact.endsWith("ed") && compact.length > 4) return compact.slice(0, -2);
  if (compact.endsWith("es") && compact.length > 4) return compact.slice(0, -2);
  if (compact.endsWith("s") && !compact.endsWith("ss") && compact.length > 3) return compact.slice(0, -1);
  return compact;
}

export function HighlightedText({
  text,
  vocabulary,
}: {
  text: string;
  vocabulary: VocabularyItem[];
}): ReactNode {
  if (!vocabulary.length) return text;
  const alternatives = vocabulary
    .flatMap((item) => {
      if (item.normalized_text.includes(" ")) return [escapeRegExp(item.display_text)];
      const base = escapeRegExp(item.normalized_text);
      return [escapeRegExp(item.display_text), `${base}(?:s|es|ed|ing)?`];
    })
    .sort((a, b) => b.length - a.length);
  const pattern = new RegExp(`\\b(${alternatives.join("|")})\\b`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, index) => {
    const item = vocabulary.find(
      (candidate) =>
        candidate.display_text.toLocaleLowerCase() === part.toLocaleLowerCase() ||
        candidate.normalized_text === normalize(part),
    );
    return item ? (
      <mark
        className="vocabulary-highlight"
        key={`${part}-${index}`}
        style={{ backgroundColor: item.color }}
        title={`${item.display_text}：${item.contextual_translation}`}
      >
        {part}
      </mark>
    ) : (
      part
    );
  });
}
