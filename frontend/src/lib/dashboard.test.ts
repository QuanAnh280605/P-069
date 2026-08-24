import { describe, expect, it } from 'vitest';

import {
  CatalogColumn,
  CatalogTable,
  MetricDefinition,
  MetricRecord,
  SemanticCatalog,
} from '@/lib/api';
import {
  DASHBOARD_DATE_PRESETS,
  DASHBOARD_MAX_WIDGETS,
  DASHBOARD_WIDTH_SPAN,
  DashboardLayoutParseError,
  DashboardWidgetConfig,
  buildDateRangeFilters,
  buildStarterDashboardWidgets,
  formatDateOnlyUtc,
  parseDashboardLayoutPayload,
  recommendDashboardChartType,
  resolveDatePresetBounds,
  resolveDrillDownDateFilters,
} from '@/lib/dashboard';

function column(overrides: Partial<CatalogColumn> & { column_id: number }): CatalogColumn {
  return {
    column_name: `col_${overrides.column_id}`,
    business_name: `Cột ${overrides.column_id}`,
    data_type: 'VARCHAR',
    is_time_dimension: false,
    allowed_values: null,
    ...overrides,
  };
}

function table(overrides: Partial<CatalogTable> & { table_id: number }): CatalogTable {
  return {
    table_name: `table_${overrides.table_id}`,
    business_name: `Bảng ${overrides.table_id}`,
    columns: [],
    ...overrides,
  };
}

const catalog: SemanticCatalog = {
  db_id: 5,
  source_type: 'live',
  query_supported: true,
  tables: [
    table({
      table_id: 1,
      table_name: 'orders',
      business_name: 'Đơn hàng',
      columns: [
        column({ column_id: 11, column_name: 'id', data_type: 'INTEGER', is_primary_key: true }),
        column({
          column_id: 12,
          column_name: 'created_at',
          business_name: 'Ngày tạo đơn',
          data_type: 'TIMESTAMP',
          is_time_dimension: true,
        }),
        column({
          column_id: 13,
          column_name: 'total_amount',
          business_name: 'Tổng tiền',
          data_type: 'NUMERIC',
        }),
        column({
          column_id: 14,
          column_name: 'order_status',
          business_name: 'Trạng thái đơn',
          data_type: 'VARCHAR',
          allowed_values: ['NEW', 'PAID', 'COMPLETED'],
        }),
      ],
    }),
    table({
      table_id: 2,
      table_name: 'customers',
      business_name: 'Khách hàng',
      columns: [
        column({
          column_id: 21,
          column_name: 'signup_date',
          business_name: 'Ngày gia nhập',
          data_type: 'DATE',
          is_time_dimension: true,
        }),
        column({ column_id: 22, column_name: 'full_name', business_name: 'Họ tên' }),
      ],
    }),
    table({
      table_id: 3,
      table_name: 'product_categories',
      business_name: 'Nhóm sản phẩm',
      columns: [
        column({
          column_id: 31,
          column_name: 'category_code',
          business_name: 'Mã nhóm',
          data_type: 'VARCHAR',
          allowed_values: ['A', 'B', 'C', 'D'],
        }),
        column({
          column_id: 32,
          column_name: 'category_score',
          business_name: 'Điểm nhóm',
          data_type: 'NUMERIC',
        }),
      ],
    }),
  ],
  relationships: [],
};

function definition(overrides: {
  baseEntity?: string;
  baseEntityId?: number | null;
  schemaVersion?: 1 | 2;
  diagnostics?: Array<{ code: string; message: string }>;
}): MetricDefinition {
  return {
    schema_version: overrides.schemaVersion ?? 2,
    metric: {
      name: 'Metric',
      formula: { function: 'SUM', expression: 'total_amount' },
      base_entity: overrides.baseEntity ?? 'orders',
      base_entity_id: overrides.baseEntityId === undefined ? 1 : overrides.baseEntityId,
      filters: [],
      status: 'approved',
      excluded_notes: '',
    },
    ...(overrides.diagnostics ? { diagnostics: overrides.diagnostics } : {}),
  };
}

