import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  DashboardWidgetConfig,
  DashboardWidgetHeight,
} from '@/lib/dashboard';

import type { DashboardWidgetData } from './useDashboardWidgetData';
import { DashboardChart } from './DashboardChart';

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

function makeWidget(overrides: Partial<DashboardWidgetConfig>): DashboardWidgetConfig {
  return {
    id: 'w1',
    metric_id: 5,
    dimension_col_id: null,
    date_filter_column_id: null,
    time_grain: null,
    chart_type: 'kpi',
    width: 'third',
    height: 'normal' as DashboardWidgetHeight,
    custom_title: null,
    ...overrides,
  };
}

function makeData(overrides: Partial<DashboardWidgetData>): DashboardWidgetData {
  return {
    status: 'success',
    points: [],
    hiddenCount: 0,
    totalValue: null,
    trendPoints: [],
    errorMessage: null,
    isConfigurationError: false,
    retry: vi.fn(),
    ...overrides,
  };
}

const POINTS = [
  { label: 'Tháng 03/2024', rawLabel: '2024-03', value: 3, rawValue: 3 },
  { label: 'Tháng 01/2024', rawLabel: '2024-01', value: 1, rawValue: 1 },
  { label: 'Tháng 02/2024', rawLabel: '2024-02', value: 2, rawValue: 2 },
];

describe('DashboardChart states', () => {
  afterEach(cleanup);
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderChart(widget: DashboardWidgetConfig, data: DashboardWidgetData) {
    return render(
      <DashboardChart
        widget={widget}
        title="Doanh thu theo tháng"
        metricName="Doanh thu thuần"
        dimensionLabel="Ngày tạo đơn"
        data={data}
      />,
    );
  }

  it('renders an accessible loading skeleton without charts', () => {
    renderChart(makeWidget({}), makeData({ status: 'loading' }));

    expect(screen.getByRole('status')).toHaveTextContent('Đang tải');
    expect(recharts.LineChart).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Thử lại' })).not.toBeInTheDocument();
  });

  it('shows runtime errors with the original message and a Retry action', () => {
    const retry = vi.fn();
    renderChart(
      makeWidget({}),
      makeData({
        status: 'error',
        errorMessage: 'Query timeout after 15s',
        isConfigurationError: false,
        retry,
      }),
    );

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Không thể tải dữ liệu');
    expect(alert).toHaveTextContent('Query timeout after 15s');

    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it('labels persisted configuration problems distinctly', () => {
    renderChart(
      makeWidget({ chart_type: 'kpi' }),
      makeData({
        status: 'error',
        errorMessage: 'KPI widgets require date_filter_column_id',
        isConfigurationError: true,
      }),
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Cấu hình widget không hợp lệ');
  });

  it('explains when querying is unavailable for the source', () => {
    renderChart(makeWidget({}), makeData({ status: 'idle' }));

    expect(screen.getByText(/không khả dụng/i)).toBeInTheDocument();
    expect(recharts.BarChart).not.toHaveBeenCalled();
  });

  it('offers an empty state when the result has no rows', () => {
    renderChart(makeWidget({ chart_type: 'bar', dimension_col_id: 3 }), makeData({}));

    expect(screen.getByText(/Chưa có dữ liệu/i)).toBeInTheDocument();
    expect(recharts.BarChart).not.toHaveBeenCalled();
  });
});

describe('DashboardChart rendering', () => {
  afterEach(cleanup);
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderChart(widget: DashboardWidgetConfig, data: DashboardWidgetData) {
    return render(
      <DashboardChart
        widget={widget}
        title="Doanh thu theo tháng"
        metricName="Doanh thu thuần"
        dimensionLabel="Ngày tạo đơn"
        data={data}
      />,
    );
  }

  it('renders KPI totals plus a trend sparkline with accessible values', () => {
    renderChart(
      makeWidget({ chart_type: 'kpi', date_filter_column_id: 9 }),
      makeData({
        totalValue: 1250000,
        trendPoints: POINTS,
      }),
    );

    expect(screen.getByText('1.250.000')).toBeInTheDocument();
    expect(recharts.AreaChart).toHaveBeenCalledTimes(1);
    expect(recharts.AreaChart.mock.calls[0][0]).toMatchObject({ data: POINTS });
    expect(screen.getByRole('table', { hidden: true })).toHaveTextContent('Doanh thu theo tháng');
  });

  it('sorts line chart points by their time key before rendering', () => {
    renderChart(
      makeWidget({ chart_type: 'line', dimension_col_id: 9, time_grain: 'month' }),
      makeData({ points: POINTS }),
    );

    expect(recharts.LineChart).toHaveBeenCalledTimes(1);
    const props = recharts.LineChart.mock.calls[0][0] as { data: Array<{ rawLabel: string }> };
    expect(props.data.map((item) => item.rawLabel)).toEqual(['2024-01', '2024-02', '2024-03']);
    expect(recharts.ResponsiveContainer).toHaveBeenCalled();
  });

  it('truncates pie slices to the bounded budget with a remainder slice', () => {
    const many = Array.from({ length: 10 }, (_, index) => ({
      label: `p${index}`,
      rawLabel: `p${index}`,
      value: 10 - index,
      rawValue: 10 - index,
    }));
    renderChart(makeWidget({ chart_type: 'pie', dimension_col_id: 3 }), makeData({ points: many }));

    const props = recharts.Pie.mock.calls[0][0] as { data: Array<{ label: string; value: number }> };
    expect(props.data).toHaveLength(8);
    expect(props.data[props.data.length - 1]).toEqual({
      label: 'Khác',
      rawLabel: '',
      value: 6,
      rawValue: 6,
    });
  });

  it('renders the ranking table with header scope and overflow note', () => {
    renderChart(
      makeWidget({ chart_type: 'table', dimension_col_id: 3 }),
      makeData({
        points: [
          { label: 'Hà Nội', rawLabel: 'hni', value: 12, rawValue: 12 },
          { label: '(Trống)', rawLabel: '', value: 0, rawValue: null },
        ],
        hiddenCount: 2,
      }),
    );

    const table = screen.getByRole('table');
    expect(within(table).getByText('Ngày tạo đơn')).toBeInTheDocument();
    expect(within(table).getAllByRole('columnheader')).toHaveLength(3);
    expect(within(table).getByText('—')).toBeInTheDocument();
    expect(screen.getByText(/\+2 mục khác/)).toBeInTheDocument();
  });

  it('keeps a visually hidden textual fallback for categorical charts', () => {
    const { container } = renderChart(
      makeWidget({ chart_type: 'bar', dimension_col_id: 3 }),
      makeData({ points: POINTS }),
    );

    const fallback = container.querySelector('table.sr-only');
    expect(fallback).not.toBeNull();
    expect(fallback).toHaveTextContent('Doanh thu theo tháng');
    expect(fallback).toHaveTextContent('Tháng 01/2024');
  });
});
