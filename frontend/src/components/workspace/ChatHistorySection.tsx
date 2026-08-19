'use client';

import { Check, Edit2, MessageSquare, Plus, Search, Trash2, X } from 'lucide-react';
import React, { useMemo, useState } from 'react';

import type { ChatSessionItem } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

import { SectionLabel } from './shared';

interface ChatHistorySectionProps {
  sessions: ChatSessionItem[];
  activeSessionId: string | null;
  loadingSessions: boolean;
  canChat: boolean;
  onSelectSession?: (sessionId: string) => void;
  onNewChat?: () => void;
  onDeleteSession?: (sessionId: string) => void;
  onRenameSession?: (sessionId: string, newTitle: string) => Promise<void> | void;
}

export function ChatHistorySection({
  sessions,
  activeSessionId,
  loadingSessions,
  canChat,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
}: ChatHistorySectionProps) {
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const filteredSessions = useMemo(() => {
    if (!search.trim()) return sessions;
    const query = search.toLowerCase();
    return sessions.filter((s) => s.title.toLowerCase().includes(query));
  }, [sessions, search]);

  const handleStartRename = (e: React.MouseEvent, session: ChatSessionItem) => {
    e.stopPropagation();
    setEditingId(session.id);
    setEditTitle(session.title);
    setDeletingId(null);
  };

  const handleSaveRename = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (editTitle.trim() && onRenameSession) {
      await onRenameSession(sessionId, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
    setEditTitle('');
  };

  const handleDeleteClick = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setDeletingId(sessionId);
    setEditingId(null);
  };

  const handleConfirmDelete = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (onDeleteSession) {
      onDeleteSession(sessionId);
    }
    setDeletingId(null);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingId(null);
  };

  if (!canChat) return null;

  return (
    <div className="flex min-h-0 max-h-64 flex-col border-t border-sidebar-border px-3 pt-3">
      {/* Header */}
      <div className="mb-1.5 flex items-center justify-between px-1">
        <div className="flex items-center gap-1.5">
          <SectionLabel>Lịch sử trò chuyện</SectionLabel>
          {sessions.length > 0 && (
            <span className="rounded-full bg-sidebar-accent px-1.5 py-0.2 text-[9px] font-mono text-sidebar-foreground/70">
              {sessions.length}
            </span>
          )}
        </div>
        {onNewChat && (
          <button
            type="button"
            onClick={onNewChat}
            className="rounded p-1 text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground cursor-pointer"
            aria-label="Tạo cuộc trò chuyện mới"
            title="Tạo cuộc trò chuyện mới"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Quick Search */}
      {sessions.length >= 3 && (
        <div className="mb-2 px-1">
          <div className="relative flex items-center">
            <Search className="absolute left-2 h-3 w-3 text-sidebar-foreground/40" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm kiếm hội thoại..."
              className="w-full rounded-md border border-sidebar-border bg-sidebar-accent/50 py-1 pl-6.5 pr-2 text-xs text-sidebar-foreground placeholder:text-sidebar-foreground/40 focus:border-sidebar-ring focus:outline-none"
            />
          </div>
        </div>
      )}

      {/* Session List */}
      <div className="flex-1 space-y-0.5 overflow-y-auto pb-1">
        {loadingSessions ? (
          <div className="space-y-1.5 p-1">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-8 rounded bg-sidebar-accent/50 animate-pulse" />
            ))}
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="px-2 py-4 text-center">
            <p className="text-[11px] text-sidebar-foreground/50">
              {search ? 'Không tìm thấy cuộc trò chuyện' : 'Chưa có đoạn chat nào'}
            </p>
            {onNewChat && !search && (
              <button
                type="button"
                onClick={onNewChat}
                className="mt-1.5 text-[11px] font-medium text-sidebar-primary hover:underline cursor-pointer"
              >
                + Bắt đầu trò chuyện mới
              </button>
            )}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            const isEditing = editingId === session.id;
            const isDeleting = deletingId === session.id;

            return (
              <div
                key={session.id}
                data-active={isActive ? 'true' : 'false'}
                onClick={() => onSelectSession?.(session.id)}
                className={cn(
                  'group relative flex cursor-pointer items-center justify-between rounded-md px-2.5 py-1.5 text-xs transition-colors',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-foreground font-medium'
                    : 'text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                )}
              >
                {/* Left: icon + title */}
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <MessageSquare
                    className={cn(
                      'h-3.5 w-3.5 shrink-0',
                      isActive ? 'text-sidebar-primary' : 'text-sidebar-foreground/45',
                    )}
                  />
                  {isEditing ? (
                    <input
                      type="text"
                      autoFocus
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') void handleSaveRename(e as any, session.id);
                        if (e.key === 'Escape') handleCancelRename(e as any);
                      }}
                      className="w-full rounded border border-sidebar-ring bg-sidebar px-1 py-0.5 text-xs text-sidebar-foreground focus:outline-none"
                    />
                  ) : isDeleting ? (
                    <span className="text-[11px] text-destructive truncate">
                      Xác nhận xóa đoạn chat?
                    </span>
                  ) : (
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs">{session.title}</p>
                      <div className="flex items-center gap-1.5 text-[10px] text-sidebar-foreground/45">
                        <span>{formatRelativeTime(session.updated_at || session.created_at)}</span>
                        {session.message_count !== undefined && session.message_count > 0 && (
                          <>
                            <span>·</span>
                            <span>{session.message_count} tin nhắn</span>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Right: Actions */}
                <div className="ml-1 flex shrink-0 items-center gap-0.5">
                  {isEditing ? (
                    <>
                      <button
                        type="button"
                        onClick={(e) => void handleSaveRename(e, session.id)}
                        className="rounded p-0.5 text-emerald-500 hover:bg-sidebar-accent cursor-pointer"
                        title="Lưu"
                        aria-label="Lưu tên mới"
                      >
                        <Check className="h-3 w-3" />
                      </button>
                      <button
                        type="button"
                        onClick={handleCancelRename}
                        className="rounded p-0.5 text-sidebar-foreground/50 hover:bg-sidebar-accent cursor-pointer"
                        title="Hủy"
                        aria-label="Hủy đổi tên"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </>
                  ) : isDeleting ? (
                    <>
                      <button
                        type="button"
                        onClick={(e) => handleConfirmDelete(e, session.id)}
                        className="rounded bg-destructive/10 px-1.5 py-0.5 text-[10px] font-bold text-destructive hover:bg-destructive/20 cursor-pointer"
                        title="Xóa vĩnh viễn"
                        aria-label="Xác nhận xóa"
                      >
                        Xóa
                      </button>
                      <button
                        type="button"
                        onClick={handleCancelDelete}
                        className="rounded p-0.5 text-sidebar-foreground/50 hover:bg-sidebar-accent cursor-pointer"
                        title="Hủy"
                        aria-label="Hủy xóa"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </>
                  ) : (
                    <div className="flex opacity-0 transition-opacity group-hover:opacity-100 items-center gap-0.5">
                      {onRenameSession && (
                        <button
                          type="button"
                          onClick={(e) => handleStartRename(e, session)}
                          className="rounded p-1 text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent cursor-pointer"
                          title="Đổi tên"
                          aria-label={`Đổi tên ${session.title}`}
                        >
                          <Edit2 className="h-3 w-3" />
                        </button>
                      )}
                      {onDeleteSession && (
                        <button
                          type="button"
                          onClick={(e) => handleDeleteClick(e, session.id)}
                          className="rounded p-1 text-sidebar-foreground/50 hover:text-destructive hover:bg-sidebar-accent cursor-pointer"
                          title="Xóa"
                          aria-label={`Xóa ${session.title}`}
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
