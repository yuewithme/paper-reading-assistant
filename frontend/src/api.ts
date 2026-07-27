export type HealthStatus = {
  service: string;
  version: string;
  environment: string;
  llm_provider: string;
  llm_configured: boolean;
};

export type Paragraph = {
  id: string;
  paragraph_index: number;
  source_text: string;
  translated_text: string | null;
  page_number: number;
  source_bbox_json: string;
};

export type PaperSummary = {
  id: string;
  title: string;
  file_name: string;
  status: string;
  page_count: number;
  pages_processed: number;
  paragraph_count: number;
  vocabulary_count: number;
  read_progress: number;
  last_read_position: string | null;
  error_message: string | null;
  translations_completed: number;
  analysis_group_count: number;
  analysis_groups_completed: number;
  ocr_duration_seconds: number | null;
  translation_duration_seconds: number | null;
  analysis_duration_seconds: number | null;
  total_duration_seconds: number | null;
  processing_started_at: string | null;
  ocr_completed_at: string | null;
  processing_completed_at: string | null;
  created_at: string;
  updated_at: string | null;
};

export type PaperDetail = PaperSummary & {
  paragraphs: Paragraph[];
};

export type SemanticGroup = {
  id: string;
  group_index: number;
  paragraph_ids: string[];
  analysis_text: string | null;
  analysis_status: string;
};

export type VocabularyItem = {
  id: string;
  paper_id: string;
  paragraph_id: string | null;
  normalized_text: string;
  display_text: string;
  contextual_translation: string;
  source_sentence: string;
  page_number: number | null;
  mastery_status: "new" | "learning" | "mastered";
  note: string;
  color: string;
  created_at: string;
};

export type Citation = {
  paragraph_id: string;
  page_number: number;
  quote: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  selected_text: string | null;
  source_paragraph_ids: string[];
  citations: Citation[];
  created_at: string;
};

export type Conversation = {
  id: string;
  paper_id: string;
  title: string;
  messages: ChatMessage[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail?.message ?? body?.detail ?? `请求失败：${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/api/health");
}

export function fetchPapers(): Promise<PaperSummary[]> {
  return request<PaperSummary[]>("/api/papers");
}

export function fetchPaper(id: string): Promise<PaperDetail> {
  return request<PaperDetail>(`/api/papers/${id}`);
}

export function importPaper(file: File): Promise<PaperSummary> {
  const body = new FormData();
  body.append("file", file);
  return request<PaperSummary>("/api/papers/import?background=true", { method: "POST", body });
}

export function deletePaper(id: string): Promise<void> {
  return request<void>(`/api/papers/${id}`, { method: "DELETE" });
}

export async function waitForPaper(id: string, attempts = 1800): Promise<PaperDetail> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const paper = await fetchPaper(id);
    if (
      paper.paragraph_count > 0
      || !["queued", "processing", "ocr_complete", "enriching"].includes(paper.status)
    ) {
      return paper;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }
  throw new Error("解析仍在后台进行，请稍后重新打开论文");
}

export function enrichPaper(id: string): Promise<PaperSummary> {
  return request<PaperSummary>(`/api/papers/${id}/enrich?background=true`, {
    method: "POST",
  });
}

export function reparsePaper(id: string, forceOcr = false): Promise<PaperSummary> {
  return request<PaperSummary>(
    `/api/papers/${id}/reparse?background=true&force_ocr=${forceOcr}`,
    { method: "POST" },
  );
}

export function saveReadingProgress(
  id: string,
  readProgress: number,
  lastReadPosition: string | null,
): Promise<PaperSummary> {
  return request<PaperSummary>(`/api/papers/${id}/progress`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      read_progress: readProgress,
      last_read_position: lastReadPosition,
    }),
  });
}

export function translatePaper(
  id: string,
  paragraphIds?: string[],
  force = false,
): Promise<{ translated_count: number; cached_count: number; paragraphs: Paragraph[] }> {
  return request(`/api/papers/${id}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paragraph_ids: paragraphIds ?? null, force }),
  });
}

export function fetchSemanticGroups(id: string): Promise<SemanticGroup[]> {
  return request<SemanticGroup[]>(`/api/papers/${id}/groups`);
}

export function generateAnalysis(
  id: string,
  groupIds?: string[],
  force = false,
): Promise<{ generated_count: number; cached_count: number; groups: SemanticGroup[] }> {
  return request(`/api/papers/${id}/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ group_ids: groupIds ?? null, force }),
  });
}

export function fetchVocabulary(id: string): Promise<VocabularyItem[]> {
  return request<VocabularyItem[]>(`/api/papers/${id}/vocabulary`);
}

export function createVocabulary(
  paperId: string,
  selectedText: string,
  paragraphId: string | null,
): Promise<VocabularyItem> {
  return request<VocabularyItem>(`/api/papers/${paperId}/vocabulary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_text: selectedText, paragraph_id: paragraphId }),
  });
}

export function updateVocabulary(
  itemId: string,
  updates: Partial<Pick<VocabularyItem, "contextual_translation" | "mastery_status" | "note" | "color">>,
): Promise<VocabularyItem> {
  return request<VocabularyItem>(`/api/vocabulary/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export function deleteVocabulary(itemId: string): Promise<void> {
  return request<void>(`/api/vocabulary/${itemId}`, { method: "DELETE" });
}

export function fetchConversation(paperId: string): Promise<Conversation> {
  return request<Conversation>(`/api/papers/${paperId}/conversation`);
}

export function sendChatMessage(
  paperId: string,
  question: string,
  selectedText: string | null,
  paragraphId: string | null,
): Promise<{ conversation: Conversation; answer: ChatMessage }> {
  return request(`/api/papers/${paperId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      selected_text: selectedText,
      paragraph_id: paragraphId,
    }),
  });
}
