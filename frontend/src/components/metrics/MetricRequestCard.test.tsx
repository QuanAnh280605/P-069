import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { MetricRequestCard } from '@/components/metrics/MetricRequestCard';
import { MetricRequest } from '@/lib/api';

const mockRequest: MetricRequest = {
  id: 42,
  db_id: 1,
  requester_id: 99,
  assistant_message_id: 'msg-1',
  suggestion_index: 0,
  status: 'pending',
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
  definition: {
    schema_version: 2,
    metric: {
      name: 'Tỷ lệ khách hàng quay lại',
      base_entity: 'orders',
      base_entity_id: 10,
      grain: { column_ids: [101] },
      formula: { function: 'COUNT_DISTINCT', expression: 'customer_id' },
      filters: [],
      status: 'pending_approval',
      confidence: 'high',
      excluded_notes: 'Chỉ tính đơn hoàn tất',
    },
  },
};

describe('MetricRequestCard', () => {
  it('renders request details correctly matching MetricCard style', () => {
    const handleApprove = vi.fn();
    const handleEdit = vi.fn();
    const handleReject = vi.fn();

    render(
      <MetricRequestCard
        request={mockRequest}
        onEdit={handleEdit}
        onApprove={handleApprove}
        onReject={handleReject}
      />,
    );

    expect(screen.getByText('Tỷ lệ khách hàng quay lại')).toBeInTheDocument();
    expect(screen.getByText('Member đề xuất')).toBeInTheDocument();
    expect(screen.getByText('Chờ duyệt')).toBeInTheDocument();
    expect(screen.getAllByText(/COUNT_DISTINCT\(customer_id\)/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Chỉ tính đơn hoàn tất')).toBeInTheDocument();
    expect(screen.getByText('Xem YAML definition')).toBeInTheDocument();

    // Click "Chỉnh sửa"
    fireEvent.click(screen.getByText('Chỉnh sửa'));
    expect(handleEdit).toHaveBeenCalledWith(mockRequest);

    // Click "Duyệt & tạo"
    fireEvent.click(screen.getByText('Duyệt & tạo'));
    expect(handleApprove).toHaveBeenCalledWith(mockRequest);

    // Click "Từ chối" with window.confirm mock
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    fireEvent.click(screen.getByText('Từ chối'));
    expect(handleReject).toHaveBeenCalledWith(mockRequest);
  });
});
