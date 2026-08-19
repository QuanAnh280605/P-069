import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatHistorySection } from '@/components/workspace/ChatHistorySection';
import type { ChatSessionItem } from '@/lib/api';

const mockSessions: ChatSessionItem[] = [
  {
    id: 's-1',
    db_id: 1,
    title: 'Doanh thu tháng 1',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    message_count: 4,
  },
  {
    id: 's-2',
    db_id: 1,
    title: 'Phân tích khách hàng mới',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
    message_count: 2,
  },
  {
    id: 's-3',
    db_id: 1,
    title: 'Báo cáo tồn kho',
    created_at: new Date(Date.now() - 7200000).toISOString(),
    updated_at: new Date(Date.now() - 7200000).toISOString(),
    message_count: 1,
  },
];

describe('ChatHistorySection', () => {
  beforeEach(() => {
    cleanup();
  });

  it('renders section header with count badge and new chat button', () => {
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        canChat={true}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />,
    );

    expect(screen.getByText('Lịch sử trò chuyện')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByLabelText('Tạo cuộc trò chuyện mới')).toBeInTheDocument();
  });

  it('renders all session items with message counts', () => {
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        canChat={true}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />,
    );

    expect(screen.getByText('Doanh thu tháng 1')).toBeInTheDocument();
    expect(screen.getByText('Phân tích khách hàng mới')).toBeInTheDocument();
    expect(screen.getByText('Báo cáo tồn kho')).toBeInTheDocument();
    expect(screen.getByText('4 tin')).toBeInTheDocument();
    expect(screen.getByText('2 tin')).toBeInTheDocument();
  });

  it('filters sessions by search input', () => {
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        canChat={true}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />,
    );

    const searchInput = screen.getByPlaceholderText('Tìm đoạn chat...');
    fireEvent.change(searchInput, { target: { value: 'khách hàng' } });

    expect(screen.getByText('Phân tích khách hàng mới')).toBeInTheDocument();
    expect(screen.queryByText('Doanh thu tháng 1')).not.toBeInTheDocument();
    expect(screen.queryByText('Báo cáo tồn kho')).not.toBeInTheDocument();
  });

  it('calls onSelectSession when clicking on a session card', () => {
    const handleSelect = vi.fn();
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        canChat={true}
        onSelectSession={handleSelect}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText('Phân tích khách hàng mới'));
    expect(handleSelect).toHaveBeenCalledWith('s-2');
  });

  it('allows renaming session inline', async () => {
    const handleRename = vi.fn().mockResolvedValue(undefined);
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        canChat={true}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={handleRename}
      />,
    );

    const editBtns = screen.getAllByTitle('Đổi tên đoạn chat');
    fireEvent.click(editBtns[0]);

    const editInput = screen.getByPlaceholderText('Tên đoạn chat...') as HTMLInputElement;
    fireEvent.change(editInput, { target: { value: 'Doanh thu Q1 mới' } });

    const saveBtn = screen.getByRole('button', { name: /Lưu/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleRename).toHaveBeenCalledWith('s-1', 'Doanh thu Q1 mới');
    });
  });

  it('confirms and calls onDeleteSession', () => {
    const handleDelete = vi.fn();
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        canChat={true}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={handleDelete}
        onRenameSession={vi.fn()}
      />,
    );

    const deleteBtns = screen.getAllByTitle('Xóa đoạn chat');
    fireEvent.click(deleteBtns[0]);

    expect(screen.getByText('Xóa đoạn chat?')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle('Xác nhận xóa'));

    expect(handleDelete).toHaveBeenCalledWith('s-1');
  });

  it('renders empty state and allows creating new chat', () => {
    const handleNewChat = vi.fn();
    render(
      <ChatHistorySection
        sessions={[]}
        activeSessionId={null}
        loadingSessions={false}
        canChat={true}
        onSelectSession={vi.fn()}
        onNewChat={handleNewChat}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />,
    );

    expect(screen.getByText('Chưa có đoạn chat')).toBeInTheDocument();
    const startBtn = screen.getByRole('button', { name: /Bắt đầu chat/i });
    fireEvent.click(startBtn);

    expect(handleNewChat).toHaveBeenCalledTimes(1);
  });

  it('returns null when canChat is false', () => {
    const { container } = render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        canChat={false}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />,
    );

    expect(container.firstChild).toBeNull();
  });
});
