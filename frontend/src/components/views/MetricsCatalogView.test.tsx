import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
import { MetricRecord } from '@/lib/api';

describe('MetricsCatalogView', () => {
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
      name: 'Số lượng đơn hàng mới',
      source: 'ai',
      version: 1,
      status: 'pending_approval',
      created_at: '2026-01-01',
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
          confidence: 'medium',
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
      />
    );

    // Section headers with counts
    expect(screen.getByText(/Metrics Đang Chờ Phê Duyệt/)).toBeInTheDocument();
    expect(screen.getByText(/Metrics Đã Phê Duyệt/)).toBeInTheDocument();

    // Metric names
    expect(screen.getByText('Doanh thu thuần')).toBeInTheDocument();
    expect(screen.getByText('Số lượng đơn hàng mới')).toBeInTheDocument();
  });

  it('shows individual approve button on pending metric cards', () => {
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

    // Button "Phê duyệt" only appears on pending metric cards
    const approveButtons = screen.getAllByTitle('Phê duyệt chỉ số này');
    expect(approveButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('calls onApproveMetric with metric_id when individual approve button is clicked', () => {
    const handleApprove = vi.fn();
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={handleApprove}
      />
    );

    // Click the individual approve button on the pending metric card (metric_id = 2)
    const approveBtn = screen.getByTitle('Phê duyệt chỉ số này');
    fireEvent.click(approveBtn);

    expect(handleApprove).toHaveBeenCalledWith(2);
  });

  it('calls onApproveAll when approving all pending metrics', () => {
    const handleApproveAll = vi.fn();
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={handleApproveAll}
      />
    );

    // Header "Duyệt tất cả" button (only visible when pending > 0)
    const approveAllBtn = screen.getByRole('button', { name: /Duyệt tất cả/i });
    fireEvent.click(approveAllBtn);

    expect(handleApproveAll).toHaveBeenCalledTimes(1);
  });

  it('calls onDeleteMetric when delete button is clicked', () => {
    const handleDelete = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={handleDelete}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
      />
    );

    const deleteButtons = screen.getAllByTitle('Xóa metric');
    fireEvent.click(deleteButtons[0]);

    expect(handleDelete).toHaveBeenCalledWith(2);
  });

  it('calls onEditMetric when edit button is clicked', () => {
    const handleEdit = vi.fn();
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={handleEdit}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
      />
    );

    const editButtons = screen.getAllByRole('button', { name: /Chỉnh sửa/i });
    fireEvent.click(editButtons[0]);

    expect(handleEdit).toHaveBeenCalledWith(mockMetrics[1]);
  });
});
