import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatSessionSwitcher } from '@/components/studio/ChatSessionSwitcher';
import { ChatSessionItem } from '@/lib/api';

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
];

describe('ChatSessionSwitcher', () => {
  beforeEach(() => {
    cleanup();
  });

  it('renders trigger button with active session title and count badge', () => {
    render(
      <ChatSessionSwitcher
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />
    );

    expect(screen.getByText('Doanh thu tháng 1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // 2 sessions badge
    expect(screen.getByRole('button', { name: /Cuộc trò chuyện mới/i })).toBeInTheDocument();
  });

  it('opens dropdown and shows all session items with message counts and search', () => {
    render(
      <ChatSessionSwitcher
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />
    );

    const trigger = screen.getByTitle('Chọn hoặc tìm kiếm cuộc trò chuyện');
    fireEvent.click(trigger);

    expect(screen.getByText('Lịch sử trò chuyện')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Tìm kiếm hội thoại/i)).toBeInTheDocument();
    expect(screen.getByText('Phân tích khách hàng mới')).toBeInTheDocument();
    expect(screen.getByText('4 tin nhắn')).toBeInTheDocument();
    expect(screen.getByText('2 tin nhắn')).toBeInTheDocument();
  });

  it('filters sessions by search input inside dropdown', () => {
    render(
      <ChatSessionSwitcher
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTitle('Chọn hoặc tìm kiếm cuộc trò chuyện'));

    const searchInput = screen.getByPlaceholderText(/Tìm kiếm hội thoại/i);
    fireEvent.change(searchInput, { target: { value: 'khách hàng' } });

    expect(screen.getByText('Phân tích khách hàng mới')).toBeInTheDocument();
    // 'Doanh thu tháng 1' in the dropdown list should be filtered out (only appears on the trigger button)
    expect(screen.queryByText('4 tin nhắn')).not.toBeInTheDocument();
  });

  it('allows renaming session inline inside dropdown', async () => {
    const handleRename = vi.fn().mockResolvedValue(undefined);
    render(
      <ChatSessionSwitcher
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={vi.fn()}
        onRenameSession={handleRename}
      />
    );

    fireEvent.click(screen.getByTitle('Chọn hoặc tìm kiếm cuộc trò chuyện'));

    const editBtns = screen.getAllByTitle('Đổi tên đoạn chat');
    fireEvent.click(editBtns[0]);

    const editInput = screen.getByPlaceholderText(/Tên cuộc trò chuyện/i) as HTMLInputElement;
    fireEvent.change(editInput, { target: { value: 'Doanh thu Q1 mới' } });

    const saveBtn = screen.getByRole('button', { name: /Lưu/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleRename).toHaveBeenCalledWith('s-1', 'Doanh thu Q1 mới');
    });
  });

  it('confirms and calls onDeleteSession inside dropdown', () => {
    const handleDelete = vi.fn();
    render(
      <ChatSessionSwitcher
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        onSelectSession={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteSession={handleDelete}
        onRenameSession={vi.fn()}
      />
    );

    fireEvent.click(screen.getByTitle('Chọn hoặc tìm kiếm cuộc trò chuyện'));

    const deleteBtns = screen.getAllByTitle('Xóa đoạn chat');
    fireEvent.click(deleteBtns[0]);

    expect(screen.getByText('Xóa đoạn chat này?')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle('Xác nhận xóa'));

    expect(handleDelete).toHaveBeenCalledWith('s-1');
  });

  it('calls onNewChat when clicking the new chat button', () => {
    const handleNewChat = vi.fn();
    render(
      <ChatSessionSwitcher
        sessions={mockSessions}
        activeSessionId="s-1"
        loadingSessions={false}
        onSelectSession={vi.fn()}
        onNewChat={handleNewChat}
        onDeleteSession={vi.fn()}
        onRenameSession={vi.fn()}
      />
    );

    const newChatBtn = screen.getByRole('button', { name: /Cuộc trò chuyện mới/i });
    fireEvent.click(newChatBtn);

    expect(handleNewChat).toHaveBeenCalledTimes(1);
  });
});
