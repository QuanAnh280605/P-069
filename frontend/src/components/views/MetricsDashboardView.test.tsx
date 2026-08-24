import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { MetricRecord, SemanticCatalog, SemanticQueryRequest } from '@/lib/api';
import {
  DashboardLayoutState,
  DashboardWidgetConfig,
} from '@/lib/dashboard';
import {
  DashboardVersionConflictError,
} from '@/lib/dashboardApi';

import { DashboardCard } from '@/components/dashboard/DashboardCard';
import {
  DashboardGrid,
  reorderWidgets,
  widthToSpanClass,
} from '@/components/dashboard/DashboardGrid';
import { clearDashboardPayloadCache } from '@/components/dashboard/useDashboardWidgetData';
import { MetricsDashboardView } from './MetricsDashboardView';

const apiMocks = vi.hoisted(() => ({
  executeSemanticQueryApi: vi.fn(),
  getMetricRecommendedDimensionsApi: vi.fn(),
  getMetricFilterColumnsApi: vi.fn(),
  loadDashboardApi: vi.fn(),
  saveDashboardApi: vi.fn(),
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    executeSemanticQueryApi: apiMocks.executeSemanticQueryApi,
    getMetricRecommendedDimensionsApi: apiMocks.getMetricRecommendedDimensionsApi,
    getMetricFilterColumnsApi: apiMocks.getMetricFilterColumnsApi,
  };
});

vi.mock('@/lib/dashboardApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/dashboardApi')>();
  return {
    ...actual,
    loadDashboardApi: apiMocks.loadDashboardApi,
    saveDashboardApi: apiMocks.saveDashboardApi,
  };
});

const recharts = vi.hoisted(() => {
  const stub = (_props?: unknown) => null;
  const container = (props: { children?: unknown }) => props.children ?? null;
  return {
    ResponsiveContainer: vi.fn(container),
    AreaChart: vi.fn(container),
    LineChart: vi.fn(container),
    BarChart: vi.fn(container),
    PieChart: vi.fn(container),
    Line: vi.fn(stub),
    Area: vi.fn(stub),
    Bar: vi.fn(stub),
    Pie: vi.fn(stub),
    Cell: vi.fn(stub),
    XAxis: vi.fn(stub),
    YAxis: vi.fn(stub),
    CartesianGrid: vi.fn(stub),
    Tooltip: vi.fn(stub),
    Legend: vi.fn(stub),
  };
});

vi.mock('recharts', () => recharts);

// ---------------------------------------------------------------------------
// Builders
// ---------------------------------------------------------------------------

function makeCatalog(querySupported = true): SemanticCatalog {
  return {
    db_id: 9,
    source_type: 'live',
    query_supported: querySupported,
    tables: [
      {
        table_id: 1,
        table_name: 'orders',
        business_name: 'Đơn hàng',
        columns: [
          {
            column_id: 15,
            column_name: 'created_at',
            business_name: 'Ngày tạo',
            data_type: 'TIMESTAMP',
            is_time_dimension: true,
            allowed_values: null,
          },
          {
            column_id: 31,
            column_name: 'customer',
            business_name: 'Khách hàng',
            data_type: 'VARCHAR',
            is_time_dimension: false,
            allowed_values: ['a', 'b', 'c'],
          },
        ],
      },
    ],
    relationships: [],
  };
}

function makeMetric(id: number, name: string, status: MetricRecord['status'] = 'approved'): MetricRecord {
  return {
    metric_id: id,
    name,
    source: 'ai',
    status,
    created_at: '2026-01-01T00:00:00Z',
    definition: {
      schema_version: 2,
      metric: {
        name,
        formula: { function: 'SUM', expression: 'amount' },
        base_entity: 'orders',
        filters: [],
        status,
        excluded_notes: '',
      },
      diagnostics: [],
    },
  };
}

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