function metric(
  metricId: number,
  overrides: Parameters<typeof definition>[0] & { status?: MetricRecord['status'] } = {},
): MetricRecord {
  return {
    metric_id: metricId,
    db_id: 5,
    name: `Metric ${metricId}`,
    definition: definition(overrides),
    source: 'ai',
    status: overrides.status ?? 'approved',
    created_at: '2026-08-01T00:00:00Z',
  };
}

describe('dashboard canonical constants', () => {
  it('caps layouts at 24 widgets and maps widths onto a 24-column grid', () => {
    expect(DASHBOARD_MAX_WIDGETS).toBe(24);
    expect(DASHBOARD_WIDTH_SPAN).toEqual({ third: 8, half: 12, full: 24 });
  });

  it('exposes the six supported date presets in a stable order', () => {
    expect(DASHBOARD_DATE_PRESETS).toEqual([
      'last_7_days',
      'last_30_days',
      'last_90_days',
      'this_month',
      'this_quarter',
      'this_year',
    ]);
  });
});

describe('parseDashboardLayoutPayload', () => {
  const validKpi: DashboardWidgetConfig = {
    id: 'w-kpi',
    metric_id: 1,
    dimension_col_id: null,
    date_filter_column_id: 12,
    time_grain: null,
    chart_type: 'kpi',
    width: 'third',
    height: 'compact',
    custom_title: null,
  };

  const validLine: DashboardWidgetConfig = {
    id: 'w-line',
    metric_id: 2,
    dimension_col_id: 12,
    date_filter_column_id: 12,
    time_grain: 'month',
    chart_type: 'line',
    width: 'half',
    height: 'normal',
    custom_title: 'Doanh thu theo tháng',
  };

  it('parses an uninitialized singleton response', () => {
    const state = parseDashboardLayoutPayload({
      db_id: 5,
      layout: null,
      version: 0,
      updated_at: null,
      updated_by: null,
    });
    expect(state).toEqual({
      db_id: 5,
      layout: null,
      version: 0,
      updated_at: null,
      updated_by: null,
    });
  });

  it('parses a saved layout into canonical widgets and drops unknown keys', () => {
    const state = parseDashboardLayoutPayload({
      db_id: 5,
      version: 3,
      updated_at: '2026-08-20T10:00:00Z',
      updated_by: 7,
      layout: {
        widgets: [{ ...validLine, unexpected_extra: 'drop-me' }],
      },
    });
    expect(state.version).toBe(3);
    expect(state.updated_by).toBe(7);
    expect(state.layout).toEqual({ widgets: [validLine] });
  });

  it('rejects payloads that are not objects', () => {
    expect(() => parseDashboardLayoutPayload(null)).toThrow(DashboardLayoutParseError);
    expect(() => parseDashboardLayoutPayload('nope')).toThrow(DashboardLayoutParseError);
  });

  it('rejects missing or invalid scalar envelope fields', () => {
    expect(() =>
      parseDashboardLayoutPayload({ layout: null, version: 0, updated_at: null, updated_by: null }),
    ).toThrow(DashboardLayoutParseError);
    expect(() =>
      parseDashboardLayoutPayload({
        db_id: 'five',
        layout: null,
        version: 0,
        updated_at: null,
        updated_by: null,
      }),
    ).toThrow(DashboardLayoutParseError);
    expect(() =>
      parseDashboardLayoutPayload({
        db_id: 5,
        layout: null,
        version: -1,
        updated_at: null,
        updated_by: null,
      }),
    ).toThrow(DashboardLayoutParseError);
  });

  it('rejects a layout whose widgets are not an array', () => {
    expect(() =>
      parseDashboardLayoutPayload({
        db_id: 5,
        version: 1,
        updated_at: null,
        updated_by: null,
        layout: { widgets: 'many' },
      }),
    ).toThrow(DashboardLayoutParseError);
  });

  it('rejects widgets with unknown chart types or invalid references', () => {
    const wrap = (widget: Record<string, unknown>) => ({
      db_id: 5,
      version: 1,
      updated_at: null,
      updated_by: null,
      layout: { widgets: [widget] },
    });

    expect(() =>
      parseDashboardLayoutPayload(wrap({ ...validKpi, chart_type: 'gauge' })),
    ).toThrow(DashboardLayoutParseError);
    expect(() => parseDashboardLayoutPayload(wrap({ ...validKpi, metric_id: 0 }))).toThrow(
      DashboardLayoutParseError,
    );
    expect(() => parseDashboardLayoutPayload(wrap({ ...validKpi, width: 'two-thirds' }))).toThrow(
      DashboardLayoutParseError,
    );
    expect(() => parseDashboardLayoutPayload(wrap({ ...validKpi, height: 'huge' }))).toThrow(
      DashboardLayoutParseError,
    );
    expect(() => parseDashboardLayoutPayload(wrap({ ...validKpi, time_grain: 'fortnight' }))).toThrow(
      DashboardLayoutParseError,
    );
    expect(() => parseDashboardLayoutPayload(wrap({ ...validKpi, date_filter_column_id: -12 }))).toThrow(
      DashboardLayoutParseError,
    );
    expect(() => parseDashboardLayoutPayload(wrap({ ...validKpi, id: '' }))).toThrow(
      DashboardLayoutParseError,
    );
  });

  it('enforces backend chart compatibility while parsing', () => {
    const wrap = (widget: Record<string, unknown>) => ({
      db_id: 5,
      version: 1,
      updated_at: null,
      updated_by: null,
      layout: { widgets: [widget] },
    });

    expect(() =>
      parseDashboardLayoutPayload(wrap({ ...validKpi, dimension_col_id: 14 })),
    ).toThrow(DashboardLayoutParseError);
    expect(() =>
      parseDashboardLayoutPayload(wrap({ ...validLine, time_grain: null })),
    ).toThrow(DashboardLayoutParseError);
    expect(() =>
      parseDashboardLayoutPayload(
        wrap({
          id: 'w-bar',
          metric_id: 3,
          dimension_col_id: null,
          date_filter_column_id: null,
          time_grain: null,
          chart_type: 'bar',
          width: 'third',
          height: 'normal',
          custom_title: null,
        }),
      ),
    ).toThrow(DashboardLayoutParseError);
  });

  it('rejects duplicate widget ids and more than the persisted maximum', () => {
    const duplicated = {
      db_id: 5,
      version: 1,
      updated_at: null,
      updated_by: null,
      layout: { widgets: [validKpi, { ...validKpi, id: 'w-kpi' }] },
    };
    expect(() => parseDashboardLayoutPayload(duplicated)).toThrow(DashboardLayoutParseError);

    const overflowWidgets: DashboardWidgetConfig[] = Array.from(
      { length: DASHBOARD_MAX_WIDGETS + 1 },
      (_, index) => ({ ...validKpi, id: `w-${index}` }),
    );
    expect(() =>
      parseDashboardLayoutPayload({
        db_id: 5,
        version: 1,
        updated_at: null,
        updated_by: null,
        layout: { widgets: overflowWidgets },
      }),
    ).toThrow(DashboardLayoutParseError);
  });

  it('normalizes absent optional fields to nulls', () => {
    const state = parseDashboardLayoutPayload({
      db_id: 5,
      version: 2,
      layout: {
        widgets: [
          {
            id: 'w-bar',
            metric_id: 3,
            dimension_col_id: 14,
            chart_type: 'bar',
            width: 'third',
            height: 'normal',
          },
        ],
      },
    });
    expect(state.layout?.widgets[0]).toEqual({
      id: 'w-bar',
      metric_id: 3,
      dimension_col_id: 14,
      date_filter_column_id: null,
      time_grain: null,
      chart_type: 'bar',
      width: 'third',
      height: 'normal',
      custom_title: null,
    });
  });
});

