import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
import * as apiModule from '@/lib/api';
import {
  MetricDefinition,
  MetricHistory,
  MetricRecord,
  MetricVersion,
  SemanticApiError,
} from '@/lib/api';

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

const unverifiedMetric: MetricRecord = {
  ...mockMetrics[1],
  metric_id: 3,
  name: 'Giá trị đơn trung bình',
  status: 'unverified',
  definition: {
    ...mockMetrics[1].definition!,
    metric: {
      ...mockMetrics[1].definition!.metric,
      name: 'Giá trị đơn trung bình',
      status: 'unverified',
    },
  },
};

describe('MetricsCatalogView', () => {
  const dataLeadCapabilities = {
    canSubmitMetric: true,
    canManageMetrics: true,
    canApproveMetrics: true,
  };

  beforeEach(() => {
    cleanup();
  });

  it('renders both Pending and Approved sections with counts', () => {
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
      />,
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
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />,
    );

    // Button "Phê duyệt" only appears on pending metric cards
    const approveButtons = screen.getAllByTitle('Phê duyệt chỉ số này');
    expect(approveButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('calls onApproveMetric with metric_id when individual approve button is clicked', () => {
    const handleApprove = vi.fn();
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={handleApprove}
      />,
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
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={handleApproveAll}
      />,
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
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={handleDelete}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
      />,
    );

    const deleteButtons = screen.getAllByTitle('Chuyển vào Thùng rác');
    fireEvent.click(deleteButtons[0]);

    expect(handleDelete).toHaveBeenCalledWith(2);
  });

  it('calls onEditMetric when edit button is clicked', () => {
    const handleEdit = vi.fn();
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={handleEdit}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
      />,
    );

    const editButtons = screen.getAllByRole('button', { name: /Chỉnh sửa/i });
    fireEvent.click(editButtons[0]);

    expect(handleEdit).toHaveBeenCalledWith(mockMetrics[1]);
  });

  it('shows a read-only notice when metric management is not allowed', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        canSubmitMetric={false}
        canManageMetrics={false}
        canApproveMetrics={false}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent(/chế độ chỉ xem/i);
    expect(screen.queryByRole('button', { name: /Sinh với AI/i })).not.toBeInTheDocument();
  });

  it('keeps Admin catalog approved-only and read-only without Data Lead instructions', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={mockMetrics}
        canSubmitMetric={false}
        canManageMetrics={false}
        canApproveMetrics={false}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent(/chế độ chỉ xem/i);
    expect(screen.getByRole('status')).not.toHaveTextContent(/liên hệ Data Lead/i);
    expect(screen.getByRole('button', { name: 'Tất cả(1)' })).toBeInTheDocument();
    expect(screen.queryByText('Số lượng đơn hàng mới')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Gửi metric/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Chỉnh sửa|Duyệt tất cả|Delete/i }),
    ).not.toBeInTheDocument();
  });

  it('does not instruct an Admin to approve metrics when no approved metric is visible', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={[mockMetrics[1]]}
        canSubmitMetric={false}
        canManageMetrics={false}
        canApproveMetrics={false}
      />,
    );

    expect(screen.queryByText(/Hãy duyệt|Data Lead/i)).not.toBeInTheDocument();
  });

  it('lets a Member view and track own unverified metrics without management actions', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={[mockMetrics[0], unverifiedMetric]}
        canSubmitMetric
        canManageMetrics={false}
        canApproveMetrics={false}
      />,
    );

    expect(screen.queryByRole('button', { name: /Gửi metric/i })).not.toBeInTheDocument();
    expect(screen.getAllByText(/Đã gửi/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Chưa được xác minh').length).toBeGreaterThan(0);
    expect(
      screen.queryByRole('button', { name: /Chỉnh sửa|Duyệt chỉ số/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByTitle('Chuyển vào Thùng rác')).not.toBeInTheDocument();
  });

  it('renders "Đề xuất với AI" button for Member when onOpenStudio is provided', () => {
    const onOpenStudio = vi.fn();
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={[mockMetrics[0]]}
        canSubmitMetric
        canManageMetrics={false}
        canApproveMetrics={false}
        onOpenStudio={onOpenStudio}
      />,
    );

    const aiBtn = screen.getByRole('button', { name: 'Đề xuất với AI' });
    expect(aiBtn).toBeInTheDocument();
    fireEvent.click(aiBtn);
    expect(onOpenStudio).toHaveBeenCalledOnce();
  });

  it('gives Data Lead edit, approve, and delete actions for unverified metrics', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={[unverifiedMetric]}
        canSubmitMetric
        canManageMetrics
        canApproveMetrics
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onApproveMetric={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Chỉnh sửa' })).toBeInTheDocument();
    expect(screen.getByTitle('Chuyển vào Thùng rác')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Duyệt chỉ số này/i })).toBeInTheDocument();
  });

  it('renders metric cards with formula expression in monospace', () => {
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />,
    );
    // Verify formula expression display
    expect(screen.getByText(/SUM\(price\).*Bảng.*orders/)).toBeInTheDocument();
    expect(screen.getByText(/COUNT\(id\).*Bảng.*orders/)).toBeInTheDocument();
  });

  it('shows individual approve button on pending metric cards', () => {
    const onApprove = vi.fn();
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={onApprove}
      />,
    );
    // Pending card should have individual approve button
    const approveBtn = screen.getByRole('button', {
      name: /Duyệt chỉ số này/i,
    });
    expect(approveBtn).toBeInTheDocument();
    fireEvent.click(approveBtn);
    expect(onApprove).toHaveBeenCalledWith(2);
  });

  it('renders filter tabs with correct metric counts', () => {
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />,
    );
    // Filter tabs should show counts
    expect(screen.getByRole('button', { name: /Tất cả\(2\)/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Chờ phê duyệt\(1\)/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Đã phê duyệt\(1\)/ })).toBeInTheDocument();
  });

  it('counts only the rendered sections in the Tất cả tab for a member submitter', () => {
    render(
      <MetricsCatalogView
        dbId={3}
        metrics={[mockMetrics[0], mockMetrics[1], unverifiedMetric]}
        canSubmitMetric
        canManageMetrics={false}
        canApproveMetrics={false}
      />,
    );

    // Sections rendered: "Đã gửi" (own unverified) + "Đã phê duyệt"; another user's
    // pending metric is not displayed anywhere, so it must not inflate the total.
    expect(screen.getByRole('button', { name: /Tất cả\(2\)/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Đã gửi\(1\)/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Đã phê duyệt\(1\)/ })).toBeInTheDocument();
  });

  it('filters metrics when filter tab is clicked', async () => {
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />,
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
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />,
    );
    // Each card should have YAML definition toggle
    expect(screen.getAllByText(/Xem YAML definition/).length).toBeGreaterThanOrEqual(2);
  });

  it('shows status badges with correct labels', () => {
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onApproveMetric={vi.fn()}
      />,
    );
    // Status badges
    expect(screen.getByText('Đã duyệt')).toBeInTheDocument();
    expect(screen.getByText('Chờ duyệt')).toBeInTheDocument();
  });

  it('renders "+ Thêm thủ công" button for Data Lead and calls onAddMetric when clicked', () => {
    const handleAdd = vi.fn();
    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onAddMetric={handleAdd}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
      />,
    );

    const addBtn = screen.getByRole('button', { name: /Thêm thủ công/i });
    expect(addBtn).toBeInTheDocument();
    fireEvent.click(addBtn);
    expect(handleAdd).toHaveBeenCalledTimes(1);
  });

  it('renders Trash tab and allows restoring soft-deleted metrics', () => {
    const handleRestore = vi.fn();
    const deletedMetric: MetricRecord = {
      ...mockMetrics[0],
      metric_id: 99,
      name: 'Metric đã xóa',
      is_deleted: true,
    };

    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={[...mockMetrics, deletedMetric]}
        onRestoreMetric={handleRestore}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
      />,
    );

    // Active tab shouldn't list the deleted metric
    expect(screen.queryByText('Metric đã xóa')).not.toBeInTheDocument();

    // Check Trash tab button with count
    const trashTab = screen.getByRole('button', { name: /Thùng rác\(1\)/i });
    expect(trashTab).toBeInTheDocument();
    fireEvent.click(trashTab);

    // Now in Trash view, deleted metric card should appear
    expect(screen.getByText('Metric đã xóa')).toBeInTheDocument();
    expect(screen.getByText('Đã xóa')).toBeInTheDocument();

    // Click Khôi phục button
    const restoreBtn = screen.getByRole('button', { name: /Khôi phục/i });
    expect(restoreBtn).toBeInTheDocument();
    fireEvent.click(restoreBtn);

    expect(handleRestore).toHaveBeenCalledWith(99);
  });

  it('moves metric to approved section immediately when status is approved without pending version', () => {
    const { rerender } = render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={[mockMetrics[1]]} // pending_approval
        onApproveMetric={vi.fn()}
      />,
    );

    // Should be in pending section
    expect(screen.getByText(/Metrics Đang Chờ Phê Duyệt/)).toBeInTheDocument();
    expect(screen.getByTitle('Phê duyệt chỉ số này')).toBeInTheDocument();

    // Rerender as approved with no pending version
    const approvedItem: MetricRecord = {
      ...mockMetrics[1],
      status: 'approved',
      has_pending_version: false,
      definition: {
        ...mockMetrics[1].definition!,
        metric: {
          ...mockMetrics[1].definition!.metric,
          status: 'approved',
        },
      },
    };

    rerender(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={[approvedItem]}
        onApproveMetric={vi.fn()}
      />,
    );

    // Pending section should be empty
    expect(screen.getByText('Không có metric nào đang chờ duyệt.')).toBeInTheDocument();
    // Approve button should no longer exist
    expect(screen.queryByTitle('Phê duyệt chỉ số này')).not.toBeInTheDocument();
    // Metric name should be in approved section
    expect(screen.getByText('Số lượng đơn hàng mới')).toBeInTheDocument();
  });

  it('displays metric with pending version in pending section with version badge', () => {
    const approvedWithPendingVersion: MetricRecord = {
      ...mockMetrics[0],
      status: 'approved',
      has_pending_version: true,
      pending_version_number: 2,
    };

    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={[approvedWithPendingVersion]}
        onApproveMetric={vi.fn()}
      />,
    );

    expect(screen.getByText(/v2 chờ duyệt/)).toBeInTheDocument();
    expect(screen.getByTitle('Phê duyệt chỉ số này')).toBeInTheDocument();
  });
});


