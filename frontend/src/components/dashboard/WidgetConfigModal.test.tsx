import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MetricRecord, SemanticQueryRequest } from '@/lib/api';
import { DashboardWidgetConfig } from '@/lib/dashboard';

import { WidgetConfigModal, WidgetConfigModalProps } from './WidgetConfigModal';

const apiMocks = vi.hoisted(() => ({
  getMetricRecommendedDimensionsApi: vi.fn(),
  getMetricFilterColumnsApi: vi.fn(),
  executeSemanticQueryApi: vi.fn(),
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    getMetricRecommendedDimensionsApi: apiMocks.getMetricRecommendedDimensionsApi,
    getMetricFilterColumnsApi: apiMocks.getMetricFilterColumnsApi,
    executeSemanticQueryApi: apiMocks.executeSemanticQueryApi,
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

function makeMetric(overrides: Partial<MetricRecord>): MetricRecord {
  return {
    metric_id: 5,
    name: 'Doanh thu thuần',
    source: 'ai',
    status: 'approved',
    created_at: '2026-01-01T00:00:00Z',
    definition: {
      schema_version: 2,
      metric: {
        name: 'Doanh thu thuần',
        formula: { function: 'SUM', expression: 'amount' },
        base_entity: 'orders',
        filters: [],
        status: 'approved',
        excluded_notes: '',
      },
      diagnostics: [],
    },
    ...overrides,
  };
}

const APPROVED_METRIC = makeMetric({});
const PENDING_METRIC = makeMetric({ metric_id: 6, name: 'Metric chờ duyệt', status: 'pending_approval' });
const LEGACY_METRIC = makeMetric({
  metric_id: 7,
  name: 'Metric legacy',
  definition: { schema_version: 1, metric: APPROVED_METRIC.definition!.metric, diagnostics: [] },
});
const DIAGNOSTIC_METRIC = makeMetric({
  metric_id: 8,
  name: 'Metric lỗi grain',
  definition: {
    ...APPROVED_METRIC.definition!,
    diagnostics: [{ code: 'grain_mismatch', message: 'Grain không khớp' }],
  },
});

const DIMENSIONS_RESPONSE = {
  metric_id: 5,
  metric_name: 'Doanh thu thuần',
  base_table: 'orders',
  dimensions: [
    {
      column_id: 31,
      column_name: 'customer_name',
      business_name: 'Tên khách hàng',
      table_id: 2,
      table_name: 'customers',
      table_business_name: 'Khách hàng',
      tier: 'A' as const,
      tier_label: 'Trực tiếp',
      is_safe_join: true,
      requires_reaggregation: false,
      data_type: 'VARCHAR',
      cardinality_hint: 3,
    },
    {
      column_id: 32,
      column_name: 'order_code',
      business_name: 'Mã đơn hàng',
      table_id: 1,
      table_name: 'orders',
      table_business_name: 'Đơn hàng',
      tier: 'A' as const,
      tier_label: 'Trực tiếp',
      is_safe_join: true,
      requires_reaggregation: false,
      data_type: 'VARCHAR',
      cardinality_hint: null,
    },
  ],
};

const FILTER_COLUMNS_RESPONSE = {
  metric_id: 5,
  metric_name: 'Doanh thu thuần',
  base_table: 'orders',
  columns: [
    {
      column_id: 15,
      column_name: 'created_at',
      business_name: 'Ngày tạo đơn',
      table_id: 1,
      table_name: 'orders',
      table_business_name: 'Đơn hàng',
      group_type: 'base' as const,
      data_type: 'TIMESTAMP',
      is_time_dimension: true,
    },
    {
      column_id: 20,
      column_name: 'channel',
      business_name: 'Kênh bán',
      table_id: 1,
      table_name: 'orders',
      table_business_name: 'Đơn hàng',
      group_type: 'base' as const,
      data_type: 'VARCHAR',
      is_time_dimension: false,
    },
  ],
};

const QUERY_RESULT = {
  sql: 'SELECT ...',
  parameters: {},
  columns: ['dimension_31', 'metric_5'],
  rows: [['Giao lưu', 10]],
  row_count: 1,
};

function renderModal(overrides: Partial<WidgetConfigModalProps> = {}) {
  const props: WidgetConfigModalProps = {
    open: true,
    dbId: 9,
    querySupported: true,
    metrics: [APPROVED_METRIC, PENDING_METRIC, LEGACY_METRIC, DIAGNOSTIC_METRIC],
    editingWidget: null,
    onSave: vi.fn(),
    onCancel: vi.fn(),
    ...overrides,
  };
  const utils = render(<WidgetConfigModal {...props} />);
  return { ...utils, onSave: props.onSave as ReturnType<typeof vi.fn>, onCancel: props.onCancel as ReturnType<typeof vi.fn> };
}

function selectByLabel(label: string): HTMLSelectElement {
  return screen.getByLabelText(label) as HTMLSelectElement;
}

function choose(label: string, value: string): void {
  fireEvent.change(selectByLabel(label), { target: { value } });
}

async function loadMetaForApprovedMetric(): Promise<void> {
  choose('Metric', '5');
  const dateSelect = await screen.findByLabelText('Cột lọc ngày');
  await waitFor(() =>
    expect(within(dateSelect).getByRole('option', { name: 'Ngày tạo đơn' })).toBeInTheDocument(),
  );
}

async function pickMetricAndBuildBarForm(): Promise<void> {
  await loadMetaForApprovedMetric();
  choose('Loại biểu đồ', 'bar');
  choose('Chiều dữ liệu', '31');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Lưu' })).toBeEnabled());
}

describe('WidgetConfigModal', () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getMetricRecommendedDimensionsApi.mockResolvedValue(DIMENSIONS_RESPONSE);
    apiMocks.getMetricFilterColumnsApi.mockResolvedValue(FILTER_COLUMNS_RESPONSE);
    apiMocks.executeSemanticQueryApi.mockResolvedValue(QUERY_RESULT);
  });

  it('lists only approved canonical-v2 metrics and searches them by name', async () => {
    renderModal();

    const metricSelect = selectByLabel('Metric');
    const optionNames = within(metricSelect)
      .getAllByRole('option')
      .map((option) => option.textContent);
    expect(optionNames).toEqual(['Doanh thu thuần']);
    expect(screen.queryByText('Metric chờ duyệt')).not.toBeInTheDocument();
    expect(screen.queryByText('Metric legacy')).not.toBeInTheDocument();
    expect(screen.queryByText('Metric lỗi grain')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Tìm metric'), { target: { value: 'zzz-không-có' } });
    expect(within(metricSelect).queryAllByRole('option')).toHaveLength(0);
    expect(screen.getByText('Không có metric đã duyệt nào.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Tìm metric'), { target: { value: 'doanh' } });
    expect(within(metricSelect).getByRole('option', { name: 'Doanh thu thuần' })).toBeInTheDocument();
  });

  it('loads recommended dimensions and time filter columns after a metric is chosen', async () => {
    renderModal();

    await loadMetaForApprovedMetric();
    expect(apiMocks.getMetricRecommendedDimensionsApi).toHaveBeenCalledWith(9, 5);
    expect(apiMocks.getMetricFilterColumnsApi).toHaveBeenCalledWith(9, 5);

    choose('Loại biểu đồ', 'bar');

    const dimensionSelect = selectByLabel('Chiều dữ liệu');
    await waitFor(() =>
      expect(within(dimensionSelect).getByRole('option', { name: 'Tên khách hàng' })).toBeInTheDocument(),
    );

    const dateSelect = selectByLabel('Cột lọc ngày');
    const dateOptions = within(dateSelect)
      .getAllByRole('option')
      .map((option) => option.textContent);
    expect(dateOptions).toEqual(['Không áp dụng', 'Ngày tạo đơn']);
    expect(dateOptions.join(' ')).not.toContain('Kênh bán');
  });

  it('adapts dimension options to chart compatibility and resets stale selections', async () => {
    renderModal();

    await loadMetaForApprovedMetric();

    choose('Loại biểu đồ', 'bar');
    let dimensionSelect = selectByLabel('Chiều dữ liệu');
    let dimensionNames = within(dimensionSelect)
      .getAllByRole('option')
      .map((option) => option.textContent);
    expect(dimensionNames).toContain('Tên khách hàng');
    expect(dimensionNames).not.toContain('Ngày tạo đơn');
    choose('Chiều dữ liệu', '31');

    choose('Loại biểu đồ', 'line');
    dimensionSelect = selectByLabel('Cột thời gian');
    dimensionNames = within(dimensionSelect)
      .getAllByRole('option')
      .map((option) => option.textContent);
    expect(dimensionNames).toEqual(['— Chọn —', 'Ngày tạo đơn']);
    expect(dimensionSelect.value).toBe('');

    choose('Loại biểu đồ', 'kpi');
    expect(screen.queryByLabelText('Chiều dữ liệu')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Cột thời gian')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Mốc thời gian')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Cột lọc ngày')).toBeInTheDocument();

    choose('Loại biểu đồ', 'bar');
    dimensionSelect = selectByLabel('Chiều dữ liệu');
    expect(dimensionSelect.value).toBe('');
  });

  it('shows a deterministic chart recommendation badge for the chosen dimension', async () => {
    renderModal();

    await loadMetaForApprovedMetric();
    choose('Loại biểu đồ', 'bar');

    choose('Chiều dữ liệu', '31');
    expect(screen.getByText('Đề xuất: Biểu đồ tròn')).toBeInTheDocument();

    choose('Chiều dữ liệu', '32');
    expect(screen.getByText('Đề xuất: Biểu đồ cột')).toBeInTheDocument();
  });

  it('lets categorical widgets opt out of date filtering and keeps dimension separate from the date column', async () => {
    const { onSave } = renderModal();

    await loadMetaForApprovedMetric();
    choose('Loại biểu đồ', 'bar');
    choose('Chiều dữ liệu', '31');
    choose('Cột lọc ngày', '');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Lưu' })).toBeEnabled());

    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave.mock.calls[0][0]).toMatchObject({
      metric_id: 5,
      chart_type: 'bar',
      dimension_col_id: 31,
      date_filter_column_id: null,
    });

    cleanup();
    apiMocks.executeSemanticQueryApi.mockClear();
    const secondSave = renderModal().onSave;
    await loadMetaForApprovedMetric();
    choose('Loại biểu đồ', 'bar');
    choose('Chiều dữ liệu', '31');
    choose('Cột lọc ngày', '15');
    fireEvent.click(await screen.findByRole('button', { name: 'Lưu' }));
    await waitFor(() => expect(secondSave).toHaveBeenCalledTimes(1));
    expect(secondSave.mock.calls[0][0]).toMatchObject({
      dimension_col_id: 31,
      date_filter_column_id: 15,
      time_grain: null,
    });
  });

  it('requires a time column before a KPI widget can be saved', async () => {
    const { onSave } = renderModal();

    await loadMetaForApprovedMetric();
    choose('Loại biểu đồ', 'kpi');

    const saveButton = screen.getByRole('button', { name: 'Lưu' });
    expect(saveButton).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('KPI cần một cột thời gian để lọc theo ngày.');
    fireEvent.click(saveButton);
    expect(onSave).not.toHaveBeenCalled();

    choose('Cột lọc ngày', '15');
    expect(saveButton).toBeEnabled();
    fireEvent.click(saveButton);
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave.mock.calls[0][0]).toMatchObject({
      chart_type: 'kpi',
      dimension_col_id: null,
      time_grain: null,
      date_filter_column_id: 15,
    });
  });

  it('persists width, height, and trimmed custom title', async () => {
    const { onSave } = renderModal();

    await pickMetricAndBuildBarForm();
    choose('Độ rộng', 'half');
    choose('Chiều cao', 'expanded');
    fireEvent.change(screen.getByLabelText('Tiêu đề widget'), { target: { value: '  Tổng quan doanh số  ' } });

    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave.mock.calls[0][0]).toMatchObject({
      width: 'half',
      height: 'expanded',
      custom_title: 'Tổng quan doanh số',
    });
  });

  it('runs the bounded preview only on the explicit preview action', async () => {
    renderModal();

    await pickMetricAndBuildBarForm();
    expect(apiMocks.executeSemanticQueryApi).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Xem trước' }));
    await waitFor(() => expect(apiMocks.executeSemanticQueryApi).toHaveBeenCalledTimes(1));

    const request = apiMocks.executeSemanticQueryApi.mock.calls[0][1] as SemanticQueryRequest;
    expect(request).toEqual({
      metric_ids: [5],
      dimensions: [{ column_id: 31 }],
      filters: [],
      limit: 100,
    });
    expect(apiMocks.executeSemanticQueryApi).toHaveBeenCalledWith('9', request);

    fireEvent.change(screen.getByLabelText('Tiêu đề widget'), { target: { value: 'đổi tiêu đề' } });
    await waitFor(() => expect(screen.getByLabelText('Tiêu đề widget')).toHaveValue('đổi tiêu đề'));
    expect(apiMocks.executeSemanticQueryApi).toHaveBeenCalledTimes(1);
  });

  it('never queries and explains the limitation for SQL Dump sources', async () => {
    renderModal({ querySupported: false });

    await pickMetricAndBuildBarForm();

    const previewButton = screen.getByRole('button', { name: 'Xem trước' });
    expect(previewButton).toBeDisabled();
    const note = screen.getByRole('note');
    expect(note).toHaveTextContent('SQL Dump');
    expect(note).toHaveTextContent('không hỗ trợ truy vấn');

    fireEvent.click(previewButton);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Lưu' })).toBeEnabled());
    expect(apiMocks.executeSemanticQueryApi).not.toHaveBeenCalled();
  });

  it('preserves the stable widget id when editing and mints a fresh id when creating', async () => {
    const editingWidget: DashboardWidgetConfig = {
      id: 'w-fixed-id',
      metric_id: 5,
      dimension_col_id: 31,
      date_filter_column_id: 15,
      time_grain: null,
      chart_type: 'bar',
      width: 'half',
      height: 'normal',
      custom_title: 'Doanh số theo khách',
    };
    const first = renderModal({ editingWidget });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Lưu' })).toBeEnabled());
    expect(selectByLabel('Metric').value).toBe('5');
    expect(selectByLabel('Chiều dữ liệu').value).toBe('31');
    expect(selectByLabel('Cột lọc ngày').value).toBe('15');

    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));
    await waitFor(() => expect(first.onSave).toHaveBeenCalledTimes(1));
    expect((first.onSave.mock.calls[0][0] as DashboardWidgetConfig).id).toBe('w-fixed-id');

    cleanup();
    const second = renderModal();
    await pickMetricAndBuildBarForm();
    fireEvent.click(screen.getByRole('button', { name: 'Lưu' }));
    await waitFor(() => expect(second.onSave).toHaveBeenCalledTimes(1));
    const createdId = (second.onSave.mock.calls[0][0] as DashboardWidgetConfig).id;
    expect(typeof createdId).toBe('string');
    expect(createdId.length).toBeGreaterThan(0);
    expect(createdId).not.toBe('w-fixed-id');
  });

  it('cancels without saving', async () => {
    const { onCancel, onSave } = renderModal();

    fireEvent.click(screen.getByRole('button', { name: 'Hủy' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onSave).not.toHaveBeenCalled();
  });

  it('blocks saving an incomplete configuration', async () => {
    const { onSave } = renderModal();

    const saveButton = screen.getByRole('button', { name: 'Lưu' });
    expect(saveButton).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Hãy chọn một metric đã duyệt.');

    fireEvent.click(saveButton);
    expect(onSave).not.toHaveBeenCalled();
  });
});
