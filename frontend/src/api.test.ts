import { afterEach, expect, test, vi } from "vitest";

import { waitForPaper, type PaperDetail } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

test("waitForPaper opens as soon as the first OCR paragraphs are readable", async () => {
  const partialPaper: PaperDetail = {
    id: "paper-1",
    title: "Progressive Paper",
    file_name: "paper.pdf",
    status: "processing",
    page_count: 15,
    pages_processed: 1,
    paragraph_count: 2,
    vocabulary_count: 0,
    read_progress: 0,
    last_read_position: null,
    error_message: null,
    translations_completed: 0,
    analysis_group_count: 0,
    analysis_groups_completed: 0,
    ocr_duration_seconds: null,
    translation_duration_seconds: null,
    analysis_duration_seconds: null,
    total_duration_seconds: null,
    processing_started_at: "2026-07-27T00:00:00Z",
    ocr_completed_at: null,
    processing_completed_at: null,
    created_at: "2026-07-27T00:00:00Z",
    updated_at: null,
    paragraphs: [
      {
        id: "paragraph-1",
        paragraph_index: 0,
        source_text: "Readable before the remaining pages finish.",
        translated_text: null,
        page_number: 1,
        source_bbox_json: "{}",
      },
    ],
  };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(partialPaper), { status: 200 }),
  );

  const result = await waitForPaper(partialPaper.id, 1);

  expect(result.status).toBe("processing");
  expect(result.pages_processed).toBe(1);
  expect(result.paragraphs).toHaveLength(1);
  expect(globalThis.fetch).toHaveBeenCalledTimes(1);
});
