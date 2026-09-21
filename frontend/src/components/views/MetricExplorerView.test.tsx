import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MetricExplorerView } from '@/components/views/MetricExplorerView';
import * as apiModule from '@/lib/api';
import { MetricRecord, SemanticCatalog } from '@/lib/api';

describe('MetricExplorerView', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    vi.spyOn(apiModule, 'getMetricRecommendedDimensionsApi').mockResolvedValue({
      metric_id: 1,
      metric_name: 'Doanh thu thuần',
      base_table: 'orders',
      dimensions: [
        {
          column_id: 102,
          column_name: 'status',
          business_name: 'Trạng thái đơn',
          table_id: 10,
          table_name: 'orders',
          table_business_name: 'Đơn hàng',
          tier: 'A',
          tier_label: 'Trực tiếp',
          is_safe_join: true,
          requires_reaggregation: false,
          data_type: 'VARCHAR',
        },
        {
          column_id: 201,
          column_name: 'city',
          business_name: 'Tỉnh / Thành phố',
          table_id: 20,
          table_name: 'customers',
          table_business_name: 'Khách hàng',
          tier: 'B',
          tier_label: 'Liên kết trực tiếp (N:1)',
          is_safe_join: true,
          requires_reaggregation: false,
          data_type: 'VARCHAR',
        },
      ],
    });
    vi.spyOn(apiModule, 'getMetricJoinPathOptionsApi').mockResolvedValue({});
  });


  it('blocks query execution for SQL Dump sources', () => {
    render(
      <MetricExplorerView
        dbId={3}
        metrics={[]}
        catalog={{ db_id: 3, source_type: 'sql_dump', query_supported: false, tables: [], relationships: [] }}
        theme="light"
      />
    );
    expect(screen.getByText(/SQL Dump chỉ chứa metadata DDL/)).toBeInTheDocument();
    expect(screen.queryByText('Preview SQL')).not.toBeInTheDocument();
  });

  it('renders prompt when no metric is selected, and reveals relevant scoped dimensions upon selecting a metric', async () => {
    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            dimensions: ['status', 'city'],
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 101,
              column_name: 'created_at',
              business_name: 'Ngày tạo đơn',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
              allowed_values: null,
            },
            {
              column_id: 102,
              column_name: 'status',
              business_name: 'Trạng thái đơn',
              data_type: 'VARCHAR',
              is_time_dimension: false,
              allowed_values: null,
            },
          ],
        },
        {
          table_id: 20,
          table_name: 'customers',
          business_name: 'Khách hàng',
          columns: [
            {
              column_id: 201,
              column_name: 'city',
              business_name: 'Tỉnh / Thành phố',
              data_type: 'VARCHAR',
              is_time_dimension: false,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [
        {
          from_entity_id: 10,
          to_entity_id: 20,
        },
      ],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="light"
      />
    );

    // Verify initial empty guidance prompt
    expect(screen.getByText(/Chọn một chỉ số ở mục 1/)).toBeInTheDocument();

    // Select metric
    const metricCheckbox = screen.getByRole('checkbox', { name: /Doanh thu thuần/i });
    fireEvent.click(metricCheckbox);

    // Scoped dimensions from backend appear
    await waitFor(() => {
      expect(screen.getAllByText('Trạng thái đơn').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Tỉnh / Thành phố').length).toBeGreaterThan(0);
    });
  });

  it('renders reference Explorer layout with tabs, Compile Preview, Execute, and guardrail badge', async () => {
    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 101,
              column_name: 'created_at',
              business_name: 'Ngày tạo đơn',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
              allowed_values: null,
            },
            {
              column_id: 102,
              column_name: 'status',
              business_name: 'Trạng thái đơn',
              data_type: 'VARCHAR',
              is_time_dimension: false,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="dark"
      />
    );

    // Tabs
    expect(screen.getByText('Bảng số liệu')).toBeInTheDocument();
    expect(screen.getByText('Biểu đồ')).toBeInTheDocument();
    expect(screen.getByText('SQL Code')).toBeInTheDocument();

    // Guardrail info
    expect(screen.getByText(/Read-only · LIMIT 100 · max 1000 · 15s timeout/)).toBeInTheDocument();

    // Buttons
    expect(screen.getByRole('button', { name: /Preview SQL/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Thực thi/i })).toBeInTheDocument();
  });

  it('selects time granularity and toggles time dimension correctly', () => {
    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 101,
              column_name: 'created_at',
              business_name: 'Ngày tạo đơn',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={[]}
        catalog={mockCatalog}
        theme="light"
      />
    );

    // 5 grain buttons exist
    expect(screen.getByText('Ngày')).toBeInTheDocument();
    expect(screen.getByText('Tháng')).toBeInTheDocument();
    expect(screen.getByText('Quý')).toBeInTheDocument();
    expect(screen.getByText('Năm')).toBeInTheDocument();

    // Click Tháng button
    const monthButton = screen.getByText('Tháng');
    fireEvent.click(monthButton);
  });

  it('automatically applies metric-defined dimensions upon selection', async () => {
    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            dimensions: ['status'],
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 102,
              column_name: 'status',
              business_name: 'Trạng thái đơn',
              data_type: 'VARCHAR',
              is_time_dimension: false,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="light"
      />
    );

    // Select metric first
    const metricCheckbox = screen.getByRole('checkbox', { name: /Doanh thu thuần/i });
    fireEvent.click(metricCheckbox);

    await waitFor(() => {
      expect(screen.getAllByText('Trạng thái đơn').length).toBeGreaterThan(0);
    });
  });

  it('renders interactive chart studio with Bar, Line, Area, and Pie chart types without errors', async () => {
    vi.spyOn(apiModule, 'executeSemanticQueryApi').mockResolvedValue({
      sql: 'SELECT status, SUM(price) FROM orders GROUP BY status',
      parameters: {},
      columns: ['status', 'total_price'],
      rows: [
        ['Hoàn thành', 1500000],
        ['Đang giao', 800000],
        ['Đã hủy', 200000],
      ],
      row_count: 3,
      execution_time_ms: 12,
    });

    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 102,
              column_name: 'status',
              business_name: 'Trạng thái đơn',
              data_type: 'VARCHAR',
              is_time_dimension: false,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="light"
      />
    );

    // Select metric and execute
    const metricCheckbox = screen.getByRole('checkbox', { name: /Doanh thu thuần/i });
    fireEvent.click(metricCheckbox);

    const execButton = screen.getByRole('button', { name: /Thực thi/i });
    fireEvent.click(execButton);

    // Wait for execution result
    await waitFor(() => {
      expect(screen.getByText('Hoàn thành')).toBeInTheDocument();
    });

    // Switch to chart tab
    const chartTabBtn = screen.getByRole('button', { name: /Biểu đồ/i });
    fireEvent.click(chartTabBtn);

    // Verify KPI summary cards and chart types
    expect(screen.getByText(/Biểu đồ trực quan/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cột/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Đường/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Vùng/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Biểu đồ Tròn/i })).toBeInTheDocument();

    // Click Pie Chart button
    const pieBtn = screen.getByRole('button', { name: /Biểu đồ Tròn/i });
    fireEvent.click(pieBtn);
  });

  it('filters metric list in Section 1 by metric search query and clears search', () => {
    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
      {
        metric_id: 2,
        name: 'Số lượng khách hàng',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Số lượng khách hàng',
            base_entity: 'customers',
            base_entity_id: 20,
            grain: { column_ids: [201] },
            formula: { function: 'COUNT', expression: 'id' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="light"
      />
    );

    // Both metrics initially visible
    expect(screen.getByText('Doanh thu thuần')).toBeInTheDocument();
    expect(screen.getByText('Số lượng khách hàng')).toBeInTheDocument();

    // Type in metric search
    const searchInput = screen.getByPlaceholderText(/Tìm nhanh chỉ số/i);
    fireEvent.change(searchInput, { target: { value: 'khách hàng' } });

    // Only matching metric is displayed
    expect(screen.getByText('Số lượng khách hàng')).toBeInTheDocument();
    expect(screen.queryByText('Doanh thu thuần')).not.toBeInTheDocument();

    // Type non-matching search
    fireEvent.change(searchInput, { target: { value: 'không tồn tại' } });
    expect(screen.getByText(/Không tìm thấy metric nào khớp/)).toBeInTheDocument();

    // Clear search
    fireEvent.change(searchInput, { target: { value: '' } });
    expect(screen.getByText('Doanh thu thuần')).toBeInTheDocument();
    expect(screen.getByText('Số lượng khách hàng')).toBeInTheDocument();
  });

  it('applies dashboard drill-down selection (metric, dimension, grain, date range) to the execution request', async () => {
    const executeSpy = vi
      .spyOn(apiModule, 'executeSemanticQueryApi')
      .mockResolvedValue({
        sql: 'SELECT status, SUM(price) FROM orders GROUP BY status',
        parameters: {},
        columns: ['status', 'total_price'],
        rows: [
          ['Hoàn thành', 1500000],
          ['Đang giao', 800000],
        ],
        row_count: 2,
        execution_time_ms: 12,
      });

    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 101,
              column_name: 'created_at',
              business_name: 'Ngày tạo đơn',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
              allowed_values: null,
            },
            {
              column_id: 102,
              column_name: 'status',
              business_name: 'Trạng thái đơn',
              data_type: 'VARCHAR',
              is_time_dimension: false,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="light"
        initialSelection={{
          metricId: 1,
          dimensionColId: 102,
          timeGrain: 'month',
          dateFilters: [
            { column_id: 101, operator: 'gte', value: '2026-01-01' },
            { column_id: 101, operator: 'lt', value: '2026-02-01' },
          ],
          requestKey: 1,
        }}
      />,
    );

    // Metric auto-selected from the drill-down
    const metricCheckbox = await screen.findByRole('checkbox', { name: /Doanh thu thuần/i });
    expect(metricCheckbox).toBeChecked();

    // Removable dashboard filter chip is shown
    expect(screen.getByText(/Bộ lọc từ Dashboard/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Thực thi/i }));

    await waitFor(() => {
      expect(executeSpy).toHaveBeenCalledTimes(1);
      const req = executeSpy.mock.calls[0][1] as apiModule.SemanticQueryRequest;
      expect(req.metric_ids).toEqual([1]);
      expect(req.dimensions).toEqual(
        expect.arrayContaining([
          { column_id: 102, time_grain: undefined },
          { column_id: 101, time_grain: 'month' },
        ]),
      );
      expect(req.filters).toEqual([
        { column_id: 101, operator: 'gte', value: '2026-01-01' },
        { column_id: 101, operator: 'lt', value: '2026-02-01' },
      ]);
    });

    // Removing the dashboard filter clears the date range
    fireEvent.click(screen.getByLabelText('Xóa bộ lọc từ Dashboard'));
    fireEvent.click(screen.getByRole('button', { name: /Thực thi/i }));

    await waitFor(() => {
      const req = executeSpy.mock.calls[1][1] as apiModule.SemanticQueryRequest;
      expect(req.filters).toEqual([]);
    });
    expect(screen.queryByText(/Bộ lọc từ Dashboard/i)).not.toBeInTheDocument();
  });

  it('emits a single time-dimension entry with grain when the dimension is the time column', async () => {
    const executeSpy = vi
      .spyOn(apiModule, 'executeSemanticQueryApi')
      .mockResolvedValue({
        sql: 'SELECT created_at, SUM(price) FROM orders GROUP BY created_at',
        parameters: {},
        columns: ['created_at', 'total_price'],
        rows: [
          ['2026-01', 1500000],
          ['2026-02', 800000],
        ],
        row_count: 2,
        execution_time_ms: 12,
      });

    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 101,
              column_name: 'created_at',
              business_name: 'Ngày tạo đơn',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
              allowed_values: null,
            },
            {
              column_id: 102,
              column_name: 'status',
              business_name: 'Trạng thái đơn',
              data_type: 'VARCHAR',
              is_time_dimension: false,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="light"
        initialSelection={{
          metricId: 1,
          dimensionColId: 101,
          timeGrain: 'month',
          dateFilters: [],
          requestKey: 1,
        }}
      />,
    );

    const metricCheckbox = await screen.findByRole('checkbox', { name: /Doanh thu thuần/i });
    expect(metricCheckbox).toBeChecked();

    fireEvent.click(screen.getByRole('button', { name: /Thực thi/i }));

    await waitFor(() => {
      expect(executeSpy).toHaveBeenCalledTimes(1);
      const req = executeSpy.mock.calls[0][1] as apiModule.SemanticQueryRequest;
      expect(req.dimensions).toEqual([{ column_id: 101, time_grain: 'month' }]);
    });
  });

  it('ignores dashboard drill-down selection for SQL Dump sources', () => {
    render(
      <MetricExplorerView
        dbId={3}
        metrics={[]}
        catalog={{
          db_id: 3,
          source_type: 'sql_dump',
          query_supported: false,
          tables: [],
          relationships: [],
        }}
        theme="light"
        initialSelection={{
          metricId: 1,
          dimensionColId: 102,
          timeGrain: 'month',
          dateFilters: [{ column_id: 101, operator: 'gte', value: '2026-01-01' }],
          requestKey: 1,
        }}
      />,
    );

    expect(screen.getByText(/SQL Dump chỉ chứa metadata DDL/)).toBeInTheDocument();
    expect(screen.queryByText('Preview SQL')).not.toBeInTheDocument();
    expect(screen.queryByText(/Bộ lọc từ Dashboard/i)).not.toBeInTheDocument();
  });

  it('applies the time grain from a dashboard drill-down to the time dimension control', async () => {
    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 101,
              column_name: 'created_at',
              business_name: 'Ngày tạo đơn',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="light"
        initialSelection={{
          metricId: 1,
          dimensionColId: null,
          timeGrain: 'quarter',
          dateFilters: [],
          requestKey: 1,
        }}
      />,
    );

    const metricCheckbox = await screen.findByRole('checkbox', { name: /Doanh thu thuần/i });
    expect(metricCheckbox).toBeChecked();

    const quarterButton = screen.getByRole('button', { name: /Quý/ });
    expect(quarterButton).toHaveClass('bg-primary');
  });

  it('renders an interactive chart after a dashboard drill-down execute', async () => {
    vi.spyOn(apiModule, 'executeSemanticQueryApi').mockResolvedValue({
      sql: 'SELECT status, SUM(price) FROM orders GROUP BY status',
      parameters: {},
      columns: ['status', 'total_price'],
      rows: [
        ['Hoàn thành', 1500000],
        ['Đang giao', 800000],
        ['Đã hủy', 200000],
      ],
      row_count: 3,
      execution_time_ms: 12,
    });

    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        name: 'Doanh thu thuần',
        source: 'ai',
        version: 1,
        status: 'approved',
        created_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu thuần',
            base_entity: 'orders',
            base_entity_id: 10,
            grain: { column_ids: [101] },
            formula: { function: 'SUM', expression: 'price' },
            filters: [],
            status: 'approved',
            confidence: 'high',
            excluded_notes: '',
          },
        },
      },
    ];

    const mockCatalog: SemanticCatalog = {
      db_id: 3,
      source_type: 'live',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 102,
              column_name: 'status',
              business_name: 'Trạng thái đơn',
              data_type: 'VARCHAR',
              is_time_dimension: false,
              allowed_values: null,
            },
          ],
        },
      ],
      relationships: [],
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={mockMetrics}
        catalog={mockCatalog}
        theme="light"
        initialSelection={{
          metricId: 1,
          dimensionColId: 102,
          timeGrain: null,
          dateFilters: [],
          requestKey: 1,
        }}
      />,
    );

    const metricCheckbox = await screen.findByRole('checkbox', { name: /Doanh thu thuần/i });
    expect(metricCheckbox).toBeChecked();

    fireEvent.click(screen.getByRole('button', { name: /Thực thi/i }));

    await waitFor(() => {
      expect(screen.getByText('Hoàn thành')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Biểu đồ/i }));

    expect(screen.getByText(/Biểu đồ trực quan/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cột/i })).toBeInTheDocument();
  });

  function buildMetric(preferredJoinPaths: Record<string, number[]> | undefined) {
    return {
      metric_id: 1,
      name: 'Doanh thu thuần',
      source: 'ai' as const,
      version: 1,
      status: 'approved' as const,
      created_at: '2026-01-01',
      definition: {
        schema_version: 2 as const,
        metric: {
          name: 'Doanh thu thuần',
          base_entity: 'orders',
          base_entity_id: 10,
          grain: { column_ids: [101] },
          formula: { function: 'SUM' as const, expression: 'price' },
          filters: [],
          status: 'approved' as const,
          confidence: 'high' as const,
          excluded_notes: '',
          preferred_join_paths: preferredJoinPaths,
        },
      },
    };
  }

  const explorerCatalog = {
    db_id: 3,
    source_type: 'live' as const,
    query_supported: true,
    tables: [
      {
        table_id: 10,
        table_name: 'orders',
        business_name: 'Đơn hàng',
        columns: [
          {
            column_id: 101,
            column_name: 'created_at',
            business_name: 'Ngày tạo đơn',
            data_type: 'TIMESTAMP',
            is_time_dimension: true,
            allowed_values: null,
          },
          {
            column_id: 102,
            column_name: 'status',
            business_name: 'Trạng thái đơn',
            data_type: 'VARCHAR',
            is_time_dimension: false,
            allowed_values: null,
          },
        ],
      },
      {
        table_id: 20,
        table_name: 'customers',
        business_name: 'Khách hàng',
        columns: [
          {
            column_id: 201,
            column_name: 'city',
            business_name: 'Tỉnh / Thành phố',
            data_type: 'VARCHAR',
            is_time_dimension: false,
            allowed_values: null,
          },
        ],
      },
    ],
    relationships: [],
  };

  it('automatically displays metric-defined dimensions and attaches them to query', async () => {
    const executeSpy = vi.spyOn(apiModule, 'executeSemanticQueryApi').mockResolvedValue({
      sql: 'SELECT city, SUM(price) FROM orders GROUP BY city',
      parameters: {},
      columns: ['city', 'total_price'],
      rows: [['Hà Nội', 1000000]],
      row_count: 1,
      execution_time_ms: 10,
    });

    const metricWithDims: MetricRecord = {
      metric_id: 1,
      name: 'Doanh thu thuần',
      source: 'ai',
      version: 1,
      status: 'approved',
      created_at: '2026-01-01',
      definition: {
        schema_version: 2,
        metric: {
          name: 'Doanh thu thuần',
          base_entity: 'orders',
          base_entity_id: 10,
          grain: { column_ids: [101] },
          dimensions: ['city'],
          formula: { function: 'SUM', expression: 'price' },
          filters: [],
          status: 'approved',
          confidence: 'high',
          excluded_notes: '',
        },
      },
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={[metricWithDims]}
        catalog={explorerCatalog}
        theme="light"
      />,
    );

    const metricCheckbox = await screen.findByRole('checkbox', { name: /Doanh thu thuần/i });
    fireEvent.click(metricCheckbox);

    await waitFor(() => {
      expect(screen.getAllByText('Tỉnh / Thành phố').length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole('button', { name: /Thực thi/i }));
    await waitFor(() => {
      expect(executeSpy).toHaveBeenCalledTimes(1);
      const req = executeSpy.mock.calls[0][1] as apiModule.SemanticQueryRequest;
      expect(req.dimensions).toEqual(expect.arrayContaining([{ column_id: 201, time_grain: undefined }]));
    });
  });

  it('maps foreign key dimension (store_id) to entity descriptive dimension (store.name)', async () => {
    vi.spyOn(apiModule, 'getMetricRecommendedDimensionsApi').mockResolvedValue({
      metric_id: 1,
      metric_name: 'Doanh thu thuần',
      base_table: 'orders',
      dimensions: [
        {
          column_id: 301,
          column_name: 'name',
          business_name: 'Tên cửa hàng',
          table_id: 30,
          table_name: 'store',
          table_business_name: 'Cửa hàng',
          tier: 'B',
          tier_label: 'Liên kết trực tiếp (N:1)',
          is_safe_join: true,
          requires_reaggregation: false,
          data_type: 'VARCHAR',
        },
      ],
    });

    const metricWithFkDim: MetricRecord = {
      metric_id: 1,
      name: 'Doanh thu thuần',
      source: 'ai',
      version: 1,
      status: 'approved',
      created_at: '2026-01-01',
      definition: {
        schema_version: 2,
        metric: {
          name: 'Doanh thu thuần',
          base_entity: 'orders',
          base_entity_id: 10,
          grain: { column_ids: [101] },
          dimensions: ['store_id'],
          formula: { function: 'SUM', expression: 'price' },
          filters: [],
          status: 'approved',
          confidence: 'high',
          excluded_notes: '',
        },
      },
    };

    render(
      <MetricExplorerView
        dbId={3}
        metrics={[metricWithFkDim]}
        catalog={explorerCatalog}
        theme="light"
      />,
    );

    const metricCheckbox = await screen.findByRole('checkbox', { name: /Doanh thu thuần/i });
    fireEvent.click(metricCheckbox);

    await waitFor(() => {
      expect(screen.getAllByText('Tên cửa hàng').length).toBeGreaterThan(0);
    });
  });
});