describe('recommendDashboardChartType', () => {
  it('recommends a KPI when there is no dimension column', () => {
    expect(recommendDashboardChartType(null)).toBe('kpi');
  });

  it('recommends a line chart for time dimensions', () => {
    const createdAt = catalog.tables[0].columns[1];
    expect(recommendDashboardChartType(createdAt)).toBe('line');
  });

  it('recommends a pie chart for low-cardinality categorical dimensions', () => {
    const status = catalog.tables[0].columns[3];
    expect(recommendDashboardChartType(status)).toBe('pie');
  });

  it('recommends a bar chart for open-ended categorical dimensions', () => {
    const fullName = catalog.tables[1].columns[1];
    expect(recommendDashboardChartType(fullName)).toBe('bar');
  });
});

describe('buildStarterDashboardWidgets', () => {
  it('returns an empty list when nothing can be inferred safely', () => {
    expect(buildStarterDashboardWidgets({ metrics: [], catalog })).toEqual([]);
    expect(buildStarterDashboardWidgets({ metrics: [], catalog: null })).toEqual([]);
    const unexecutable = [
      metric(1, { status: 'pending_approval' }),
      metric(2, { schemaVersion: 1 }),
      metric(3, { diagnostics: [{ code: 'GRAIN_UNSUPPORTED', message: 'bad grain' }] }),
    ];
    expect(buildStarterDashboardWidgets({ metrics: unexecutable, catalog })).toEqual([]);
  });

  it('skips metrics whose base table offers no safe time or business dimension', () => {
    const bareCatalog: SemanticCatalog = {
      ...catalog,
      tables: [
        table({
          table_id: 9,
          table_name: 'ledger',
          columns: [
            column({ column_id: 91, column_name: 'entry_id', data_type: 'INTEGER', is_primary_key: true }),
            column({ column_id: 92, column_name: 'amount', data_type: 'NUMERIC' }),
          ],
        }),
      ],
    };
    const ledgerMetric = [metric(50, { baseEntity: 'ledger', baseEntityId: 9 })];
    expect(buildStarterDashboardWidgets({ metrics: ledgerMetric, catalog: bareCatalog })).toEqual([]);
  });

  it('builds deterministic cards preferring explicit time columns', () => {
    const metrics = [
      metric(1),
      metric(2),
      metric(30, { baseEntity: 'product_categories', baseEntityId: 3 }),
    ];

    const widgets = buildStarterDashboardWidgets({ metrics, catalog });

    expect(widgets).toHaveLength(3);
    expect(widgets[0]).toEqual({
      id: 'starter-1',
      metric_id: 1,
      dimension_col_id: null,
      date_filter_column_id: 12,
      time_grain: null,
      chart_type: 'kpi',
      width: 'third',
      height: 'compact',
      custom_title: null,
    });
    expect(widgets[1]).toEqual({
      id: 'starter-2',
      metric_id: 2,
      dimension_col_id: 12,
      date_filter_column_id: 12,
      time_grain: 'month',
      chart_type: 'line',
      width: 'half',
      height: 'normal',
      custom_title: null,
    });
    expect(widgets[2]).toEqual({
      id: 'starter-30',
      metric_id: 30,
      dimension_col_id: 31,
      date_filter_column_id: null,
      time_grain: null,
      chart_type: 'pie',
      width: 'third',
      height: 'normal',
      custom_title: null,
    });
  });

  it('produces at most five cards and only references catalog column ids', () => {
    const metrics = Array.from({ length: 8 }, (_, index) => metric(index + 1));
    const widgets = buildStarterDashboardWidgets({ metrics, catalog });

    expect(widgets).toHaveLength(5);
    const knownColumnIds = new Set(catalog.tables.flatMap((t) => t.columns.map((c) => c.column_id)));
    for (const widget of widgets) {
      expect(widget.id).toBe(`starter-${widget.metric_id}`);
      if (widget.dimension_col_id !== null) expect(knownColumnIds.has(widget.dimension_col_id)).toBe(true);
      if (widget.date_filter_column_id !== null) {
        expect(knownColumnIds.has(widget.date_filter_column_id)).toBe(true);
      }
    }
  });
});

