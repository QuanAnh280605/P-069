import { describe, expect, it } from 'vitest';

import { MetricDefinition } from '@/lib/api';
import {
  buildMetricVersionDiff,
  buildMetricVersionLines,
  diffMetricVersionLines,
} from '@/lib/metric-version-diff';

function makeDefinition(
  expression: string,
  filters: Array<{ field: string; operator: 'eq' | 'in'; value: unknown }> = [],
): MetricDefinition {
  return {
    metric: {
      name: 'Doanh thu',
      formula: { function: 'SUM', expression },
      base_entity: 'OrderItem',
      filters,
      status: 'approved',
      excluded_notes: '',
    },
  };
}

describe('buildMetricVersionLines', () => {
  it('renders the formula first and filters after in sorted stable order', () => {
    const lines = buildMetricVersionLines(
      makeDefinition('quantity * unit_price', [
        { field: 'order_status', operator: 'eq', value: 'COMPLETED' },
        { field: 'store_id', operator: 'in', value: [1, 2] },
      ]),
    );

    expect(lines).toEqual(['SUM(quantity * unit_price)', 'order_status eq "COMPLETED"', 'store_id in [1,2]']);
  });

  it('returns null for a legacy version without a definition', () => {
    expect(buildMetricVersionLines(null)).toBeNull();
    expect(buildMetricVersionLines(undefined)).toBeNull();
  });
});

describe('diffMetricVersionLines', () => {
  it('marks every row unchanged for identical line sets', () => {
    const rows = diffMetricVersionLines(['SUM(a)', 'status eq "DONE"'], ['SUM(a)', 'status eq "DONE"']);

    expect(rows).toEqual([
      { status: 'unchanged', text: 'SUM(a)' },
      { status: 'unchanged', text: 'status eq "DONE"' },
    ]);
  });

  it('emits removed then added rows when the formula is replaced', () => {
    const rows = diffMetricVersionLines(['SUM(a)'], ['SUM(a - b)']);

    expect(rows).toEqual([
      { status: 'removed', text: 'SUM(a)' },
      { status: 'added', text: 'SUM(a - b)' },
    ]);
  });

  it('emits added rows for new lines appended at the end', () => {
    const rows = diffMetricVersionLines(['SUM(a)'], ['SUM(a)', 'region eq "north"']);

    expect(rows).toEqual([
      { status: 'unchanged', text: 'SUM(a)' },
      { status: 'added', text: 'region eq "north"' },
    ]);
  });

  it('emits removed rows for deleted lines', () => {
    const rows = diffMetricVersionLines(['SUM(a)', 'region eq "north"'], ['SUM(a)']);

    expect(rows).toEqual([
      { status: 'unchanged', text: 'SUM(a)' },
      { status: 'removed', text: 'region eq "north"' },
    ]);
  });
});

describe('buildMetricVersionDiff', () => {
  it('shows only unchanged rows when formula and filters are identical', () => {
    const definition = makeDefinition('amount', [{ field: 'status', operator: 'eq', value: 'DONE' }]);

    const result = buildMetricVersionDiff(definition, definition);

    expect(result.available).toBe(true);
    if (result.available) {
      expect(result.rows.map((row) => row.status)).toEqual(['unchanged', 'unchanged']);
    }
  });

  it('surfaces a formula change as SUM(a) replaced by SUM(a - b)', () => {
    const result = buildMetricVersionDiff(makeDefinition('a'), makeDefinition('a - b'));

    expect(result.available).toBe(true);
    if (result.available) {
      expect(result.rows).toEqual([
        { status: 'removed', text: 'SUM(a)' },
        { status: 'added', text: 'SUM(a - b)' },
      ]);
    }
  });

  it('surfaces filter value changes while keeping other lines unchanged', () => {
    const previous = makeDefinition('amount', [{ field: 'status', operator: 'eq', value: 'OPEN' }]);
    const current = makeDefinition('amount', [{ field: 'status', operator: 'eq', value: 'DONE' }]);

    const result = buildMetricVersionDiff(previous, current);

    expect(result.available).toBe(true);
    if (result.available) {
      expect(result.rows).toEqual([
        { status: 'unchanged', text: 'SUM(amount)' },
        { status: 'removed', text: 'status eq "OPEN"' },
        { status: 'added', text: 'status eq "DONE"' },
      ]);
    }
  });

  it('keeps ordering stable when equal filters arrive in a different order', () => {
    const previous = makeDefinition('amount', [
      { field: 'status', operator: 'eq', value: 'DONE' },
      { field: 'region', operator: 'eq', value: 'north' },
    ]);
    const current = makeDefinition('amount', [
      { field: 'region', operator: 'eq', value: 'north' },
      { field: 'status', operator: 'eq', value: 'DONE' },
    ]);

    const result = buildMetricVersionDiff(previous, current);

    expect(result.available).toBe(true);
    if (result.available) {
      expect(result.rows.every((row) => row.status === 'unchanged')).toBe(true);
    }
  });

  it('reports an unavailable diff for legacy null definitions', () => {
    expect(buildMetricVersionDiff(null, makeDefinition('a'))).toEqual({ available: false });
    expect(buildMetricVersionDiff(makeDefinition('a'), null)).toEqual({ available: false });
    expect(buildMetricVersionDiff(null, null)).toEqual({ available: false });
  });
});
