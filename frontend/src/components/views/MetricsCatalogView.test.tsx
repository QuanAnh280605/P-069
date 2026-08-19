import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
import { MetricRecord } from '@/lib/api';

describe('MetricsCatalogView', () => {
  const mockMetrics: MetricRecord[] = [
    {
      metric_id: 1,
      db_id: 3,
      name: 'Doanh thu thuần',
      description: 'Tổng doanh thu sau giảm giá',
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
    {
      metric_id: 2,
      db_id: 3,
      name: 'Số lượng đơn hàng mới',
      description: 'Đơn hàng mới tạo',
      sql_template: 'SELECT COUNT(id) FROM orders',
      source: 'ai',
      status: 'pending_approval',
      created_by: 1,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
      definition: {
        schema_version: 2,
        metric: {
          name: 'Số lượng đơn hàng mới',
          base_entity: 'orders',
          base_entity_id: 10,
          grain: { column_ids: [101] },
          formula: { function: 'COUNT', expression: 'id' },
          filters: [],
          status: 'pending_approval',
          confidence: 'high',
          excluded_notes: '',
        },
      },
    },
  ];

  beforeEach(() => {
    cleanup();
  });

  it('renders both Pending and Approved sections with counts', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />
    );

    // Verify sections
    expect(screen.getByText('1. Metrics Đang Chờ Phê Duyệt')).toBeInTheDocument();
    expect(screen.getByText('2. Metrics Đã Phê Duyệt (Official Metrics)')).toBeInTheDocument();

    // Verify metrics in appropriate sections
    expect(screen.getByText('Số lượng đơn hàng mới')).toBeInTheDocument();
    expect(screen.getByText('Doanh thu thuần')).toBeInTheDocument();

    // Verify quick action button
    expect(screen.getByText('Duyệt tất cả (1)')).toBeInTheDocument();
  });

  it('renders metric cards with formula expression in monospace', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />
    );
    // Verify formula expression display
    expect(screen.getByText(/SUM\(price\).*Bảng.*orders/)).toBeInTheDocument();
    expect(screen.getByText(/COUNT\(id\).*Bảng.*orders/)).toBeInTheDocument();
  });

  it('shows individual approve button on pending metric cards', () => {
    const onApprove = vi.fn();
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={onApprove}
      />
    );
    // Pending card should have individual approve button
    const approveBtn = screen.getByRole('button', { name: /Duyệt chỉ số này/i });
    expect(approveBtn).toBeInTheDocument();
    fireEvent.click(approveBtn);
    expect(onApprove).toHaveBeenCalledWith(2);
  });

  it('renders filter tabs with correct metric counts', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />
    );
    // Filter tabs should show counts
    expect(screen.getByText(/Tất cả \(2\)/)).toBeInTheDocument();
    expect(screen.getByText(/Chờ phê duyệt \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/Đã phê duyệt \(1\)/)).toBeInTheDocument();
  });

  it('filters metrics when filter tab is clicked', async () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />
    );

    // Click on "Chờ phê duyệt" tab
    fireEvent.click(screen.getByText(/Chờ phê duyệt/));

    // Only pending metric should be visible in the card grid
    expect(screen.getByText('Số lượng đơn hàng mới')).toBeInTheDocument();
    expect(screen.queryByText('Doanh thu thuần')).not.toBeInTheDocument();
  });

  it('shows YAML definition toggle in metric cards', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />
    );
    // Each card should have YAML definition toggle
    expect(screen.getAllByText(/Xem YAML definition/).length).toBeGreaterThanOrEqual(2);
  });

  it('shows status badges with correct labels', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />
    );
    // Status badges
    expect(screen.getByText('Đã duyệt')).toBeInTheDocument();
    expect(screen.getByText('Chờ duyệt')).toBeInTheDocument();
  });
});
