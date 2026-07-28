import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import type { PaperDetail, SemanticGroup } from "../api";
import { PaperReader } from "./PaperReader";

const apiMocks = vi.hoisted(() => ({
  fetchSemanticGroups: vi.fn(),
  fetchVocabulary: vi.fn(),
}));

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    fetchSemanticGroups: apiMocks.fetchSemanticGroups,
    fetchVocabulary: apiMocks.fetchVocabulary,
  };
});

const paper: PaperDetail = {
  id: "paper-1",
  title: "Test Paper",
  file_name: "test.pdf",
  status: "ready",
  page_count: 1,
  pages_processed: 1,
  paragraph_count: 3,
  vocabulary_count: 0,
  read_progress: 0,
  last_read_position: null,
  error_message: null,
  translations_completed: 3,
  analysis_group_count: 3,
  analysis_groups_completed: 3,
  ocr_duration_seconds: null,
  translation_duration_seconds: null,
  analysis_duration_seconds: null,
  total_duration_seconds: null,
  processing_started_at: null,
  ocr_completed_at: null,
  processing_completed_at: null,
  created_at: "2026-07-28T00:00:00Z",
  updated_at: null,
  paragraphs: [
    {
      id: "paragraph-1",
      paragraph_index: 0,
      source_text: "Leading skipped source paragraph.",
      translated_text: "前置但无需单独解读的原文。",
      page_number: 1,
      source_bbox_json: "{}",
    },
    {
      id: "paragraph-2",
      paragraph_index: 1,
      source_text: "Analyzed source paragraph.",
      translated_text: "有解读的原文。",
      page_number: 1,
      source_bbox_json: "{}",
    },
    {
      id: "paragraph-3",
      paragraph_index: 2,
      source_text: "Trailing skipped source paragraph.",
      translated_text: "后置但无需单独解读的原文。",
      page_number: 1,
      source_bbox_json: "{}",
    },
  ],
};

const groups: SemanticGroup[] = [
  {
    id: "group-1",
    group_index: 0,
    paragraph_ids: ["paragraph-1"],
    analysis_text: null,
    analysis_status: "skipped",
  },
  {
    id: "group-2",
    group_index: 1,
    paragraph_ids: ["paragraph-2"],
    analysis_text: "### 完整解读\n\n这是应当完整展示的内容。",
    analysis_status: "ready",
  },
  {
    id: "group-3",
    group_index: 2,
    paragraph_ids: ["paragraph-3"],
    analysis_text: null,
    analysis_status: "skipped",
  },
];

beforeEach(() => {
  apiMocks.fetchSemanticGroups.mockResolvedValue(groups);
  apiMocks.fetchVocabulary.mockResolvedValue([]);
});

test("merges skipped source paragraphs into the preceding analysis row", async () => {
  const { container } = render(
    <PaperReader
      paper={paper}
      llmConfigured
      onPaperChange={vi.fn()}
    />,
  );

  expect(await screen.findByText("这是应当完整展示的内容。")).toBeInTheDocument();
  expect(screen.getByText("Leading skipped source paragraph.")).toBeInTheDocument();
  expect(screen.getByText("Trailing skipped source paragraph.")).toBeInTheDocument();
  expect(screen.queryByText("GROUP 2")).not.toBeInTheDocument();
  expect(screen.queryByText("结构信息，无需单独解读。")).not.toBeInTheDocument();
  expect(
    container.querySelectorAll(
      '[data-group-number="1"] .semantic-source .bilingual-paragraph',
    ),
  ).toHaveLength(3);
  expect(container.querySelector(".semantic-analysis--source-only")).not.toBeInTheDocument();
});
