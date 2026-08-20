'use client';

import {
  Check,
  ChevronDown,
  History,
  MessageSquare,
  MessageSquarePlus,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';

import { ChatSessionItem } from '@/lib/api';

interface ChatSessionSwitcherProps {
  sessions: ChatSessionItem[];
  activeSessionId: string | null;
  loadingSessions: boolean;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void | Promise<void>;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, newTitle: string) => Promise<void> | void;
}

export function ChatSessionSwitcher({
  sessions,
  activeSessionId,
  loadingSessions,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onRenameSession,
}: ChatSessionSwitcherProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [isStartingNewChat, setIsStartingNewChat] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const newChatLockRef = useRef(false);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId) || null,
    [sessions, activeSessionId]
  );

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase().trim();
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, searchQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setEditingId(null);
        setDeletingId(null);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [isOpen]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      const timer = setTimeout(() => searchInputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

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
      await onRenameSession(sessionId, draftTitle.trim());
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
    onDeleteSession(sessionId);
    setDeletingId(null);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingId(null);
  };

  const handleNewChat = () => {
    if (newChatLockRef.current) return;
    newChatLockRef.current = true;
    setIsStartingNewChat(true);
    setIsOpen(false);
    const unlock = () => {
      newChatLockRef.current = false;
      setIsStartingNewChat(false);
    };
    try {
      void Promise.resolve(onNewChat()).then(unlock, unlock);
    } catch {
      unlock();
    }
  };

  return (
    <div ref={containerRef} className="relative flex items-center gap-2">
      {/* 1. Main Session Selector Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`group flex items-center gap-2 rounded-xl border px-3 py-1.5 text-xs font-semibold shadow-2xs transition-all cursor-pointer ${
          isOpen
            ? 'border-indigo-400 bg-indigo-50/80 text-indigo-950 dark:border-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-200 ring-2 ring-indigo-500/20'
            : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-200 dark:hover:border-indigo-800 dark:hover:bg-slate-800/80'
        }`}
        title="Chọn hoặc tìm kiếm cuộc trò chuyện"
        aria-expanded={isOpen}
      >
        <div className="flex h-5 w-5 items-center justify-center rounded-md bg-indigo-50 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400">
          <MessageSquare className="h-3 w-3" />
        </div>

        <span className="max-w-[160px] md:max-w-[220px] truncate text-left">
          {activeSession ? activeSession.title : 'Cuộc trò chuyện mới'}
        </span>

        {sessions.length > 0 && (
          <span className="rounded-full bg-slate-100 px-1.5 py-0.2 text-[10px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            {sessions.length}
          </span>
        )}

        <ChevronDown
          className={`h-3.5 w-3.5 text-slate-400 transition-transform duration-200 ${
            isOpen ? 'rotate-180 text-indigo-600 dark:text-indigo-400' : 'group-hover:text-slate-600 dark:group-hover:text-slate-300'
          }`}
        />
      </button>

      {/* 2. Direct "+ Cuộc trò chuyện mới" Button */}
      <button
        type="button"
        onClick={() => {
          handleNewChat();
        }}
        disabled={isStartingNewChat}
        className="group flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm shadow-indigo-500/20 hover:shadow-md hover:shadow-indigo-500/30 hover:brightness-105 active:scale-95 transition-all cursor-pointer shrink-0"
        title="Tạo cuộc trò chuyện mới"
      >
        <Plus className="h-3.5 w-3.5 transition-transform group-hover:rotate-90" />
        <span className="hidden sm:inline">Cuộc trò chuyện mới</span>
      </button>

      {/* 3. Floating Glassmorphism Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 md:w-96 rounded-2xl border border-slate-200/90 bg-white/95 backdrop-blur-md p-2.5 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-150 dark:border-slate-800 dark:bg-[#0E1526]/95 dark:shadow-black/60">
          {/* Header of dropdown */}
          <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800/80 px-1">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 dark:text-slate-200">
              <History className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
              <span>Lịch sử trò chuyện</span>
              <span className="rounded-full bg-slate-100 px-1.5 py-0.2 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {sessions.length}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-all cursor-pointer"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Search Bar inside dropdown */}
          <div className="pt-2">
            <div className="relative flex items-center">
              <Search className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm kiếm hội thoại..."
                className="w-full rounded-xl border border-slate-200 bg-slate-50/90 py-1.5 pl-8 pr-7 text-xs text-slate-800 placeholder-slate-400 outline-none focus:border-indigo-500 focus:bg-white focus:ring-1 focus:ring-indigo-500 dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:border-indigo-500 dark:focus:bg-slate-900 transition-all"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>

          {/* Session Cards List */}
          <div className="mt-2 max-h-72 space-y-1 overflow-y-auto py-1 pr-0.5">
            {/* Loading Skeleton */}
            {loadingSessions && sessions.length === 0 && (
              <div className="space-y-1.5 py-2">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800/60"
                  />
                ))}
              </div>
            )}

            {/* Empty State: No sessions */}
            {!loadingSessions && sessions.length === 0 && (
              <div className="py-6 px-2 text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-500 dark:bg-indigo-950/50 dark:text-indigo-400 mb-2">
                  <MessageSquarePlus className="h-5 w-5" />
                </div>
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Chưa có cuộc trò chuyện nào
                </p>
                <button
                  type="button"
                  onClick={handleNewChat}
                  disabled={isStartingNewChat}
                  className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50/60 px-3 py-1.5 text-[11px] font-bold text-indigo-600 hover:bg-indigo-100 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-400 dark:hover:bg-indigo-900/50 transition-all cursor-pointer"
                >
                  <Sparkles className="h-3 w-3" />
                  <span>Bắt đầu cuộc trò chuyện mới</span>
                </button>
              </div>
            )}

            {/* Empty Search */}
            {!loadingSessions && sessions.length > 0 && filteredSessions.length === 0 && (
              <div className="py-6 text-center text-xs text-slate-400">
                <Search className="mx-auto h-4 w-4 mb-1 opacity-40" />
                <p className="font-medium">Không tìm thấy hội thoại</p>
                <p className="text-[10px] text-slate-400 mt-0.5">&quot;{searchQuery}&quot;</p>
              </div>
            )}

            {/* Sessions */}
            {filteredSessions.map((session) => {
              const isActive = activeSessionId === session.id;
              const isEditing = editingId === session.id;
              const isDeleting = deletingId === session.id;
              const timeLabel = formatRelativeTime(session.updated_at || session.created_at);

              return (
                <div
                  key={session.id}
                  onClick={() => {
                    if (!isEditing && !isDeleting) {
                      onSelectSession(session.id);
                      setIsOpen(false);
                    }
                  }}
                  className={`group relative rounded-xl border p-2 text-left transition-all cursor-pointer ${
                    isActive
                      ? 'border-indigo-400 bg-indigo-50/90 shadow-2xs dark:border-indigo-800 dark:bg-indigo-950/50'
                      : 'border-slate-100 bg-white/70 hover:border-slate-200 hover:bg-slate-50 dark:border-slate-800/70 dark:bg-slate-900/40 dark:hover:border-slate-700 dark:hover:bg-slate-800/50'
                  }`}
                >
                  {/* Left Active Indicator */}
                  {isActive && (
                    <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-gradient-to-b from-indigo-500 to-purple-600" />
                  )}

                  {/* Inline Edit Mode */}
                  {isEditing ? (
                    <div
                      className="space-y-1.5 pl-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="text"
                        autoFocus
                        value={draftTitle}
                        onChange={(e) => setDraftTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveEdit(session.id, e);
                          if (e.key === 'Escape') handleCancelEdit(e as unknown as React.MouseEvent);
                        }}
                        placeholder="Tên cuộc trò chuyện..."
                        className="w-full rounded-lg border border-indigo-400 bg-white px-2 py-1 text-xs text-slate-900 outline-none focus:ring-1 focus:ring-indigo-500 dark:border-indigo-600 dark:bg-slate-950 dark:text-slate-100"
                      />
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          disabled={isSavingEdit}
                          onClick={(e) => handleSaveEdit(session.id, e)}
                          className="inline-flex items-center gap-1 rounded bg-indigo-600 px-2 py-0.5 text-[10px] font-bold text-white hover:bg-indigo-700 disabled:opacity-50 cursor-pointer"
                        >
                          <Check className="h-2.5 w-2.5" /> Lưu
                        </button>
                        <button
                          type="button"
                          onClick={handleCancelEdit}
                          className="rounded px-1.5 py-0.5 text-[10px] text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer"
                        >
                          Hủy
                        </button>
                      </div>
                    </div>
                  ) : isDeleting ? (
                    /* Inline Delete Confirmation */
                    <div
                      className="flex items-center justify-between rounded-lg bg-red-50 p-1.5 pl-2 text-xs dark:bg-red-950/40"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span className="text-[11px] font-medium text-red-700 dark:text-red-300">
                        Xóa đoạn chat này?
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={(e) => handleConfirmDelete(session.id, e)}
                          className="rounded bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white hover:bg-red-700 cursor-pointer"
                          title="Xác nhận xóa"
                        >
                          Xóa
                        </button>
                        <button
                          type="button"
                          onClick={handleCancelDelete}
                          className="rounded px-1.5 py-0.5 text-[10px] text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer"
                          title="Hủy"
                        >
                          Hủy
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* Normal Display Item */
                    <div className="flex items-start justify-between gap-1 pl-1">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <History
                            className={`h-3.5 w-3.5 shrink-0 ${
                              isActive
                                ? 'text-indigo-600 dark:text-indigo-400'
                                : 'text-slate-400 group-hover:text-slate-600 dark:text-slate-500 dark:group-hover:text-slate-300'
                            }`}
                          />
                          <span
                            className={`truncate text-xs font-semibold ${
                              isActive
                                ? 'text-indigo-950 dark:text-indigo-100'
                                : 'text-slate-700 group-hover:text-slate-900 dark:text-slate-200 dark:group-hover:text-white'
                            }`}
                            title={session.title}
                          >
                            {session.title}
                          </span>
                          {isActive && (
                            <span className="rounded bg-indigo-100 px-1 py-0.1 text-[9px] font-bold text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300 shrink-0">
                              Active
                            </span>
                          )}
                        </div>

                        <div className="mt-0.5 flex items-center gap-2 text-[10px] text-slate-400 dark:text-slate-500">
                          <span>{timeLabel}</span>
                          {session.message_count > 0 && (
                            <>
                              <span>•</span>
                              <span>{session.message_count} tin nhắn</span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Action buttons on hover */}
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        <button
                          type="button"
                          onClick={(e) => handleStartEdit(session, e)}
                          className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-indigo-600 dark:hover:bg-slate-800 dark:hover:text-indigo-400 transition-all cursor-pointer"
                          title="Đổi tên đoạn chat"
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleStartDelete(session.id, e)}
                          className="rounded p-1 text-slate-400 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400 transition-all cursor-pointer"
                          title="Xóa đoạn chat"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return 'Vừa xong';
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Vừa xong';
    if (diffMins < 60) return `${diffMins} phút trước`;
    if (diffHours < 24 && date.getDate() === now.getDate()) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    if (diffDays === 1 || (diffDays === 0 && date.getDate() !== now.getDate())) {
      return 'Hôm qua';
    }
    if (diffDays < 7) {
      return `${diffDays} ngày trước`;
    }
    return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
  } catch {
    return 'Vừa xong';
  }
}