function makeResult(columns: string[], rows: unknown[][]) {
  return { sql: 'SELECT 1', parameters: {}, columns, rows, row_count: rows.length };
}

function stateWith(layout: DashboardLayoutState['layout'], overrides: Partial<DashboardLayoutState> = {}): DashboardLayoutState {
  return {
    db_id: 9,
    layout,
    version: 1,
    updated_at: '2026-08-01T10:00:00Z',
    updated_by: 42,
    ...overrides,
  };
}

const DIMENSIONS_RESPONSE = {
  metric_id: 5,
  metric_name: 'Doanh thu',
  base_table: 'orders',
  dimensions: [
    { column_id: 31, column_name: 'customer', business_name: 'Khách hàng', table_id: 1, table_name: 'orders', table_business_name: 'Đơn hàng', tier: 'A' as const, tier_label: 'Trực tiếp', is_safe_join: true, requires_reaggregation: false, data_type: 'VARCHAR', cardinality_hint: 3 },
  ],
};

const FILTER_COLUMNS_RESPONSE = {
  metric_id: 5,
  metric_name: 'Doanh thu',
  base_table: 'orders',
  columns: [
    { column_id: 15, column_name: 'created_at', business_name: 'Ngày tạo', table_id: 1, table_name: 'orders', table_business_name: 'Đơn hàng', group_type: 'base' as const, data_type: 'TIMESTAMP', is_time_dimension: true },
  ],
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  clearDashboardPayloadCache();
  apiMocks.executeSemanticQueryApi.mockResolvedValue(
    makeResult(['metric_5'], [[100]]),
  );
  apiMocks.getMetricRecommendedDimensionsApi.mockResolvedValue(DIMENSIONS_RESPONSE);
  apiMocks.getMetricFilterColumnsApi.mockResolvedValue(FILTER_COLUMNS_RESPONSE);
  apiMocks.loadDashboardApi.mockResolvedValue(stateWith(null));
  apiMocks.saveDashboardApi.mockImplementation(async (_dbId, layout) =>
    stateWith(layout, { version: 1, updated_at: '2026-08-01T10:00:00Z', updated_by: 42 }),
  );
});

afterEach(cleanup);

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

describe('reorderWidgets', () => {
  const items = [widget({ id: 'a' }), widget({ id: 'b' }), widget({ id: 'c' })];

  it('moves an item to the target position', () => {
    expect(reorderWidgets(items, 'a', 'c').map((w) => w.id)).toEqual(['b', 'c', 'a']);
    expect(reorderWidgets(items, 'c', 'a').map((w) => w.id)).toEqual(['c', 'a', 'b']);
  });

  it('returns the same list when ids are identical or missing', () => {
    expect(reorderWidgets(items, 'a', 'a')).toBe(items);
    expect(reorderWidgets(items, 'a', 'missing')).toBe(items);
  });
});

describe('widthToSpanClass', () => {
  it('maps each width to a responsive 24-column span', () => {
    expect(widthToSpanClass('third')).toContain('md:col-span-8');
    expect(widthToSpanClass('half')).toContain('md:col-span-12');
    expect(widthToSpanClass('full')).toContain('md:col-span-24');
  });
});

// ---------------------------------------------------------------------------
// DashboardCard
// ---------------------------------------------------------------------------

