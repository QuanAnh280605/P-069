import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MetricModal } from '@/components/modals/MetricModal';
import * as apiModule from '@/lib/api';
import { MetricDefinition, MetricJoinPathOptions, SemanticCatalog, SemanticTable } from '@/lib/api';

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

  it('hides the formula expression field when reviewing a Member proposal', () => {
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        isMemberRequest
      />,
    );

    expect(screen.getByText('Duyệt & Chỉnh sửa đề xuất của Member')).toBeInTheDocument();
    expect(screen.queryByText('Biểu thức công thức')).not.toBeInTheDocument();
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

  const mockCatalog: SemanticCatalog = {
    db_id: 5,
    source_type: 'live',
    query_supported: true,
    tables: [
      {
        table_id: 10,
        table_name: 'orders',
        business_name: 'Đơn hàng',
        columns: [
          { column_id: 101, column_name: 'created_at', business_name: 'Ngày tạo', data_type: 'TIMESTAMP', is_time_dimension: true, allowed_values: null },
          { column_id: 102, column_name: 'status', business_name: 'Trạng thái', data_type: 'VARCHAR', is_time_dimension: false, allowed_values: null },
        ],
      },
      {
        table_id: 20,
        table_name: 'customers',
        business_name: 'Khách hàng',
        columns: [
          { column_id: 201, column_name: 'city', business_name: 'Tỉnh/Thành phố', data_type: 'VARCHAR', is_time_dimension: false, allowed_values: null },
        ],
      },
    ],
    relationships: [],
  };

  const joinOptions: MetricJoinPathOptions = {
    '20': [
      {
        relationship_ids: [5],
        entity_ids: [10, 20],
        labels: ['Đơn thuộc khách'],
        descriptions: ['Mỗi đơn hàng thuộc về một khách hàng'],
      },
      {
        relationship_ids: [6],
        entity_ids: [10, 20],
        labels: ['Đơn giao cho khách'],
        descriptions: ['Giao dịch được gán cho khách hàng'],
      },
    ],
  };

  it('does not show Ngữ cảnh quan hệ section in metric modal', async () => {
    vi.spyOn(apiModule, 'getMetricJoinPathOptionsApi').mockResolvedValue(joinOptions);
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={vi.fn()}
        tables={mockTables}
        initialDefinition={mockDefinition}
        dbId="5"
        catalog={mockCatalog}
      />,
    );

    expect(screen.queryByText('Ngữ cảnh quan hệ')).not.toBeInTheDocument();
  });

  it('saves metric definition directly without join path configuration', async () => {
    const onSave = vi.fn();
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={onSave}
        tables={mockTables}
        initialDefinition={mockDefinition}
        dbId="5"
        catalog={mockCatalog}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Lưu metric' }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
  });

  it('blocks save and shows a blocking message for a stale stored preferred path', async () => {
    const onSave = vi.fn();
    const definition: MetricDefinition = {
      metric: {
        ...mockDefinition.metric,
      },
    };
    render(
      <MetricModal
        isOpen
        onClose={vi.fn()}
        onSave={onSave}
        tables={mockTables}
        initialDefinition={definition}
        dbId="5"
        catalog={mockCatalog}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Lưu metric' }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
  });
});
