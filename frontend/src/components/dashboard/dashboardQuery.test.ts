import { beforeEach, describe, expect, it, vi } from 'vitest';

import { executeSemanticQueryApi, type SemanticQueryResult } from '@/lib/api';
import {
  buildDateRangeFilters,
  DashboardWidgetConfig,
  resolveDatePresetBounds,
} from '@/lib/dashboard';

import {
  buildWidgetPoints,
  buildWidgetQueryRequests,
  DashboardWidgetConfigError,
  extractTotalValue,
  KPI_TREND_DEFAULT_GRAIN,
  MAX_CONCURRENT_WIDGET_QUERIES,
  resetWidgetQueryScheduler,
  runWidgetExecution,
  WIDGET_ROW_LIMIT,
} from './dashboardQuery';

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return { ...actual, executeSemanticQueryApi: vi.fn() };
});

const NOW = new Date(Date.UTC(2026, 7, 20));

function widget(overrides: Partial<DashboardWidgetConfig>): DashboardWidgetConfig {
  return {
    id: 'w1',
    metric_id: 5,
    dimension_col_id: null,
    date_filter_column_id: null,
    time_grain: null,
    chart_type: 'kpi',
    width: 'third',
    height: 'compact',
    custom_title: null,
    ...overrides,
  };
}

function makeResult(columns: string[], rows: unknown[][]): SemanticQueryResult {
  return { sql: 'SELECT 1', parameters: {}, columns, rows, row_count: rows.length };
}

describe('buildWidgetQueryRequests', () => {
  it('builds one bounded request for line widgets with grain and date filters', () => {
    const requests = buildWidgetQueryRequests({
      widget: widget({
        chart_type: 'line',
        dimension_col_id: 12,
        date_filter_column_id: 12,
        time_grain: 'month',
      }),
      globalGrain: null,
      datePreset: 'last_30_days',
      now: NOW,
    });

    expect(requests).toHaveLength(1);
    expect(requests[0].metric_ids).toEqual([5]);
    expect(requests[0].dimensions).toEqual([{ column_id: 12, time_grain: 'month' }]);
    expect(requests[0].limit).toBe(100);
    expect(requests[0].filters).toEqual(
      buildDateRangeFilters(12, resolveDatePresetBounds('last_30_days', NOW)),
    );
    expect(requests[0].filters[0]).toMatchObject({ operator: 'gte', value: '2026-07-22' });
    expect(requests[0].filters[1]).toMatchObject({ operator: 'lt', value: '2026-08-21' });
  });

  it('emits no date filters when the date preset is opted out', () => {
    const requests = buildWidgetQueryRequests({
      widget: widget({ chart_type: 'bar', dimension_col_id: 3 }),
      globalGrain: null,
      datePreset: null,
      now: NOW,
    });

    expect(requests[0].filters).toEqual([]);
  });

  it('emits no date filters when the widget has no date column even with a preset', () => {
    const requests = buildWidgetQueryRequests({
      widget: widget({ chart_type: 'pie', dimension_col_id: 3, date_filter_column_id: null }),
      globalGrain: null,
      datePreset: 'this_month',
      now: NOW,
    });

    expect(requests[0].filters).toEqual([]);
  });

  it('returns a total request plus a trend request for KPI widgets', () => {
    const requests = buildWidgetQueryRequests({
      widget: widget({ chart_type: 'kpi', date_filter_column_id: 9 }),
      globalGrain: 'week',
      datePreset: 'last_7_days',
      now: NOW,
    });

    expect(requests).toHaveLength(2);
    expect(requests[0]).toMatchObject({ metric_ids: [5], limit: 1 });
    expect(requests[0].dimensions).toBeUndefined();
    expect(requests[0].filters.length).toBe(2);
    expect(requests[1].metric_ids).toEqual([5]);
    expect(requests[1].dimensions).toEqual([{ column_id: 9, time_grain: 'week' }]);
    expect(requests[1].limit).toBe(WIDGET_ROW_LIMIT);
  });

  it('falls back to the default grain for KPI trends without a global grain', () => {
    const requests = buildWidgetQueryRequests({
      widget: widget({ chart_type: 'kpi', date_filter_column_id: 9 }),
      globalGrain: null,
      datePreset: null,
      now: NOW,
    });

    expect(KPI_TREND_DEFAULT_GRAIN).toBe('month');
    expect(requests[1].dimensions?.[0]?.time_grain).toBe('month');
  });

  it('lets the global grain override the persisted widget grain', () => {
    const requests = buildWidgetQueryRequests({
      widget: widget({
        chart_type: 'area',
        dimension_col_id: 12,
        date_filter_column_id: 12,
        time_grain: 'month',
      }),
      globalGrain: 'quarter',
      datePreset: null,
      now: NOW,
    });

    expect(requests[0].dimensions?.[0]?.time_grain).toBe('quarter');
  });

  it('requests categorical dimensions without a time grain', () => {
    for (const chartType of ['bar', 'pie', 'table'] as const) {
      const requests = buildWidgetQueryRequests({
        widget: widget({ chart_type: chartType, dimension_col_id: 3 }),
        globalGrain: 'day',
        datePreset: null,
        now: NOW,
      });

      expect(requests).toHaveLength(1);
      expect(Object.keys(requests[0].dimensions?.[0] ?? {})).toEqual(['column_id']);
    }
  });

  it('caps every request limit at one hundred rows', () => {
    const variants = [
      { chart_type: 'kpi' as const, date_filter_column_id: 9 },
      { chart_type: 'line' as const, dimension_col_id: 12, date_filter_column_id: 12, time_grain: 'month' as const },
      { chart_type: 'table' as const, dimension_col_id: 3 },
    ];
    for (const variant of variants) {
      const requests = buildWidgetQueryRequests({
        widget: widget(variant),
        globalGrain: 'year',
        datePreset: 'last_90_days',
        now: NOW,
      });
      for (const request of requests) {
        expect(request.limit).toBeGreaterThanOrEqual(1);
        expect(request.limit).toBeLessThanOrEqual(100);
      }
    }
  });

  it('throws configuration errors for incompatible persisted widgets', () => {
    const cases = [
      widget({ chart_type: 'kpi', date_filter_column_id: null }),
      widget({ chart_type: 'line', dimension_col_id: null, date_filter_column_id: 12 }),
      widget({ chart_type: 'bar', dimension_col_id: null }),
    ];
    for (const broken of cases) {
      expect(() =>
        buildWidgetQueryRequests({ widget: broken, globalGrain: null, datePreset: null, now: NOW }),
      ).toThrow(DashboardWidgetConfigError);
    }
  });

  it('requires a resolvable grain for time-series charts', () => {
    expect(() =>
      buildWidgetQueryRequests({
        widget: widget({ chart_type: 'line', dimension_col_id: 12, time_grain: null }),
        globalGrain: null,
        datePreset: null,
        now: NOW,
      }),
    ).toThrow(DashboardWidgetConfigError);
  });
});