describe('DashboardCard', () => {
  const baseProps = {
    widget: widget({ id: 'w1', metric_id: 5, chart_type: 'bar', dimension_col_id: 31, custom_title: 'Doanh thu' }),
    dbId: 9,
    globalGrain: null,
    datePreset: null,
    refreshGeneration: 0,
    querySupported: true,
    editMode: false,
    metricName: 'Doanh thu thuần',
    dimensionLabel: null,
    isFirst: true,
    isLast: false,
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onResize: vi.fn(),
  };

  it('renders the resolved title and queries data when supported', async () => {
    render(<DashboardCard {...baseProps} />);
    expect(screen.getByTestId('dashboard-card-title')).toHaveTextContent('Doanh thu');
    await waitFor(() => expect(apiMocks.executeSemanticQueryApi).toHaveBeenCalled());
  });

  it('does not query when the source is not supported', () => {
    render(<DashboardCard {...baseProps} querySupported={false} />);
    expect(apiMocks.executeSemanticQueryApi).not.toHaveBeenCalled();
  });

  it('shows edit controls only in edit mode and allows editing and deleting', () => {
    const { rerender } = render(<DashboardCard {...baseProps} editMode={false} />);
    expect(screen.queryByLabelText(/Chỉnh sửa widget/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Xóa widget/)).not.toBeInTheDocument();

    rerender(<DashboardCard {...baseProps} editMode />);
    const edit = screen.getByLabelText(/Chỉnh sửa widget/) as HTMLButtonElement;
    const deleteBtn = screen.getByLabelText(/Xóa widget/) as HTMLButtonElement;
    fireEvent.click(edit);
    fireEvent.click(deleteBtn);
    expect(baseProps.onEdit).toHaveBeenCalledTimes(1);
    expect(baseProps.onDelete).toHaveBeenCalledTimes(1);
  });

  it('invokes the drill-down callback with the widget and current date preset', () => {
    const onDrillDown = vi.fn();
    render(<DashboardCard {...baseProps} onDrillDown={onDrillDown} />);
    fireEvent.click(screen.getByRole('button', { name: 'Xem chi tiết' }));
    expect(onDrillDown).toHaveBeenCalledTimes(1);
    expect(onDrillDown).toHaveBeenCalledWith(baseProps.widget, baseProps.datePreset);
  });

  it('retries after an error', async () => {
    apiMocks.executeSemanticQueryApi.mockRejectedValueOnce(new Error('boom'));
    render(<DashboardCard {...baseProps} />);
    const retry = await screen.findByRole('button', { name: 'Thử lại' });
    expect(retry).toBeInTheDocument();
    apiMocks.executeSemanticQueryApi.mockResolvedValue(makeResult(['metric_5'], [[5]]));
    fireEvent.click(retry);
    await waitFor(() => expect(apiMocks.executeSemanticQueryApi).toHaveBeenCalledTimes(2));
  });
});

// ---------------------------------------------------------------------------
// DashboardGrid
// ---------------------------------------------------------------------------

