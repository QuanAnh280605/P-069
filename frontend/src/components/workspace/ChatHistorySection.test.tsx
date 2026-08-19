import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ChatSessionItem } from '@/lib/api';
import { ChatHistorySection } from './ChatHistorySection';

describe('ChatHistorySection', () => {
  afterEach(() => cleanup());

  const mockSessions: ChatSessionItem[] = [
    {
      id: 'session-1',
      db_id: 1,
      title: 'Doanh thu Q1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 3,
    },
    {
      id: 'session-2',
      db_id: 1,
      title: 'Khách hàng active',
      created_at: new Date(Date.now() - 3600000).toISOString(),
      updated_at: new Date(Date.now() - 3600000).toISOString(),
      message_count: 5,
    },
    {
      id: 'session-3',
      db_id: 1,
      title: 'Phân tích đơn hủy',
      created_at: new Date(Date.now() - 86400000).toISOString(),
      updated_at: new Date(Date.now() - 86400000).toISOString(),
      message_count: 1,
    },
  ];

  it('does not render if canChat is false', () => {
    const { container } = render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="session-1"
        loadingSessions={false}
        canChat={false}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders session items with titles and message counts', () => {
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="session-1"
        loadingSessions={false}
        canChat={true}
      />,
    );

    expect(screen.getByText('Lịch sử trò chuyện')).toBeInTheDocument();
    expect(screen.getByText('Doanh thu Q1')).toBeInTheDocument();
    expect(screen.getByText('Khách hàng active')).toBeInTheDocument();
    expect(screen.getByText('Phân tích đơn hủy')).toBeInTheDocument();
    expect(screen.getByText('3 tin nhắn')).toBeInTheDocument();
  });

  it('highlights the active session with data-active attribute', () => {
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="session-2"
        loadingSessions={false}
        canChat={true}
      />,
    );

    const activeItem = screen.getByText('Khách hàng active').closest('[data-active]');
    expect(activeItem).toHaveAttribute('data-active', 'true');

    const inactiveItem = screen.getByText('Doanh thu Q1').closest('[data-active]');
    expect(inactiveItem).toHaveAttribute('data-active', 'false');
  });

  it('calls onSelectSession when clicking a session item', () => {
    const handleSelect = vi.fn();
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="session-1"
        loadingSessions={false}
        canChat={true}
        onSelectSession={handleSelect}
      />,
    );

    fireEvent.click(screen.getByText('Khách hàng active'));
    expect(handleSelect).toHaveBeenCalledWith('session-2');
  });

  it('filters sessions using the search input when sessions >= 3', () => {
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="session-1"
        loadingSessions={false}
        canChat={true}
      />,
    );

    const searchInput = screen.getByPlaceholderText('Tìm kiếm hội thoại...');
    fireEvent.change(searchInput, { target: { value: 'Doanh thu' } });

    expect(screen.getByText('Doanh thu Q1')).toBeInTheDocument();
    expect(screen.queryByText('Khách hàng active')).not.toBeInTheDocument();
  });

  it('calls onNewChat when clicking the new chat button', () => {
    const handleNewChat = vi.fn();
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="session-1"
        loadingSessions={false}
        canChat={true}
        onNewChat={handleNewChat}
      />,
    );

    const newBtn = screen.getByLabelText('Tạo cuộc trò chuyện mới');
    fireEvent.click(newBtn);
    expect(handleNewChat).toHaveBeenCalledTimes(1);
  });

  it('allows renaming session inline', async () => {
    const handleRename = vi.fn();
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="session-1"
        loadingSessions={false}
        canChat={true}
        onRenameSession={handleRename}
      />,
    );

    const renameBtn = screen.getByLabelText('Đổi tên Doanh thu Q1');
    fireEvent.click(renameBtn);

    const input = screen.getByDisplayValue('Doanh thu Q1');
    fireEvent.change(input, { target: { value: 'Doanh thu năm 2026' } });

    const saveBtn = screen.getByLabelText('Lưu tên mới');
    fireEvent.click(saveBtn);

    expect(handleRename).toHaveBeenCalledWith('session-1', 'Doanh thu năm 2026');
  });

  it('shows delete confirmation and calls onDeleteSession on confirm', () => {
    const handleDelete = vi.fn();
    render(
      <ChatHistorySection
        sessions={mockSessions}
        activeSessionId="session-1"
        loadingSessions={false}
        canChat={true}
        onDeleteSession={handleDelete}
      />,
    );

    const deleteBtn = screen.getByLabelText('Xóa Doanh thu Q1');
    fireEvent.click(deleteBtn);

    expect(screen.getByText('Xác nhận xóa đoạn chat?')).toBeInTheDocument();

    const confirmBtn = screen.getByLabelText('Xác nhận xóa');
    fireEvent.click(confirmBtn);

    expect(handleDelete).toHaveBeenCalledWith('session-1');
  });
});
