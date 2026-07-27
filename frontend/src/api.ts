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
  paragraph_count: number;
  vocabulary_count: number;
  read_progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string | null;
};

export type PaperDetail = PaperSummary & {
  paragraphs: Paragraph[];
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
  return request<PaperSummary>("/api/papers/import", { method: "POST", body });
}

export function deletePaper(id: string): Promise<void> {
  return request<void>(`/api/papers/${id}`, { method: "DELETE" });
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
