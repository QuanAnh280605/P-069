import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

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
});
