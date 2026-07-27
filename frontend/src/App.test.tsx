import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders the paper library and import control", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          service: "paper-reading-assistant-api",
          version: "0.2.0",
          environment: "test",
          llm_provider: "qwen",
          llm_configured: false,
        }),
        { status: 200 },
      ),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));

  render(<App />);

  expect(screen.getByRole("heading", { name: "论文辅助研读助手" })).toBeInTheDocument();
  expect(await screen.findByText("等待 API Key")).toBeInTheDocument();
  expect(screen.getByText("阶段 1 · PDF 导入与结构化")).toBeInTheDocument();
  expect(screen.getByText("导入 PDF")).toBeInTheDocument();
});
