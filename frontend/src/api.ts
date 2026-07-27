export type HealthStatus = {
  service: string;
  version: string;
  environment: string;
  llm_provider: string;
  llm_configured: boolean;
};

export type PaperSummary = {
  id: string;
  title: string;
  file_name: string;
  status: string;
  created_at: string;
};

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/api/health");
}

export function fetchPapers(): Promise<PaperSummary[]> {
  return request<PaperSummary[]>("/api/papers");
}

