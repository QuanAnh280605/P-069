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
    expect(screen.getByText(/Chọn ít nhất 1 Chỉ số ở mục 1/)).toBeInTheDocument();

    // Select metric
    const metricCheckbox = screen.getByRole('checkbox', { name: /Doanh thu thuần/i });
    fireEvent.click(metricCheckbox);

    // Scoped dimensions from backend appear
    await waitFor(() => {
      expect(screen.getByText('Trạng thái đơn')).toBeInTheDocument();
      expect(screen.getByText('Tỉnh / Thành phố')).toBeInTheDocument();
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

  it('allows clicking dimension pill to toggle selection', async () => {
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

    // Select metric first
    const metricCheckbox = screen.getByRole('checkbox', { name: /Doanh thu thuần/i });
    fireEvent.click(metricCheckbox);

    await waitFor(() => {
      expect(screen.getByText('Trạng thái đơn')).toBeInTheDocument();
    });

    // Click the dimension pill button
    const pillBtn = screen.getByRole('button', { name: /Trạng thái đơn/i });
    fireEvent.click(pillBtn);

    // It should now appear in the selected tray
    expect(screen.getByText(/Đang chọn/)).toBeInTheDocument();
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
});
