import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NotificationCenter } from '@/components/workspace/NotificationCenter';
import { AppNotification } from '@/lib/api';

const metricRequestNotification: AppNotification = {
  id: 1,
  type: 'metric_request_submitted',
  title: 'Có yêu cầu metric mới',
  body: 'Doanh thu trước thuế',
  metric_request_id: 5,
  read_at: null,
  created_at: new Date().toISOString(),
};

const readNotification: AppNotification = {
  id: 3,
  type: 'metric_request_approved',
  title: 'Metric request đã được duyệt',
  body: 'AOV trung bình',
  metric_request_id: 6,
  read_at: '2026-01-01T00:00:00Z',
  created_at: new Date().toISOString(),
};

const systemNotification: AppNotification = {
  id: 2,
  type: 'system_maintenance',
  title: 'Bảo trì hệ thống',
  body: 'Hệ thống tạm dừng 22:00',
  read_at: null,
  created_at: new Date().toISOString(),
};

function renderCenter(props: Partial<Parameters<typeof NotificationCenter>[0]> = {}) {
  return render(
    <NotificationCenter
      items={[metricRequestNotification]}
      unreadCount={1}
      onOpenCatalog={vi.fn()}
      onMarkAllRead={vi.fn().mockResolvedValue(undefined)}
      {...props}
    />,
  );
}

describe('NotificationCenter', () => {
  beforeEach(() => {
    cleanup();
  });

  it('does not mark notifications read just by opening the panel', () => {
    const onMarkAllRead = vi.fn().mockResolvedValue(undefined);
    renderCenter({ onMarkAllRead });

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo' }));

    expect(onMarkAllRead).not.toHaveBeenCalled();
  });

  it('marks all notifications read from the header action', () => {
    const onMarkAllRead = vi.fn().mockResolvedValue(undefined);
    renderCenter({ onMarkAllRead });

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đánh dấu đã đọc' }));

    expect(onMarkAllRead).toHaveBeenCalledTimes(1);
  });

  it('hides the mark-all-read action when nothing is unread', () => {
    renderCenter({ unreadCount: 0 });

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo' }));

    expect(screen.queryByRole('button', { name: 'Đánh dấu đã đọc' })).not.toBeInTheDocument();
  });

  it('opens the catalog and closes the dropdown when a metric request item is clicked', () => {
    const onOpenCatalog = vi.fn();
    renderCenter({ onOpenCatalog });

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo' }));
    fireEvent.click(screen.getByRole('button', { name: /Có yêu cầu metric mới/ }));

    expect(onOpenCatalog).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Có yêu cầu metric mới')).not.toBeInTheDocument();
  });

  it('shows the unread dot only for unread items with a relative time', () => {
    renderCenter({ items: [metricRequestNotification, readNotification] });

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo' }));

    expect(screen.getAllByText('vừa xong').length).toBe(2);
    expect(screen.getByText('Có yêu cầu metric mới').previousSibling).toHaveClass('bg-primary');
    expect(screen.getByText('Metric request đã được duyệt').previousSibling).toBeNull();
  });

  it('renders non metric request notifications as plain rows', () => {
    renderCenter({ items: [systemNotification] });

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo' }));

    expect(screen.getByText('Bảo trì hệ thống')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Bảo trì hệ thống/ })).not.toBeInTheDocument();
  });

  it('shows an inviting empty state when there are no notifications', () => {
    renderCenter({ items: [], unreadCount: 0 });

    fireEvent.click(screen.getByRole('button', { name: 'Thông báo' }));

    expect(screen.getByText('Chưa có thông báo')).toBeInTheDocument();
    expect(screen.getByText('Yêu cầu metric và kết quả phê duyệt sẽ xuất hiện tại đây.')).toBeInTheDocument();
  });
});
