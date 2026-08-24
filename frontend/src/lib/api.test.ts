import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  createMetricApi,
  executeSemanticQueryApi,
  MetricDefinition,
  rollbackMetricApi,
  SemanticApiError,
} from '@/lib/api';

const definition: MetricDefinition = {
  metric: {
    name: 'Doanh thu',
    formula: { function: 'SUM', expression: 'quantity * unit_price' },
    base_entity: 'OrderItem',
    filters: [],
    status: 'pending_approval',
    confidence: 'high',
    excluded_notes: '',
  },
};

describe('semantic adapter', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('persists canonical JSON and never sends SQL template', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ metric_id: 7, definition, source: 'ai' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    vi.stubGlobal('fetch', fetchMock);
    const record = await createMetricApi('5', { definition, source: 'ai' });
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const payload = JSON.parse(String(request.body));
    expect(record.metric_id).toBe(7);
    expect(payload.definition).toEqual(definition);
    expect(payload).not.toHaveProperty('sql_template');
  });

  it('preserves the backend-controlled status for Member submissions', async () => {
    const response = {
      metric_id: 7,
      definition,
      source: 'manual',
      status: 'unverified',
    };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(response), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    const record = await createMetricApi('5', { definition, source: 'manual' });

    expect(record.status).toBe('unverified');
  });

  it('keeps the backend permission error visible', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: 'Member chỉ được gửi metric mới.' }), {
            status: 403,
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
    );

    await expect(createMetricApi('5', { definition, source: 'manual' })).rejects.toEqual(
      new SemanticApiError(403, 'Member chỉ được gửi metric mới.', 'Member chỉ được gửi metric mới.'),
    );
  });

  it('executes only semantic selections and returns compiled results', async () => {
    const response = {
      sql: 'SELECT COUNT(*) FROM orders LIMIT 100',
      parameters: {},
      columns: ['count'],
      rows: [[2]],
      row_count: 1,
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await executeSemanticQueryApi('5', {
      metric_ids: [7],
      dimensions: [{ column_id: 11 }],
      filters: [],
      limit: 100,
    });
    const payload = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(payload).toEqual({
      metric_ids: [7],
      dimensions: [{ column_id: 11 }],
      filters: [],
      limit: 100,
    });
    expect(payload).not.toHaveProperty('sql');
  });

  it('rolls back by posting to the exact versioned path and maps the mutation response', async () => {
    const response = {
      metric_id: 7,
      definition,
      source: 'manual',
      status: 'approved',
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const record = await rollbackMetricApi('5', 7, 2);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/semantic\/5\/metric\/7\/rollback\/2$/);
    expect((init as RequestInit).method).toBe('POST');
    expect(record.metric_id).toBe(7);
    expect(record.status).toBe('approved');
    expect(record.definition).toEqual(definition);
  });

  it('propagates backend rollback failures as SemanticApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Chỉ được phép khôi phục về phiên bản cũ hơn.' }), {
          status: 422,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    await expect(rollbackMetricApi('5', 7, 3)).rejects.toEqual(
      new SemanticApiError(
        422,
        'Chỉ được phép khôi phục về phiên bản cũ hơn.',
        'Chỉ được phép khôi phục về phiên bản cũ hơn.',
      ),
    );
  });
});
