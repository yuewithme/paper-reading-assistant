const UPDATE_CHECK_INTERVAL_MS = 60_000;

export function extractEntryAsset(html: string, baseUrl: string): string | null {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const entry = parsed.querySelector<HTMLScriptElement>('script[type="module"][src]');
  const source = entry?.getAttribute("src");
  return source ? new URL(source, baseUrl).href : null;
}

export function startAppUpdateWatcher(): () => void {
  const currentEntry = document.querySelector<HTMLScriptElement>(
    'script[type="module"][src]',
  )?.src;

  if (!currentEntry) {
    return () => undefined;
  }

  let checking = false;
  let stopped = false;

  const checkForUpdate = async () => {
    if (checking || stopped) {
      return;
    }

    checking = true;
    try {
      const response = await fetch(`/index.html?update=${Date.now()}`, {
        cache: "no-store",
      });
      if (!response.ok) {
        return;
      }

      const nextEntry = extractEntryAsset(
        await response.text(),
        window.location.origin,
      );
      if (nextEntry && nextEntry !== currentEntry) {
        window.location.reload();
      }
    } catch {
      // A temporary network failure should not interrupt reading.
    } finally {
      checking = false;
    }
  };

  const intervalId = window.setInterval(
    checkForUpdate,
    UPDATE_CHECK_INTERVAL_MS,
  );
  const handleVisibilityChange = () => {
    if (document.visibilityState === "visible") {
      void checkForUpdate();
    }
  };
  document.addEventListener("visibilitychange", handleVisibilityChange);

  return () => {
    stopped = true;
    window.clearInterval(intervalId);
    document.removeEventListener("visibilitychange", handleVisibilityChange);
  };
}
