import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders the stage-zero workspace and Qwen status", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          service: "paper-reading-assistant-api",
          version: "0.1.0",
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
  expect(screen.getByText("阶段 0 · 工程基础")).toBeInTheDocument();
});
