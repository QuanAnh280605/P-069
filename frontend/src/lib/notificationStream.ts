import { API_BASE, AppNotification, getAuthHeader, refreshAccessToken } from '@/lib/api';

export interface NotificationStreamPayload {
  items: AppNotification[];
  unread_count: number;
}

const RETRY_BASE_MS = 1000;
const RETRY_MAX_MS = 5000;
const RETRY_AUTH_FAILURE_MS = 10000;

export function createSseDataParser(onData: (data: string) => void): (chunk: string) => void {
  let buffer = '';
  return (chunk: string) => {
    buffer += chunk;
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      emitBlock(block, onData);
      boundary = buffer.indexOf('\n\n');
    }
  };
}

function emitBlock(block: string, onData: (data: string) => void): void {
  const dataLines = block
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).replace(/^ /, ''));
  if (dataLines.length) onData(dataLines.join('\n'));
}

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });

async function consumeStream(
  res: Response,
  onData: (data: string) => void,
  signal: AbortSignal,
): Promise<void> {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  const feed = createSseDataParser(onData);
  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done) return;
      feed(decoder.decode(value, { stream: true }));
    }
  } finally {
    void reader.cancel();
  }
}

export function streamNotifications(
  onUpdate: (payload: NotificationStreamPayload) => void,
): () => void {
  const controller = new AbortController();
  const run = async () => {
    let retryMs = RETRY_BASE_MS;
    while (!controller.signal.aborted) {
      try {
        const auth = getAuthHeader();
        const res = await fetch(`${API_BASE}/api/v1/notifications/stream`, {
          headers: { Accept: 'text/event-stream', ...auth },
          signal: controller.signal,
        });

        if (res.status === 401) {
          const newToken = await refreshAccessToken();
          if (!newToken) {
            await sleep(RETRY_AUTH_FAILURE_MS, controller.signal);
            continue;
          }
          continue;
        }

        if (res.status === 403) {
          await sleep(RETRY_AUTH_FAILURE_MS, controller.signal);
          continue;
        }

        if (!res.ok || !res.body) throw new Error(`Notification stream failed: ${res.status}`);
        retryMs = RETRY_BASE_MS;
        await consumeStream(res, parseInto(onUpdate), controller.signal);
      } catch {
        // aborted or the connection dropped — retry with backoff below
      }
      if (controller.signal.aborted) return;
      await sleep(retryMs, controller.signal);
      retryMs = Math.min(retryMs * 2, RETRY_MAX_MS);
    }
  };
  void run();
  return () => controller.abort();
}

function parseInto(onUpdate: (payload: NotificationStreamPayload) => void): (data: string) => void {
  return (data) => {
    try {
      onUpdate(JSON.parse(data) as NotificationStreamPayload);
    } catch {
      // ignore malformed events and wait for the next snapshot
    }
  };
}
