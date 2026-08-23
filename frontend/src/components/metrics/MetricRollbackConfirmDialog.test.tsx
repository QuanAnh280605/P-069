import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MetricRollbackConfirmDialog } from '@/components/metrics/MetricRollbackConfirmDialog';

function renderDialog(overrides: Partial<Parameters<typeof MetricRollbackConfirmDialog>[0]> = {}) {
  const props = {
    open: true,
    metricName: 'Doanh thu thuần',
    targetVersion: 2,
    currentVersion: 3,
    pending: false,
    onConfirm: vi.fn(),
    onOpenChange: vi.fn(),
    ...overrides,
  };
  render(<MetricRollbackConfirmDialog {...props} />);
  return props;
}

describe('MetricRollbackConfirmDialog', () => {
  afterEach(() => {
    cleanup();
  });

  it('warns that newer versions are permanently deleted and shows the affected range', () => {
    renderDialog({ targetVersion: 2, currentVersion: 3 });

    expect(screen.getByText(/xóa vĩnh viễn/i)).toBeInTheDocument();
    expect(screen.getByText(/v3/)).toBeInTheDocument();
  });

  it('lists every affected version when several are newer than the target', () => {
    renderDialog({ targetVersion: 1, currentVersion: 3 });

    expect(screen.getByText(/v2, v3/)).toBeInTheDocument();
  });

  it('calls onConfirm when the destructive confirm button is clicked', () => {
    const props = renderDialog();

    fireEvent.click(screen.getByRole('button', { name: /khôi phục/i }));

    expect(props.onConfirm).toHaveBeenCalledTimes(1);
  });

  it('disables confirm and cancel buttons while pending', () => {
    renderDialog({ pending: true });

    const confirm = screen.getByRole('button', { name: /đang khôi phục/i });
    const cancel = screen.getByRole('button', { name: /hủy/i });
    expect(confirm).toBeDisabled();
    expect(cancel).toBeDisabled();
  });

  it('does not call onOpenChange while pending', () => {
    const props = renderDialog({ pending: true });

    fireEvent.click(screen.getByRole('button', { name: /hủy/i }));

    expect(props.onOpenChange).not.toHaveBeenCalled();
  });

  it('closes via cancel when not pending', () => {
    const props = renderDialog();

    fireEvent.click(screen.getByRole('button', { name: /hủy/i }));

    expect(props.onOpenChange).toHaveBeenCalledWith(false);
  });

  it('renders nothing when closed', () => {
    renderDialog({ open: false });

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
