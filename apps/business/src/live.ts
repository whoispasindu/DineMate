const LOOPBACK = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"]);

export function reachableStream(url: string): string {
  try {
    const parsed = new URL(url);
    if (LOOPBACK.has(parsed.hostname) && !LOOPBACK.has(window.location.hostname)) {
      parsed.hostname = window.location.hostname;
    }
    return parsed.toString();
  } catch {
    return url;
  }
}