describe('MetricsCatalogView history modal', () => {
  function makeDefinition(expression: string): MetricDefinition {
    return {
      schema_version: 2,
      metric: {
        name: 'Doanh thu thuần',
        base_entity: 'orders',
        base_entity_id: 10,
        grain: { column_ids: [101] },
        formula: { function: 'SUM', expression },
        filters: [],
        status: 'approved',
        confidence: 'high',
        excluded_notes: '',
      },
    };
  }

  function makeVersion(version: number, expression: string): MetricVersion {
    return {
      version,
      definition: makeDefinition(expression),
      changed_by: 1,
      change_reason: 'update',
      created_at: `2026-01-0${version}`,
    };
  }

  const approvedMetric: MetricRecord = {
    metric_id: 1,
    name: 'Doanh thu thuần',
    source: 'ai',
    version: 3,
    status: 'approved',
    created_at: '2026-01-03',
    definition: makeDefinition('a - b'),
  };

  const mockHistory: MetricHistory = {
    metric_id: 1,
    metric_name: 'Doanh thu thuần',
    versions: [makeVersion(3, 'a - b'), makeVersion(2, 'a'), makeVersion(1, 'a')],
  };

  const historyAfterRollback: MetricHistory = {
    ...mockHistory,
    versions: mockHistory.versions.filter((version) => version.version <= 2),
  };

  const dataLead = { canManageMetrics: true, canSubmitMetric: true, canApproveMetrics: true };

  const renderCatalog = (props: Record<string, unknown> = {}) =>
    render(
      <MetricsCatalogView dbId={3} metrics={[approvedMetric]} {...dataLead} {...props} />,
    );

  const openHistory = async () => {
    fireEvent.click(screen.getByTitle('Xem lịch sử phiên bản'));
    await screen.findByRole('dialog');
  };

  beforeEach(() => {
    cleanup();
    vi.spyOn(apiModule, 'getMetricHistoryApi').mockResolvedValue(mockHistory);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('defaults selectors to the latest two versions and renders the colored diff', async () => {
    renderCatalog();
    await openHistory();

    expect(apiModule.getMetricHistoryApi).toHaveBeenCalledWith('3', 1);
    const baseSelect = screen.getByLabelText('Bản gốc (cũ)') as HTMLSelectElement;
    const compareSelect = screen.getByLabelText('So sánh (mới)') as HTMLSelectElement;
    expect(baseSelect.value).toBe('2');
    expect(compareSelect.value).toBe('3');

    const diff = screen.getByTestId('metric-version-diff');
    const removed = within(diff).getByText('SUM(a)').closest('[data-status]');
    const added = within(diff).getByText('SUM(a - b)').closest('[data-status]');
    expect(removed).toHaveAttribute('data-status', 'removed');
    expect(added).toHaveAttribute('data-status', 'added');
  });

  it('rejects equal selections instead of rendering an empty diff', async () => {
    renderCatalog();
    await openHistory();

    fireEvent.change(screen.getByLabelText('Bản gốc (cũ)'), { target: { value: '3' } });

    expect(screen.getByText(/hai phiên bản khác nhau/i)).toBeInTheDocument();
    expect(screen.queryByTestId('metric-version-diff')).not.toBeInTheDocument();
  });

  it('hides rollback for roles without manage capability', async () => {
    vi.spyOn(apiModule, 'rollbackMetricApi');
    renderCatalog({ canManageMetrics: false, canApproveMetrics: false });
    await openHistory();

    expect(
      screen.queryByRole('button', { name: 'Khôi phục phiên bản này' }),
    ).not.toBeInTheDocument();
  });

  it('shows rollback for Data Lead only when the selected target is older than current', async () => {
    renderCatalog();
    await openHistory();

    expect(screen.getByRole('button', { name: 'Khôi phục phiên bản này' })).toBeInTheDocument();

    // Selecting the newest version as target hides the destructive action.
    fireEvent.change(screen.getByLabelText('Bản gốc (cũ)'), { target: { value: '3' } });
    expect(
      screen.queryByRole('button', { name: 'Khôi phục phiên bản này' }),
    ).not.toBeInTheDocument();
  });

  it('confirms destructively, refetches history, notifies parent, and resets selectors', async () => {
    const getHistorySpy = vi
      .spyOn(apiModule, 'getMetricHistoryApi')
      .mockResolvedValueOnce(mockHistory)
      .mockResolvedValueOnce(historyAfterRollback);
    vi.spyOn(apiModule, 'rollbackMetricApi').mockResolvedValue(approvedMetric);
    const onMetricsChanged = vi.fn().mockResolvedValue(undefined);
    renderCatalog({ onMetricsChanged });
    await openHistory();

    fireEvent.click(screen.getByRole('button', { name: 'Khôi phục phiên bản này' }));
    expect(await screen.findByText(/xóa vĩnh viễn/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Khôi phục & xóa phiên bản mới' }));

    await waitFor(() => expect(onMetricsChanged).toHaveBeenCalledTimes(1));
    expect(apiModule.rollbackMetricApi).toHaveBeenCalledWith('3', 1, 2);
    expect(getHistorySpy).toHaveBeenCalledTimes(2);
    expect(getHistorySpy).toHaveBeenLastCalledWith('3', 1);
    expect(screen.getByText(/Đã khôi phục/i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Khôi phục & xóa phiên bản mới' }),
    ).not.toBeInTheDocument();
    expect((screen.getByLabelText('Bản gốc (cũ)') as HTMLSelectElement).value).toBe('1');
    expect((screen.getByLabelText('So sánh (mới)') as HTMLSelectElement).value).toBe('2');
  });

  it('retains the history modal and shows a Vietnamese error when rollback fails', async () => {
    vi.spyOn(apiModule, 'rollbackMetricApi').mockRejectedValue(
      new SemanticApiError(422, 'Chỉ được phép khôi phục về phiên bản cũ hơn.'),
    );
    renderCatalog();
    await openHistory();

    fireEvent.click(screen.getByRole('button', { name: 'Khôi phục phiên bản này' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Khôi phục & xóa phiên bản mới' }));

    expect(await screen.findByText(/Chỉ được phép khôi phục về phiên bản cũ hơn/)).toBeInTheDocument();
    expect(screen.getByText(/Lịch sử · Doanh thu thuần/)).toBeInTheDocument();
  });

  it('locks confirm and close controls while rollback is pending', async () => {
    vi.spyOn(apiModule, 'rollbackMetricApi').mockImplementation(
      () => new Promise(() => undefined),
    );
    renderCatalog();
    await openHistory();

    fireEvent.click(screen.getByRole('button', { name: 'Khôi phục phiên bản này' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Khôi phục & xóa phiên bản mới' }));

    expect(await screen.findByRole('button', { name: /Đang khôi phục/i })).toBeDisabled();
    expect(screen.queryByLabelText('Close')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Bản gốc (cũ)')).toBeDisabled();
  });

  it('shows a Vietnamese error and keeps the modal closed when history loading fails', async () => {
    vi.spyOn(apiModule, 'getMetricHistoryApi').mockRejectedValue(new Error('network down'));
    renderCatalog();

    fireEvent.click(screen.getByTitle('Xem lịch sử phiên bản'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/Không thể tải lịch sử/i);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('announces loading state while fetching history', async () => {
    let resolveHistory!: (value: MetricHistory) => void;
    vi.spyOn(apiModule, 'getMetricHistoryApi').mockReturnValue(
      new Promise<MetricHistory>((resolve) => {
        resolveHistory = resolve;
      }),
    );
    renderCatalog();

    fireEvent.click(screen.getByTitle('Xem lịch sử phiên bản'));
    expect(screen.getByRole('status')).toHaveTextContent(/Đang tải lịch sử/i);

    await act(async () => {
      resolveHistory(mockHistory);
    });
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  it('hides rollback when only one version exists so no older target can be selected', async () => {
    vi.spyOn(apiModule, 'getMetricHistoryApi').mockResolvedValue({
      ...mockHistory,
      versions: [makeVersion(1, 'a')],
    });
    renderCatalog();
    await openHistory();

    expect(
      screen.queryByRole('button', { name: 'Khôi phục phiên bản này' }),
    ).not.toBeInTheDocument();
  });
});

describe('MetricsCatalogView member metric requests in pending approval section', () => {
  const dataLeadCapabilities = {
    canSubmitMetric: true,
    canManageMetrics: true,
    canApproveMetrics: true,
  };

  const mockMemberRequest: apiModule.MetricRequest = {
    id: 42,
    db_id: 3,
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
        excluded_notes: '',
      },
    },
  };

  beforeEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders member metric request inside pending approval section and updates tab count', async () => {
    vi.spyOn(apiModule, 'listMetricRequestsApi').mockResolvedValue([mockMemberRequest]);

    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
      />,
    );

    // Wait for member request to load and appear inside Pending approval section
    expect(await screen.findByText('Tỷ lệ khách hàng quay lại')).toBeInTheDocument();
    expect(screen.getByText('Member đề xuất')).toBeInTheDocument();

    // Section 1 header should reflect 1 pending metric + 1 member request = 2
    expect(screen.getByText(/1\. Metrics Đang Chờ Phê Duyệt/)).toBeInTheDocument();

    // Pending tab button should include pending request
    const pendingTab = screen.getByRole('button', { name: /Chờ phê duyệt/ });
    expect(pendingTab).toHaveTextContent('(2)');
  });

  it('displays member request when switching to Chờ phê duyệt tab and allows approve', async () => {
    vi.spyOn(apiModule, 'listMetricRequestsApi').mockResolvedValue([mockMemberRequest]);
    const approveSpy = vi.spyOn(apiModule, 'approveMetricRequestApi').mockResolvedValue({
      ...mockMemberRequest,
      status: 'approved',
    });

    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
        onMetricsChanged={vi.fn()}
      />,
    );

    expect(await screen.findByText('Tỷ lệ khách hàng quay lại')).toBeInTheDocument();

    // Switch to "Chờ phê duyệt" tab
    fireEvent.click(screen.getByRole('button', { name: /Chờ phê duyệt/ }));

    // Verify request is present in "Chờ phê duyệt" tab
    expect(screen.getByText('Tỷ lệ khách hàng quay lại')).toBeInTheDocument();

    // Click "Duyệt & tạo"
    fireEvent.click(screen.getByRole('button', { name: 'Duyệt & tạo' }));

    await waitFor(() => {
      expect(approveSpy).toHaveBeenCalledWith('3', 42, undefined);
    });
  });

  it('allows rejecting a member metric request', async () => {
    vi.spyOn(apiModule, 'listMetricRequestsApi').mockResolvedValue([mockMemberRequest]);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const rejectSpy = vi.spyOn(apiModule, 'rejectMetricRequestApi').mockResolvedValue({
      ...mockMemberRequest,
      status: 'rejected',
    });

    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
      />,
    );

    expect(await screen.findByText('Tỷ lệ khách hàng quay lại')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Từ chối' }));

    await waitFor(() => {
      expect(rejectSpy).toHaveBeenCalledWith('3', 42);
    });
  });

  it('calls onEditRequest when clicking Chỉnh sửa on member request', async () => {
    vi.spyOn(apiModule, 'listMetricRequestsApi').mockResolvedValue([mockMemberRequest]);
    const handleEditRequest = vi.fn();

    render(
      <MetricsCatalogView
        {...dataLeadCapabilities}
        dbId={3}
        metrics={mockMetrics}
        onDeleteMetric={vi.fn()}
        onEditMetric={vi.fn()}
        onEditRequest={handleEditRequest}
        onOpenStudio={vi.fn()}
        onApproveAll={vi.fn()}
      />,
    );

    expect(await screen.findByText('Tỷ lệ khách hàng quay lại')).toBeInTheDocument();

    const requestCard = screen.getByText('Tỷ lệ khách hàng quay lại').closest('article')!;
    fireEvent.click(within(requestCard).getByRole('button', { name: 'Chỉnh sửa' }));
    expect(handleEditRequest).toHaveBeenCalledWith(mockMemberRequest);
  });
});