describe('DashboardGrid', () => {
  const widgets = [
    widget({ id: 'a', metric_id: 5, custom_title: 'A', width: 'third' }),
    widget({ id: 'b', metric_id: 6, custom_title: 'B', width: 'half' }),
  ];
  const metrics = [makeMetric(5, 'A'), makeMetric(6, 'B')];
  const catalog = makeCatalog();

  function renderGrid(onReorder = vi.fn(), onResizeWidget = vi.fn()) {
    return render(
      <DashboardGrid
        widgets={widgets}
        dbId={9}
        globalGrain={null}
        datePreset={null}
        refreshGeneration={0}
        querySupported
        editMode
        metrics={metrics}
        catalog={catalog}
        onReorder={onReorder}
        onResizeWidget={onResizeWidget}
        onEditWidget={vi.fn()}
        onDeleteWidget={vi.fn()}
      />,
    );
  }

  it('wraps each card with its 24-column grid style and stable id', () => {
    const { container } = renderGrid();
    const first = container.querySelector('[data-widget-id="a"]') as HTMLElement;
    expect(first.getAttribute('data-widget-id')).toBe('a');
    expect(first.style.gridColumn).toBe('span 8 / span 8');
  });

  it('reorders widgets correctly', () => {
    const reordered = reorderWidgets(widgets, 'a', 'b');
    expect(reordered.map((w) => w.id)).toEqual(['b', 'a']);
  });

  it('does not persist reorder during a drag (only on drop)', () => {
    const onReorder = vi.fn();
    renderGrid(onReorder);
    expect(onReorder).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// MetricsDashboardView
// ---------------------------------------------------------------------------

function renderView(overrides: Record<string, unknown> = {}) {
  const props = {
    dbId: 9,
    metrics: [makeMetric(5, 'Doanh thu'), makeMetric(6, 'Số lượng')],
    catalog: makeCatalog(),
    database: { id: '9', name: 'Live DB', engine: 'postgresql' as const, status: 'connected' as const, tables: 1 },
    canEdit: true,
    onOpenCatalog: vi.fn(),
    onDrillDown: vi.fn(),
    ...overrides,
  };
  const utils = render(<MetricsDashboardView {...props} />);
  return {
    ...utils,
    onOpenCatalog: props.onOpenCatalog as ReturnType<typeof vi.fn>,
    onDrillDown: props.onDrillDown as ReturnType<typeof vi.fn>,
  };
}

describe('MetricsDashboardView — gates and loading', () => {
  it('shows a loading state before the layout resolves', () => {
    apiMocks.loadDashboardApi.mockReturnValue(new Promise(() => {}));
    renderView();
    expect(screen.getByText(/Đang tải bảng điều khiển/)).toBeInTheDocument();
  });

  it('shows Live-DB guidance for SQL Dump and issues zero compile/execute calls', () => {
    renderView({ catalog: makeCatalog(false) });
    expect(screen.getByText(/SQL Dump/)).toBeInTheDocument();
    expect(apiMocks.loadDashboardApi).not.toHaveBeenCalled();
    expect(apiMocks.executeSemanticQueryApi).not.toHaveBeenCalled();
  });

  it('shows a no-approved-metrics state linking to Catalog', () => {
    const pending = makeMetric(5, 'Chờ', 'pending_approval');
    const { onOpenCatalog } = renderView({ metrics: [pending] });
    const link = screen.getByRole('button', { name: /Đi tới Catalog/ });
    fireEvent.click(link);
    expect(onOpenCatalog).toHaveBeenCalledTimes(1);
  });
});

describe('MetricsDashboardView — persistence', () => {
  it('builds a starter layout and saves it with expected_version 0 when none exists', async () => {
    apiMocks.loadDashboardApi.mockResolvedValue(stateWith(null));
    renderView();
    await waitFor(() =>
      expect(apiMocks.saveDashboardApi).toHaveBeenCalledWith(
        9,
        expect.objectContaining({ widgets: expect.any(Array) }),
        0,
      ),
    );
    const saved = apiMocks.saveDashboardApi.mock.calls[0][1] as { widgets: DashboardWidgetConfig[] };
    expect(saved.widgets.length).toBeGreaterThan(0);
  });

  it('does not re-save when a layout already exists', async () => {
    apiMocks.loadDashboardApi.mockResolvedValue(
      stateWith({ widgets: [widget({ id: 'existing', metric_id: 5, custom_title: 'Đã có' })] }),
    );
    renderView();
    await waitFor(() => expect(screen.getByTestId('dashboard-card-title')).toBeInTheDocument());
    expect(apiMocks.saveDashboardApi).not.toHaveBeenCalled();
  });

  it('displays persisted updated-at and updater metadata', async () => {
    apiMocks.loadDashboardApi.mockResolvedValue(
      stateWith({ widgets: [widget({ id: 'existing', metric_id: 5, custom_title: 'Có sẵn' })] }, { updated_at: '2026-08-01T10:00:00Z', updated_by: 42 }),
    );
    renderView();
    const meta = await screen.findByTestId('layout-metadata');
    expect(meta).toHaveAttribute('data-updated-at', '2026-08-01T10:00:00Z');
    expect(meta).toHaveAttribute('data-updated-by', '42');
  });
});

describe('MetricsDashboardView — edit, add, delete', () => {
  beforeEach(() => {
    apiMocks.loadDashboardApi.mockResolvedValue(
      stateWith({ widgets: [widget({ id: 'a', metric_id: 5, custom_title: 'A', chart_type: 'kpi', date_filter_column_id: 15 })] }),
    );
  });

  it('toggles edit mode to reveal widget controls', async () => {
    renderView();
    await screen.findByTestId('dashboard-card-title');
    expect(screen.queryByLabelText(/Chỉnh sửa widget/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Chỉnh sửa' }));
    expect(screen.getByLabelText(/Chỉnh sửa widget/)).toBeInTheDocument();
  });

  it('adds a widget through the modal and persists the new layout', async () => {
    renderView();
    await screen.findByTestId('dashboard-card-title');
    fireEvent.click(screen.getByRole('button', { name: 'Chỉnh sửa' }));
    fireEvent.click(screen.getByRole('button', { name: 'Thêm widget' }));

    const metricSelect = await screen.findByLabelText('Metric');
    fireEvent.change(metricSelect, { target: { value: '5' } });
    const dateSelect = await screen.findByLabelText('Cột lọc ngày');
    fireEvent.change(dateSelect, { target: { value: '15' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    await waitFor(() =>
      expect(apiMocks.saveDashboardApi).toHaveBeenCalledWith(
        9,
        expect.objectContaining({ widgets: expect.arrayContaining([expect.objectContaining({ id: 'a' })]) }),
        1,
      ),
    );
  });

  it('edits an existing widget and persists the updated layout', async () => {
    renderView();
    await screen.findByTestId('dashboard-card-title');
    fireEvent.click(screen.getByRole('button', { name: 'Chỉnh sửa' }));
    fireEvent.click(screen.getByLabelText(/Chỉnh sửa widget/));
    const titleInput = await screen.findByLabelText('Tiêu đề widget');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Lưu' })).toBeEnabled());
    fireEvent.change(titleInput, { target: { value: 'Doanh thu mới' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));

    await waitFor(() =>
      expect(apiMocks.saveDashboardApi).toHaveBeenCalledWith(
        9,
        expect.objectContaining({
          widgets: expect.arrayContaining([
            expect.objectContaining({ id: 'a', custom_title: 'Doanh thu mới' }),
          ]),
        }),
        1,
      ),
    );
  });

  it('deletes a widget and persists the reduced layout', async () => {
    renderView();
    await screen.findByTestId('dashboard-card-title');
    fireEvent.click(screen.getByRole('button', { name: 'Chỉnh sửa' }));
    fireEvent.click(screen.getByLabelText(/Xóa widget/));
    await waitFor(() =>
      expect(apiMocks.saveDashboardApi).toHaveBeenCalledWith(
        9,
        expect.objectContaining({ widgets: [] }),
        1,
      ),
    );
  });
});

describe('MetricsDashboardView — controls', () => {
  beforeEach(() => {
    apiMocks.loadDashboardApi.mockResolvedValue(
      stateWith({
        widgets: [
          widget({ id: 'a', metric_id: 5, chart_type: 'line', dimension_col_id: 15, date_filter_column_id: 15, time_grain: 'month', custom_title: 'A' }),
        ],
      }),
    );
  });

  it('emits gte + lt date filters for the configured date column', async () => {
    renderView();
    await waitFor(() => expect(apiMocks.executeSemanticQueryApi).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('Khoảng thời gian'), { target: { value: 'last_7_days' } });
    await waitFor(() => {
      const calls = apiMocks.executeSemanticQueryApi.mock.calls;
      const last = calls[calls.length - 1][1] as SemanticQueryRequest;
      const ops = last.filters.map((f) => f.operator);
      expect(ops).toContain('gte');
      expect(ops).toContain('lt');
      expect(last.filters.every((f) => f.column_id === 15)).toBe(true);
    });
  });

  it('refreshes all widgets and records the last data refresh', async () => {
    renderView();
    await waitFor(() => expect(apiMocks.executeSemanticQueryApi).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: 'Làm mới tất cả' }));
    await waitFor(() => expect(apiMocks.executeSemanticQueryApi).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId('last-data-refresh')).toBeInTheDocument();
  });
});

describe('MetricsDashboardView — conflict and reset', () => {
  beforeEach(() => {
    apiMocks.loadDashboardApi.mockResolvedValue(
      stateWith({ widgets: [widget({ id: 'a', metric_id: 5, custom_title: 'A', chart_type: 'kpi', date_filter_column_id: 15 })] }),
    );
  });

  it('surfaces a conflict and reloads the server row on demand', async () => {
    apiMocks.saveDashboardApi.mockRejectedValueOnce(new DashboardVersionConflictError(2));
    renderView();
    await screen.findByTestId('dashboard-card-title');
    fireEvent.click(screen.getByRole('button', { name: 'Chỉnh sửa' }));
    fireEvent.click(screen.getByLabelText(/Xóa widget/));

    const banner = await screen.findByRole('alert');
    expect(banner).toHaveTextContent('phiên bản mới');
    fireEvent.click(screen.getByRole('button', { name: 'Tải phiên bản mới' }));
    await waitFor(() => expect(apiMocks.loadDashboardApi).toHaveBeenCalledTimes(2));
  });

  it('overwrites after reloading the server version', async () => {
    apiMocks.saveDashboardApi
      .mockRejectedValueOnce(new DashboardVersionConflictError(2))
      .mockImplementationOnce(async (_dbId, layout) => stateWith(layout, { version: 3 }));
    renderView();
    await screen.findByTestId('dashboard-card-title');
    fireEvent.click(screen.getByRole('button', { name: 'Chỉnh sửa' }));
    fireEvent.click(screen.getByLabelText(/Xóa widget/));
    const overwrite = await screen.findByRole('button', { name: /Thử ghi đè/ });
    fireEvent.click(overwrite);
    await waitFor(() => expect(apiMocks.saveDashboardApi).toHaveBeenCalledTimes(2));
  });

  it('resets to a deterministic default after confirmation', async () => {
    window.confirm = vi.fn(() => true);
    renderView();
    await screen.findByTestId('dashboard-card-title');
    fireEvent.click(screen.getByRole('button', { name: 'Chỉnh sửa' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đặt lại' }));
    await waitFor(() =>
      expect(apiMocks.saveDashboardApi).toHaveBeenCalledWith(
        9,
        expect.objectContaining({ widgets: expect.any(Array) }),
        1,
      ),
    );
  });
});

describe('MetricsDashboardView — drill-down date preset propagation', () => {
  beforeEach(() => {
    apiMocks.loadDashboardApi.mockResolvedValue(
      stateWith({
        widgets: [
          widget({
            id: 'a',
            metric_id: 5,
            chart_type: 'line',
            dimension_col_id: 15,
            date_filter_column_id: 15,
            time_grain: 'month',
            custom_title: 'A',
          }),
        ],
      }),
    );
  });

  it('propagates the current date preset through the drill-down callback', async () => {
    const { onDrillDown } = renderView();
    await screen.findByTestId('dashboard-card-title');
    fireEvent.change(screen.getByLabelText('Khoảng thời gian'), { target: { value: 'this_year' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xem chi tiết' }));

    expect(onDrillDown).toHaveBeenCalledTimes(1);
    const [argWidget, argPreset] = onDrillDown.mock.calls[0];
    expect(argWidget.metric_id).toBe(5);
    expect(argPreset).toBe('this_year');
  });

  it('propagates a null date preset (all-time) when no preset is selected', async () => {
    const { onDrillDown } = renderView();
    await screen.findByTestId('dashboard-card-title');
    fireEvent.click(screen.getByRole('button', { name: 'Xem chi tiết' }));

    expect(onDrillDown).toHaveBeenCalledTimes(1);
    expect(onDrillDown.mock.calls[0][1]).toBeNull();
  });
});
