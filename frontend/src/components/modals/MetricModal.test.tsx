import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MetricModal } from '@/components/modals/MetricModal';
import { MetricDefinition, SemanticTable } from '@/lib/api';

const mockTables: SemanticTable[] = [
  {
    table_name: 'orders',
    business_name: 'Đơn hàng',
    description: 'Bảng đơn hàng',
    columns: [
      { column_name: 'price', data_type: 'numeric', business_name: 'Giá' },
      {
        column_name: 'quantity',
        data_type: 'integer',
        business_name: 'Số lượng',
      },
    ],
  },
];

const mockDefinition: MetricDefinition = {
  metric: {
    name: 'Doanh thu thuần',
    formula: { function: 'SUM', expression: 'price' },
    base_entity: 'orders',
    filters: [],
    status: 'pending_approval',
    confidence: 'high',
    excluded_notes: '',
  },
};

describe('MetricModal', () => {
  beforeEach(() => {
    cleanup();
  });

  it('renders the metric name in the modal header', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        initialName="Doanh thu thuần"
      />,
    );
    expect(screen.getByText('Định nghĩa Business Metric')).toBeInTheDocument();
  });

  it('shows Definition and History tabs', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        initialName="Doanh thu thuần"
      />,
    );
    expect(screen.getByRole('button', { name: /Definition/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /History/i })).toBeInTheDocument();
  });

  it('shows Definition tab content by default with form fields', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        initialName="Doanh thu thuần"
      />,
    );
    // Definition tab should be active and show form fields
    expect(screen.getByText('Tên metric')).toBeInTheDocument();
    expect(screen.getByText('Base entity')).toBeInTheDocument();
    expect(screen.getByText('Hàm tổng hợp')).toBeInTheDocument();
    expect(screen.getByText('Biểu thức công thức')).toBeInTheDocument();
  });

  it('switches to History tab and shows version timeline', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        initialName="Doanh thu thuần"
        versions={[
          {
            version: 2,
            definition: mockDefinition,
            change_reason: 'Updated formula',
            created_at: '2026-01-15T10:00:00Z',
          },
          {
            version: 1,
            definition: mockDefinition,
            change_reason: 'Initial creation',
            created_at: '2026-01-10T08:00:00Z',
          },
        ]}
      />,
    );
    const historyBtn = screen.getByRole('button', { name: /History/i });
    fireEvent.click(historyBtn);
    expect(screen.getByText(/Version 2/)).toBeInTheDocument();
    expect(screen.getByText(/Version 1/)).toBeInTheDocument();
    expect(screen.getByText(/Updated formula/)).toBeInTheDocument();
  });

  it('shows StatusPill in modal header for pending metric', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        initialName="Doanh thu thuần"
        status="pending_approval"
      />,
    );
    expect(screen.getByText('Chờ duyệt')).toBeInTheDocument();
  });

  it('shows approve button for non-approved metrics', () => {
    const onApprove = vi.fn();
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        initialName="Doanh thu thuần"
        status="pending_approval"
        onApprove={onApprove}
      />,
    );
    const approveBtn = screen.getByRole('button', { name: /Phê duyệt/i });
    expect(approveBtn).toBeInTheDocument();
    fireEvent.click(approveBtn);
    expect(onApprove).toHaveBeenCalled();
  });

  it('shows approved status text instead of approve button for approved metrics', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        initialName="Doanh thu thuần"
        status="approved"
      />,
    );
    expect(screen.getByText(/Đã có trong Semantic Layer/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Phê duyệt/i })).not.toBeInTheDocument();
  });

  it('displays YAML preview with compiled spec', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        initialName="Doanh thu thuần"
      />,
    );
    // YAML preview section should be visible
    expect(screen.getByText(/Preview chỉ đọc/i)).toBeInTheDocument();
  });

  it('explains that non-authorized users cannot save a metric', () => {
    const onSave = vi.fn();
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={onSave}
        tables={mockTables}
        initialDefinition={mockDefinition}
        canSave={false}
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(/không có quyền/i);
    expect(screen.getByRole('button', { name: 'Lưu metric' })).toBeDisabled();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('presents the standard form as a Member submission', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        submissionMode
      />,
    );

    expect(screen.getByText('Gửi Business Metric')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Gửi metric' })).toBeEnabled();
    expect(screen.getByText(/Chưa được xác minh sau khi gửi/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Phê duyệt/i })).not.toBeInTheDocument();
  });
});
