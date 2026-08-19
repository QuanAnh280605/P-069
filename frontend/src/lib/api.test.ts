import { afterEach, describe, expect, it, vi } from 'vitest';

import { createMetricApi, executeSemanticQueryApi, MetricDefinition } from '@/lib/api';

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
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ metric_id: 7, definition, source: 'ai' }), { status: 201, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const record = await createMetricApi('5', { definition, source: 'ai' });
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const payload = JSON.parse(String(request.body));
    expect(record.metric_id).toBe(7);
    expect(payload.definition).toEqual(definition);
    expect(payload).not.toHaveProperty('sql_template');
  });

  it('executes only semantic selections and returns compiled results', async () => {
    const response = { sql: 'SELECT COUNT(*) FROM orders LIMIT 100', parameters: {}, columns: ['count'], rows: [[2]], row_count: 1 };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    await executeSemanticQueryApi('5', { metric_ids: [7], dimensions: [{ column_id: 11 }], filters: [], limit: 100 });
    const payload = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(payload).toEqual({ metric_ids: [7], dimensions: [{ column_id: 11 }], filters: [], limit: 100 });
    expect(payload).not.toHaveProperty('sql');
  });
});
