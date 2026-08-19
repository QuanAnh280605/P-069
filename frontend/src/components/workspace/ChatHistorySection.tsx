'use client';

import React, { useMemo, useState } from 'react';
import {
  Check,
  Edit2,
  MessageSquare,
  MessageSquarePlus,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from 'lucide-react';

import type { ChatSessionItem } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { SectionLabel } from './shared';

export interface ChatHistorySectionProps {
  sessions?: ChatSessionItem[];
  activeSessionId?: string | null;
  loadingSessions?: boolean;
  canChat?: boolean;
  onSelectSession?: (sessionId: string) => void;
  onNewChat?: () => void;
  onDeleteSession?: (sessionId: string) => void;
  onRenameSession?: (sessionId: string, newTitle: string) => Promise<void> | void;
}

export function ChatHistorySection({
  sessions = [],
  activeSessionId = null,
  loadingSessions = false,
  canChat = true,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
}: ChatHistorySectionProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase().trim();
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, searchQuery]);

  if (!canChat) return null;

  const handleStartEdit = (session: ChatSessionItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(session.id);
    setDraftTitle(session.title);
    setDeletingId(null);
  };

  const handleSaveEdit = async (sessionId: string, e?: React.MouseEvent | React.FormEvent) => {
    e?.stopPropagation();
    if (!draftTitle.trim()) {
      setEditingId(null);
      return;
    }
    setIsSavingEdit(true);
    try {
      await onRenameSession?.(sessionId, draftTitle.trim());
      setEditingId(null);
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleCancelEdit = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingId(null);
  };

  const handleStartDelete = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingId(sessionId);
    setEditingId(null);
  };

  const handleConfirmDelete = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onDeleteSession?.(sessionId);
    setDeletingId(null);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingId(null);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col px-3 pt-3">
      {/* Header */}
      <div className="mb-1.5 flex items-center justify-between px-1">
        <div className="flex items-center gap-1.5">
          <SectionLabel>Lịch sử trò chuyện</SectionLabel>
          {sessions.length > 0 && (
            <span className="rounded-full bg-sidebar-accent px-1.5 py-0.5 font-mono text-[10px] text-sidebar-foreground/70">
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

      {/* Search Input (visible when sessions >= 3) */}
      {sessions.length >= 3 && (
        <div className="relative mb-2 px-1">
          <Search className="pointer-events-none absolute left-3 top-2 h-3 w-3 text-sidebar-foreground/40" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm đoạn chat..."
            className="w-full rounded-md border border-sidebar-border bg-sidebar-accent/40 py-1 pl-7 pr-6 font-sans text-xs text-sidebar-foreground placeholder:text-sidebar-foreground/40 outline-none focus:border-sidebar-ring focus:bg-sidebar-accent/80 transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-2 text-sidebar-foreground/40 hover:text-sidebar-foreground cursor-pointer"
              aria-label="Clear search"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      )}

      {/* Sessions List */}
      <div className="flex-1 space-y-1 overflow-y-auto pb-2">
        {loadingSessions && sessions.length === 0 && (
          <div className="space-y-1 px-1 py-1">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 animate-pulse rounded-md bg-sidebar-accent/50" />
            ))}
          </div>
        )}

        {!loadingSessions && sessions.length === 0 && (
          <div className="rounded-md border border-dashed border-sidebar-border px-2 py-4 text-center">
            <MessageSquarePlus className="mx-auto h-4 w-4 text-sidebar-foreground/40 mb-1" />
            <p className="font-sans text-xs text-sidebar-foreground/60">Chưa có đoạn chat</p>
            {onNewChat && (
              <button
                type="button"
                onClick={onNewChat}
                className="mt-2 inline-flex items-center gap-1 rounded bg-sidebar-primary px-2.5 py-1 font-sans text-[11px] font-medium text-sidebar-primary-foreground transition-opacity hover:opacity-90 cursor-pointer"
              >
                <Plus className="h-3 w-3" />
                <span>Bắt đầu chat</span>
              </button>
            )}
          </div>
        )}

        {!loadingSessions && sessions.length > 0 && filteredSessions.length === 0 && (
          <div className="px-2 py-4 text-center text-xs text-sidebar-foreground/50">
            Không tìm thấy đoạn chat phù hợp
          </div>
        )}

        {filteredSessions.map((session) => {
          const isActive = activeSessionId === session.id;
          const isEditing = editingId === session.id;
          const isDeleting = deletingId === session.id;
          const timeLabel = formatRelativeTime(session.updated_at || session.created_at);

          return (
            <div
              key={session.id}
              data-active={isActive ? 'true' : 'false'}
              onClick={() => {
                if (!isEditing && !isDeleting) {
                  onSelectSession?.(session.id);
                }
              }}
              className={cn(
                'group relative cursor-pointer rounded-md border px-2.5 py-1.5 text-left transition-colors',
                isActive
                  ? 'border-sidebar-border bg-sidebar-accent text-sidebar-foreground font-medium'
                  : 'border-transparent text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
              )}
            >
              {isEditing ? (
                <div className="space-y-1" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="text"
                    autoFocus
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void handleSaveEdit(session.id, e);
                      if (e.key === 'Escape') handleCancelEdit(e as unknown as React.MouseEvent);
                    }}
                    placeholder="Tên đoạn chat..."
                    className="w-full rounded border border-sidebar-ring bg-sidebar px-1.5 py-0.5 font-sans text-xs text-sidebar-foreground outline-none"
                  />
                  <div className="flex items-center justify-end gap-1">
                    <button
                      type="button"
                      disabled={isSavingEdit}
                      onClick={(e) => void handleSaveEdit(session.id, e)}
                      className="inline-flex items-center gap-0.5 rounded bg-sidebar-primary px-1.5 py-0.5 font-sans text-[10px] font-medium text-sidebar-primary-foreground hover:opacity-90 disabled:opacity-50 cursor-pointer"
                    >
                      <Check className="h-2.5 w-2.5" /> Lưu
                    </button>
                    <button
                      type="button"
                      onClick={handleCancelEdit}
                      className="rounded px-1.5 py-0.5 font-sans text-[10px] text-sidebar-foreground/60 hover:text-sidebar-foreground cursor-pointer"
                    >
                      Hủy
                    </button>
                  </div>
                </div>
              ) : isDeleting ? (
                <div
                  className="flex items-center justify-between gap-1 rounded bg-destructive/10 p-1 text-xs"
                  onClick={(e) => e.stopPropagation()}
                >
                  <span className="text-[11px] font-medium text-destructive">Xóa đoạn chat?</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={(e) => handleConfirmDelete(session.id, e)}
                      className="rounded bg-destructive px-1.5 py-0.5 text-[10px] font-bold text-white hover:opacity-90 cursor-pointer"
                      title="Xác nhận xóa"
                    >
                      Xóa
                    </button>
                    <button
                      type="button"
                      onClick={handleCancelDelete}
                      className="rounded px-1 py-0.5 text-[10px] text-sidebar-foreground/60 hover:text-sidebar-foreground cursor-pointer"
                      title="Hủy"
                    >
                      Hủy
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <MessageSquare
                        className={cn(
                          'h-3.5 w-3.5 shrink-0',
                          isActive ? 'text-sidebar-primary' : 'text-sidebar-foreground/50',
                        )}
                      />
                      <span className="truncate font-sans text-xs font-medium" title={session.title}>
                        {session.title}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1.5 pl-5 font-mono text-[10px] text-sidebar-foreground/50">
                      <span>{timeLabel}</span>
                      {session.message_count !== undefined && session.message_count > 0 && (
                        <>
                          <span>·</span>
                          <span>{session.message_count} tin</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Actions on hover */}
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    {onRenameSession && (
                      <button
                        type="button"
                        onClick={(e) => handleStartEdit(session, e)}
                        className="rounded p-0.5 text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors cursor-pointer"
                        title="Đổi tên đoạn chat"
                        aria-label={`Đổi tên ${session.title}`}
                      >
                        <Pencil className="h-3 w-3" />
                      </button>
                    )}
                    {onDeleteSession && (
                      <button
                        type="button"
                        onClick={(e) => handleStartDelete(session.id, e)}
                        className="rounded p-0.5 text-sidebar-foreground/50 hover:text-destructive transition-colors cursor-pointer"
                        title="Xóa đoạn chat"
                        aria-label={`Xóa ${session.title}`}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
