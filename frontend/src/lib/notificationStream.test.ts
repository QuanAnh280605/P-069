import { afterEach, describe, expect, it, vi } from 'vitest';

import { createSseDataParser, NotificationStreamPayload, streamNotifications } from '@/lib/notificationStream';

describe('createSseDataParser', () => {
  it('emits the data payload of each complete block', () => {
    const received: string[] = [];
    const feed = createSseDataParser((data) => received.push(data));

    feed('data: {"a":1}\n\n');
    feed(': keepalive\n\n');
    feed('data: {"a":2}\n\n');

    expect(received).toEqual(['{"a":1}', '{"a":2}']);
  });

  it('reassembles blocks split across chunk boundaries', () => {
    const received: string[] = [];
    const feed = createSseDataParser((data) => received.push(data));

    feed('data: {"a"');
    feed(':1}\n');
    feed('\ndata: {"b":2}\n\n');

    expect(received).toEqual(['{"a":1}', '{"b":2}']);
  });

  it('joins multi-line data fields', () => {
    const received: string[] = [];
    const feed = createSseDataParser((data) => received.push(data));

    feed('data: line1\ndata: line2\n\n');

    expect(received).toEqual(['line1\nline2']);
  });
});

describe('streamNotifications', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('pushes parsed payloads to the callback until cancelled', async () => {
    const payload: NotificationStreamPayload = { items: [], unread_count: 2 };
    const encoder = new TextEncoder();
    const fetchMock = vi.fn(async () => {
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
          controller.close();
        },
      });
      return new Response(body, { headers: { 'Content-Type': 'text/event-stream' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    const updates: NotificationStreamPayload[] = [];
    const cancel = streamNotifications((update) => updates.push(update));

    await vi.waitFor(() => expect(updates.length).toBeGreaterThanOrEqual(1));
    expect(updates[0]).toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/notifications/stream',
      expect.objectContaining({ headers: expect.objectContaining({ Accept: 'text/event-stream' }) }),
    );

    cancel();
  });

  it('stops reconnecting after cancellation', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 500 }));
    vi.stubGlobal('fetch', fetchMock);

    const cancel = streamNotifications(() => undefined);
    cancel();

    await new Promise((resolve) => window.setTimeout(resolve, 50));
    expect(fetchMock.mock.calls.length).toBeLessThanOrEqual(1);
  });
});