describe('UTC date preset helpers', () => {
  const now = new Date('2026-08-24T15:30:45Z');

  it('formats UTC date-only strings regardless of local timezone', () => {
    expect(formatDateOnlyUtc(new Date('2026-08-24T15:30:45Z'))).toBe('2026-08-24');
    expect(formatDateOnlyUtc(new Date('2026-01-05T00:30:00Z'))).toBe('2026-01-05');
  });

  it('computes rolling windows ending at the current UTC day', () => {
    expect(resolveDatePresetBounds('last_7_days', now)).toEqual({
      start: '2026-08-18',
      endExclusive: '2026-08-25',
    });
    expect(resolveDatePresetBounds('last_30_days', now)).toEqual({
      start: '2026-07-26',
      endExclusive: '2026-08-25',
    });
    expect(resolveDatePresetBounds('last_90_days', now)).toEqual({
      start: '2026-05-27',
      endExclusive: '2026-08-25',
    });
  });

  it('computes calendar windows in UTC', () => {
    expect(resolveDatePresetBounds('this_month', now)).toEqual({
      start: '2026-08-01',
      endExclusive: '2026-09-01',
    });
    expect(resolveDatePresetBounds('this_quarter', now)).toEqual({
      start: '2026-07-01',
      endExclusive: '2026-10-01',
    });
    expect(resolveDatePresetBounds('this_year', now)).toEqual({
      start: '2026-01-01',
      endExclusive: '2027-01-01',
    });
  });

  it('handles year and month boundaries deterministically', () => {
    const newYear = new Date('2027-01-15T00:00:00Z');
    expect(resolveDatePresetBounds('this_year', newYear)).toEqual({
      start: '2027-01-01',
      endExclusive: '2028-01-01',
    });
    const monthEdge = new Date('2026-03-05T23:59:59Z');
    expect(resolveDatePresetBounds('last_7_days', monthEdge)).toEqual({
      start: '2026-02-27',
      endExclusive: '2026-03-06',
    });
  });

  it('emits half-open gte/lt query filters against the chosen column', () => {
    const bounds = resolveDatePresetBounds('this_month', now);
    expect(buildDateRangeFilters(15, bounds)).toEqual([
      { column_id: 15, operator: 'gte', value: '2026-08-01' },
      { column_id: 15, operator: 'lt', value: '2026-09-01' },
    ]);
  });
});

describe('resolveDrillDownDateFilters', () => {
  const now = new Date('2026-08-24T15:30:45Z');
  const baseWidget: DashboardWidgetConfig = {
    id: 'w1',
    metric_id: 1,
    dimension_col_id: null,
    date_filter_column_id: 12,
    time_grain: null,
    chart_type: 'kpi',
    width: 'third',
    height: 'compact',
    custom_title: null,
  };

  it('resolves the chosen date preset into gte/lt filters for the widget date column', () => {
    expect(resolveDrillDownDateFilters(baseWidget, 'this_year', now)).toEqual([
      { column_id: 12, operator: 'gte', value: '2026-01-01' },
      { column_id: 12, operator: 'lt', value: '2027-01-01' },
    ]);
  });

  it('returns no filters when the preset is null (all-time semantics)', () => {
    expect(resolveDrillDownDateFilters(baseWidget, null, now)).toEqual([]);
  });

  it('returns no filters when the widget has no date filter column', () => {
    const noDate = { ...baseWidget, date_filter_column_id: null };
    expect(resolveDrillDownDateFilters(noDate, 'last_30_days', now)).toEqual([]);
  });
});
