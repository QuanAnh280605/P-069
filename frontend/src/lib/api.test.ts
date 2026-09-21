import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  approveSchemaReviewApi,
  createMetricApi,
  executeSemanticQueryApi,
  getMetricJoinPathOptionsApi,
  MetricDefinition,
  rollbackMetricApi,
  SemanticApiError,
  sendChatOrchestratorApi,
  updateRelationshipReviewApi,
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

  it('sends the persisted preferred_join_paths in the create payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ metric_id: 7, definition, source: 'manual' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const definitionWithPaths: MetricDefinition = {
      metric: {
        ...definition.metric,
        preferred_join_paths: { '20': [5, 6] },
      },
    };
    await createMetricApi('5', { definition: definitionWithPaths, source: 'manual' });

    const payload = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(payload.definition.metric.preferred_join_paths).toEqual({ '20': [5, 6] });
  });

  it('fetches governed join-path options and parses the target-keyed map', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            '20': [
              {
                relationship_ids: [5],
                entity_ids: [10, 20],
                labels: ['Đơn thuộc khách'],
                descriptions: ['note'],
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      );
    vi.stubGlobal('fetch', fetchMock);

    const options = await getMetricJoinPathOptionsApi('5', 10);
    const [url] = fetchMock.mock.calls[0] as [string, ...unknown[]];
    expect(String(url)).toMatch(/\/api\/v1\/semantic\/5\/metric\/join-path-options\?base_entity_id=10$/);
    expect(options['20'][0].relationship_ids).toEqual([5]);
    expect(options['20'][0].labels).toEqual(['Đơn thuộc khách']);
  });

  it('surfaces Admin-forbidden join-path access as SemanticApiError (role matrix)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Admin không được tạo metric.' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    await expect(getMetricJoinPathOptionsApi('5', 10)).rejects.toMatchObject({ status: 403 });
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

  it('delegates AI chat requests to fetch without an artificial abort deadline', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ session_id: 'session-123', chat_response: 'ok' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const response = await sendChatOrchestratorApi('5', 'Tạo metric doanh thu');
    expect(fetchMock).toHaveBeenCalled();
    expect(response.session_id).toBe('session-123');
  });
});
describe('relationship review adapter', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('puts relationship governance edits to the relationship path', async () => {
    const rel = {
      relationship_id: 9,
      from_entity_id: 1,
      to_entity_id: 2,
      from_table_name: 'orders',
      to_table_name: 'customers',
      column_pairs: [],
      business_name: 'Đơn thuộc khách',
      description: 'note',
      ai_business_name: null,
      ai_description: null,
      validation_status: 'valid',
      review_status: 'pending_review',
      ambiguous_target_groups: [],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(rel), { status: 200, headers: { 'Content-Type': 'application/json' } }),
      );
    vi.stubGlobal('fetch', fetchMock);

    const result = await updateRelationshipReviewApi('5', 9, 'Đơn thuộc khách', 'note');

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/semantic\/5\/relationship\/9$/);
    expect((init as RequestInit).method).toBe('PUT');
    const payload = JSON.parse(String((init as RequestInit).body));
    expect(payload).toEqual({ business_name: 'Đơn thuộc khách', description: 'note' });
    expect(result.relationship_id).toBe(9);
  });

  it('approves relationships when relationship_ids are supplied', async () => {
    const response = {
      db_id: 5,
      approved_tables: 0,
      approved_columns: 0,
      approved_relationships: 2,
      pending_tables: 0,
      pending_columns: 0,
      pending_relationships: 0,
      status: 'approved',
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(response), { status: 200, headers: { 'Content-Type': 'application/json' } }),
      );
    vi.stubGlobal('fetch', fetchMock);

    const result = await approveSchemaReviewApi('5', undefined, [9, 10]);

    const payload = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(payload).toEqual({ table_names: null, relationship_ids: [9, 10] });
    expect(result.approved_relationships).toBe(2);
    expect(result.pending_relationships).toBe(0);
  });

  it('surfaces invalid relationship approval as SemanticApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              error: 'invalid_relationship',
              relationship_id: 9,
              message: 'Relationship 9 is technically invalid',
            },
          }),
          { status: 422, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    await expect(approveSchemaReviewApi('5', undefined, [9])).rejects.toMatchObject({
      status: 422,
    });
  });
});
