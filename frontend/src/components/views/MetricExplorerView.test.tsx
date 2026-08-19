import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { MetricExplorerView } from '@/components/views/MetricExplorerView';
import { MetricRecord, SemanticCatalog } from '@/lib/api';

describe('MetricExplorerView', () => {
  afterEach(() => cleanup());

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
    expect(screen.queryByText('Compile & Execute')).not.toBeInTheDocument();
  });

  it('renders query summary banner, metric selector, and grouped dimensions for Live DB', () => {
    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        db_id: 3,
        name: 'Doanh thu thuần',
        description: 'Tổng doanh thu',
        sql_template: 'SELECT SUM(price) FROM orders',
        source: 'ai',
        status: 'approved',
        created_by: 1,
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
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
      source_type: 'postgresql',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          db_id: 3,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          description: 'Bảng đơn hàng',
          columns: [
            {
              column_id: 101,
              table_id: 10,
              column_name: 'created_at',
              business_name: 'Ngày tạo đơn',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
            },
            {
              column_id: 102,
              table_id: 10,
              column_name: 'status',
              business_name: 'Trạng thái đơn',
              data_type: 'VARCHAR',
              is_time_dimension: false,
            },
          ],
        },
        {
          table_id: 20,
          db_id: 3,
          table_name: 'customers',
          business_name: 'Khách hàng',
          description: 'Bảng khách hàng',
          columns: [
            {
              column_id: 201,
              table_id: 20,
              column_name: 'city',
              business_name: 'Tỉnh / Thành phố',
              data_type: 'VARCHAR',
              is_time_dimension: false,
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

    // Verify banner and sections
    expect(screen.getByText('CÂU HỎI PHÂN TÍCH HIỆN TẠI')).toBeInTheDocument();
    expect(screen.getByText(/1. CHỈ SỐ ĐO LƯỜNG/)).toBeInTheDocument();
    expect(screen.getByText(/2. CHIỀU PHÂN TÍCH/)).toBeInTheDocument();
    expect(screen.getByText('Doanh thu thuần')).toBeInTheDocument();
    expect(screen.getByText('Đơn hàng')).toBeInTheDocument();
    expect(screen.getByText('Khách hàng')).toBeInTheDocument();
    expect(screen.getByText('Ngày tạo đơn')).toBeInTheDocument();
    expect(screen.getByText('Tỉnh / Thành phố')).toBeInTheDocument();
  });

  it('renders reference Explorer layout with tabs, Compile Preview, Execute, and guardrail badge', async () => {
    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        db_id: 3,
        name: 'Doanh thu thuần',
        description: 'Tổng doanh thu',
        sql_template: 'SELECT SUM(price) FROM orders',
        source: 'ai',
        status: 'approved',
        created_by: 1,
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
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
      source_type: 'postgresql',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          db_id: 3,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          description: 'Bảng đơn hàng',
          columns: [
            {
              column_id: 101,
              table_id: 10,
              column_name: 'created_at',
              business_name: 'Ngày tạo đơn',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
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

    // Compile Preview and Execute are distinct buttons
    const previewButtons = screen.getAllByRole('button', { name: /Preview SQL/i });
    expect(previewButtons.length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: /Thực thi.*Execute/i }).length).toBeGreaterThanOrEqual(1);

    // Select a metric to trigger ResultPanel rendering
    const metricCheckbox = screen.getByRole('checkbox', { name: /Doanh thu thuần/i });
    fireEvent.click(metricCheckbox);

    // Result panel tabs: Table, Chart, SQL
    expect(screen.getByRole('button', { name: /Bảng số liệu/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Biểu đồ/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /SQL Code/i })).toBeInTheDocument();

    // Guardrail badge: Read-only, authoritative limits 100 default, 1000 max, 15s timeout
    expect(screen.getByText(/Read-only/i)).toBeInTheDocument();
    expect(screen.getByText(/LIMIT 100/)).toBeInTheDocument();
    expect(screen.getByText(/max 1000/)).toBeInTheDocument();
    expect(screen.getByText(/15s timeout/)).toBeInTheDocument();
  });

  it('disables unreachable table dimensions when a metric with no join path is selected', async () => {
    const { fireEvent } = await import('@testing-library/react');

    const mockMetrics: MetricRecord[] = [
      {
        metric_id: 1,
        db_id: 3,
        name: 'Doanh thu bán lẻ',
        description: '',
        sql_template: '',
        source: 'ai',
        status: 'approved',
        created_by: 1,
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
        definition: {
          schema_version: 2,
          metric: {
            name: 'Doanh thu bán lẻ',
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
      source_type: 'postgresql',
      query_supported: true,
      tables: [
        {
          table_id: 10,
          db_id: 3,
          table_name: 'orders',
          business_name: 'Đơn hàng',
          columns: [
            {
              column_id: 101,
              table_id: 10,
              column_name: 'created_at',
              business_name: 'Ngày tạo',
              data_type: 'TIMESTAMP',
              is_time_dimension: true,
            },
          ],
        },
        {
          table_id: 78,
          db_id: 3,
          table_name: 'city',
          business_name: 'Thành phố',
          columns: [
            {
              column_id: 7801,
              table_id: 78,
              column_name: 'city_name',
              business_name: 'Tên thành phố',
              data_type: 'VARCHAR',
              is_time_dimension: false,
            },
          ],
        },
      ],
      relationships: [], // No relationship between orders and city
    };

    render(<MetricExplorerView dbId={3} metrics={mockMetrics} catalog={mockCatalog} theme="light" />);

    // Select the metric
    const metricCheckbox = screen.getByRole('checkbox', { name: /Doanh thu bán lẻ/i });
    fireEvent.click(metricCheckbox);

    // By default, it prioritizes reachable tables and displays the filter tab
    expect(screen.getByText(/Chỉ hiện bảng liên kết/i)).toBeInTheDocument();

    // Click "Tất cả" tab to inspect unreachable tables
    const allTab = screen.getByRole('button', { name: /Tất cả/i });
    fireEvent.click(allTab);

    // City table should show "Chưa liên kết" badge
    expect(screen.getByText(/Chưa liên kết/i)).toBeInTheDocument();

    // Click on City table accordion to expand and verify its columns
    const cityAccordion = screen.getByText('Thành phố');
    fireEvent.click(cityAccordion);

    const cityCheckbox = screen.getByRole('checkbox', { name: /Tên thành phố/i });
    expect(cityCheckbox).toBeDisabled();
  });
});