describe('result to points mapping', () => {
  it('maps alias columns into formatted points with null safety', () => {
    const points = buildWidgetPoints({
      result: makeResult(
        ['dimension_12', 'metric_5'],
        [
          ['pending', 3],
          [null, null],
          ['done', '7'],
        ],
      ),
      metricId: 5,
      dimensionId: 12,
      sortByTime: false,
    });

    expect(points).toEqual([
      { label: 'pending', rawLabel: 'pending', value: 3, rawValue: 3 },
      { label: '(Trống)', rawLabel: '', value: 0, rawValue: null },
      { label: 'done', rawLabel: 'done', value: 7, rawValue: '7' },
    ]);
  });

  it('sorts time-series points by parsed keys when requested', () => {
    const points = buildWidgetPoints({
      result: makeResult(
        ['dimension_9', 'metric_5'],
        [
          ['2024-03', 3],
          ['2024-01', 1],
          ['2024-02', 2],
        ],
      ),
      metricId: 5,
      dimensionId: 9,
      sortByTime: true,
    });

    expect(points.map((item) => item.rawLabel)).toEqual(['2024-01', '2024-02', '2024-03']);
  });

  it('falls back to positional columns when aliases are absent', () => {
    const points = buildWidgetPoints({
      result: makeResult(['status', 'SUM(price)'], [['hà nội', '1500']]),
      metricId: 5,
      dimensionId: null,
      sortByTime: false,
    });

    expect(points[0]).toMatchObject({ label: 'hà nội', value: 1500 });
  });

  it('extracts the KPI total strictly from the first row', () => {
    expect(extractTotalValue(makeResult(['metric_5'], [[42]]), 5)).toBe(42);
    expect(extractTotalValue(makeResult(['metric_5'], []), 5)).toBeNull();
    expect(extractTotalValue(makeResult(['metric_5'], [[null]]), 5)).toBeNull();
    expect(extractTotalValue(makeResult(['other'], [['n/a']]), 5)).toBeNull();
  });
});

describe('widget execution scheduler', () => {
  const request = {
    metric_ids: [5],
    filters: [],
    limit: WIDGET_ROW_LIMIT,
  };

  beforeEach(() => {
    resetWidgetQueryScheduler();
  });

  it('caps concurrent executions at three across cards', async () => {
    let active = 0;
    let maxActive = 0;
    vi.mocked(executeSemanticQueryApi).mockImplementation(async () => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setTimeout(resolve, 5));
      active -= 1;
      return makeResult(['metric_5'], [[10]]);
    });

    await Promise.all(
      Array.from({ length: 10 }, () => runWidgetExecution('7', request)),
    );

    expect(executeSemanticQueryApi).toHaveBeenCalledTimes(10);
    expect(maxActive).toBe(MAX_CONCURRENT_WIDGET_QUERIES);
    expect(maxActive).toBe(6);
  });

  it('starts work immediately while below the cap', async () => {
    let active = 0;
    let maxActive = 0;
    vi.mocked(executeSemanticQueryApi).mockImplementation(async () => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await Promise.resolve();
      active -= 1;
      return makeResult(['metric_5'], [[10]]);
    });

    await Promise.all([
      runWidgetExecution('7', request),
      runWidgetExecution('7', request),
    ]);

    expect(maxActive).toBe(2);
  });

  it('propagates execution errors to the caller', async () => {
    vi.mocked(executeSemanticQueryApi).mockRejectedValueOnce(new Error('timeout'));
    await expect(runWidgetExecution('7', request)).rejects.toThrow('timeout');
  });
});
