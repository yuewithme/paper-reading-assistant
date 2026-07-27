import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { VocabularyItem } from "../api";
import { AnalysisMarkdown } from "./AnalysisMarkdown";

const vocabulary: VocabularyItem[] = [
  {
    id: "vocabulary-1",
    paper_id: "paper-1",
    paragraph_id: null,
    normalized_text: "attention",
    display_text: "attention",
    contextual_translation: "注意力",
    source_sentence: "Attention connects tokens.",
    page_number: 1,
    mastery_status: "new",
    note: "",
    color: "#f2d675",
    created_at: "2026-07-27T00:00:00Z",
  },
];

test("renders analysis markdown instead of showing raw markers", () => {
  render(
    <AnalysisMarkdown
      text={
        "### 核心方法\n\n- 使用 **attention**\n- 保持上下文\n\n" +
        "| 指标 | 结果 |\n| --- | --- |\n| BLEU | 28.4 |"
      }
      vocabulary={vocabulary}
    />,
  );

  expect(screen.getByRole("heading", { name: "核心方法" })).toBeInTheDocument();
  expect(screen.getByRole("list")).toBeInTheDocument();
  expect(screen.getByRole("table")).toBeInTheDocument();
  expect(screen.queryByText("### 核心方法")).not.toBeInTheDocument();
  expect(screen.getByText("attention").tagName).toBe("MARK");
});

test("does not execute raw html returned by the model", () => {
  const { container } = render(
    <AnalysisMarkdown
      text={'<script data-testid="unsafe">alert("x")</script>\n\n安全内容'}
      vocabulary={[]}
    />,
  );

  expect(container.querySelector("script")).not.toBeInTheDocument();
  expect(screen.getByText("安全内容")).toBeInTheDocument();
});

test("compiles inline and display LaTeX with common delimiters", () => {
  const { container } = render(
    <AnalysisMarkdown
      text={
        "状态为 $h_{t-1}$，并计算 \\(QK^T\\)。\n\n" +
        "\\[\\operatorname{Attention}(Q,K,V)=\\operatorname{softmax}(QK^T/\\sqrt{d_k})V\\]"
      }
      vocabulary={[]}
    />,
  );

  expect(container.querySelectorAll(".katex").length).toBeGreaterThanOrEqual(3);
  expect(container.querySelector(".katex-display")).toBeInTheDocument();
  expect(container.textContent).not.toContain("$h_{t-1}$");
  expect(
    container.querySelector(".katex-display .katex-html")?.textContent,
  ).toContain("Attention");
});
