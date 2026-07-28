import { describe, expect, it } from "vitest";

import { extractEntryAsset } from "./updateWatcher";

describe("extractEntryAsset", () => {
  it("returns the absolute URL of the current Vite entry asset", () => {
    const html = `
      <!doctype html>
      <html>
        <head>
          <script type="module" src="/assets/index-new-build.js"></script>
        </head>
      </html>
    `;

    expect(extractEntryAsset(html, "https://reader.example.com/paper")).toBe(
      "https://reader.example.com/assets/index-new-build.js",
    );
  });

  it("returns null when the page has no module entry", () => {
    expect(
      extractEntryAsset("<html><body>offline</body></html>", "https://reader.example.com"),
    ).toBeNull();
  });
});
