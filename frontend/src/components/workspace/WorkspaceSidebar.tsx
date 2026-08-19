'use client';

import { useState } from 'react';
import {
  Bot,
  BookMarked,
  Building2,
  ChevronDown,
  ChevronLeft,
  Compass,
  LogOut,
  MessageSquare,
  Moon,
  PanelLeftClose,
  Plus,
  Settings,
  Sun,
  Trash2,
  Upload,
  Users,
} from 'lucide-react';

import type { ChatSessionItem } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useWorkspace } from '@/context/WorkspaceContext';

import { ChatHistorySection } from './ChatHistorySection';
import { EngineIcon, engineLabels, SectionLabel, type ViewId, type WorkspaceDatabase } from './shared';

interface WorkspaceSidebarProps {
  databases: WorkspaceDatabase[];
  activeDbId: string | null;
  view: ViewId;
  theme: 'light' | 'dark';
  pendingCount: number;
  collapsed: boolean;
  userName?: string;
  chatSessions?: ChatSessionItem[];
  activeChatSessionId?: string | null;
  loadingChatSessions?: boolean;
  canChat?: boolean;
  onSelectView: (view: ViewId) => void;
  onToggleCollapse: () => void;
  onToggleTheme: () => void;
  onSelectDatabase: (id: string) => void;
  onRemoveDatabase: (id: string) => void;
  onConnectDatabase: () => void;
  onOpenSettings: () => void;
  onOpenWorkspaceManagement?: () => void;
  onLogout?: () => void;
  onSelectChatSession?: (sessionId: string) => void;
  onNewChatSession?: () => void;
  onDeleteChatSession?: (sessionId: string) => void;
  onRenameChatSession?: (sessionId: string, newTitle: string) => Promise<void> | void;
}

const navItems: { id: ViewId; label: string; icon: typeof Bot }[] = [
  { id: 'ai-studio', label: 'AI Studio', icon: Bot },
  { id: 'catalog', label: 'Metrics Catalog', icon: BookMarked },
  { id: 'explorer', label: 'Metric Explorer', icon: Compass },
  { id: 'export', label: 'Export Playground', icon: Upload },
];

export function WorkspaceSidebar({
  databases,
  activeDbId,
  view,
  theme,
  pendingCount,
  collapsed,
  userName,
  chatSessions = [],
  activeChatSessionId = null,
  loadingChatSessions = false,
  canChat = false,
  onSelectView,
  onToggleCollapse,
  onToggleTheme,
  onSelectDatabase,
  onRemoveDatabase,
  onConnectDatabase,
  onOpenSettings,
  onOpenWorkspaceManagement,
  onLogout,
  onSelectChatSession,
  onNewChatSession,
  onDeleteChatSession,
  onRenameChatSession,
}: WorkspaceSidebarProps) {
  const { workspaces, currentWorkspace, role, switchWorkspace } = useWorkspace();
  const [wsDropdownOpen, setWsDropdownOpen] = useState(false);

  if (collapsed) {
    return (
      <aside className="flex h-full w-14 flex-col items-center gap-4 border-r border-sidebar-border bg-sidebar py-4">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="rounded-md p-2 text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
          aria-label="Expand sidebar"
        >
          <ChevronLeft className="h-4 w-4 rotate-180" />
        </button>
        {onOpenWorkspaceManagement && (
          <button
            type="button"
            onClick={onOpenWorkspaceManagement}
            className="rounded-md p-2 text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
            title="Quản lý Workspace & Thành viên"
            aria-label="Manage workspace"
          >
            <Building2 className="h-4 w-4" />
          </button>
        )}
        <nav className="flex flex-1 flex-col gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectView(item.id)}
                aria-label={item.label}
                aria-current={view === item.id ? 'page' : undefined}
                className={cn(
                  'relative rounded-md p-2 transition-colors',
                  view === item.id
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                    : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground',
                )}
              >
                <Icon className="h-4 w-4" />
              </button>
            );
          })}
          {canChat && onNewChatSession && (
            <button
              type="button"
              onClick={() => {
                onSelectView('ai-studio');
                onNewChatSession();
              }}
              className="relative rounded-md p-2 text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground cursor-pointer"
              aria-label="Tạo cuộc trò chuyện mới"
              title="Tạo cuộc trò chuyện mới"
            >
              <MessageSquare className="h-4 w-4" />
              {chatSessions.length > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-sidebar-primary text-[9px] font-mono font-bold text-sidebar-primary-foreground">
                  {chatSessions.length}
                </span>
              )}
            </button>
          )}
        </nav>
        <button
          type="button"
          onClick={onToggleTheme}
          className="rounded-md p-2 text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </aside>
    );
  }

  return (
    <aside className="flex h-full w-72 flex-col border-r border-sidebar-border bg-sidebar">
      {/* Brand */}
      <div className="flex items-center justify-between px-4 py-4">
        <div className="flex items-baseline gap-1.5">
          <span className="font-display text-2xl tracking-tight text-sidebar-foreground">S206</span>
          <span className="font-mono text-[10px] text-sidebar-foreground/50">SEMANTIC</span>
        </div>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="rounded-md p-1.5 text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
          aria-label="Collapse sidebar"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>

      {/* Workspace Switcher & RBAC */}
      <div className="relative px-3 pb-2">
        <div className="flex items-center gap-2 rounded-lg border border-sidebar-border bg-sidebar-accent/50 p-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
            <Building2 className="h-3.5 w-3.5" />
          </div>
          <div
            className="min-w-0 flex-1 cursor-pointer"
            onClick={() => setWsDropdownOpen(!wsDropdownOpen)}
          >
            <div className="flex items-center gap-1">
              <span className="truncate text-xs font-semibold text-sidebar-foreground">
                {currentWorkspace?.name || 'Workspace'}
              </span>
              <ChevronDown className="h-3 w-3 shrink-0 text-sidebar-foreground/50" />
            </div>
            <p className="truncate font-mono text-[10px] text-sidebar-foreground/50 capitalize">
              {role ? role.replace('_', ' ') : 'Member'}
            </p>
          </div>
          {onOpenWorkspaceManagement && (
            <button
              type="button"
              onClick={onOpenWorkspaceManagement}
              className="rounded p-1 text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground cursor-pointer"
              title="Quản lý Workspace & Thành viên"
              aria-label="Manage workspace"
            >
              <Users className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {wsDropdownOpen && (
          <div className="absolute left-3 right-3 top-full z-50 mt-1 rounded-lg border border-sidebar-border bg-card p-1 shadow-lg">
            <div className="flex items-center justify-between px-2 py-1">
              <p className="font-mono text-[10px] uppercase text-muted-foreground">
                Workspaces ({workspaces.length})
              </p>
              {onOpenWorkspaceManagement && (
                <button
                  type="button"
                  onClick={() => {
                    setWsDropdownOpen(false);
                    onOpenWorkspaceManagement();
                  }}
                  className="font-mono text-[10px] text-primary hover:underline cursor-pointer"
                >
                  Quản lý
                </button>
              )}
            </div>
            {workspaces.map((ws) => (
              <button
                key={ws.id}
                type="button"
                onClick={() => {
                  switchWorkspace(ws.id);
                  setWsDropdownOpen(false);
                }}
                className={cn(
                  'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition-colors cursor-pointer',
                  ws.id === currentWorkspace?.id
                    ? 'bg-primary text-primary-foreground font-medium'
                    : 'text-foreground hover:bg-accent',
                )}
              >
                <span className="truncate">{ws.name}</span>
                <span className="font-mono text-[10px] opacity-75 capitalize">{ws.role}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-0.5 px-3 py-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = view === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectView(item.id)}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'group flex items-center gap-3 rounded-md px-3 py-2 text-left transition-colors',
                active
                  ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                  : 'text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-foreground',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 text-sm">{item.label}</span>
              {item.id === 'catalog' && pendingCount > 0 && (
                <span
                  className={cn(
                    'rounded-full px-1.5 py-0.5 font-mono text-[10px]',
                    active ? 'bg-sidebar-primary-foreground/20' : 'bg-sidebar-accent text-sidebar-foreground',
                  )}
                >
                  {pendingCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Chat History */}
      {canChat && (
        <ChatHistorySection
          sessions={chatSessions}
          activeSessionId={activeChatSessionId}
          loadingSessions={loadingChatSessions}
          canChat={canChat}
          onSelectSession={onSelectChatSession}
          onNewChat={onNewChatSession}
          onDeleteSession={onDeleteChatSession}
          onRenameSession={onRenameChatSession}
        />
      )}

      {/* Data Sources */}
      <div className="flex min-h-0 flex-1 flex-col px-3 pt-4">
        <div className="mb-2 flex items-center justify-between px-1">
          <SectionLabel>Data Sources</SectionLabel>
          <button
            type="button"
            onClick={onConnectDatabase}
            className="rounded p-1 text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground cursor-pointer"
            aria-label="Connect database"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto pb-2">
          {databases.map((db) => {
            const active = db.id === activeDbId;
            return (
              <div
                key={db.id}
                data-active={active ? 'true' : 'false'}
                className={cn(
                  'group cursor-pointer rounded-md border px-3 py-2 transition-colors',
                  active
                    ? 'border-sidebar-border bg-sidebar-accent'
                    : 'border-transparent hover:bg-sidebar-accent/60',
                )}
                onClick={() => onSelectDatabase(db.id)}
              >
                <div className="flex items-center gap-2">
                  <span
                    data-testid="db-status-dot"
                    className={cn(
                      'h-1.5 w-1.5 shrink-0 rounded-full',
                      db.status === 'connected'
                        ? 'bg-emerald-500'
                        : db.status === 'error'
                          ? 'bg-destructive'
                          : 'bg-muted-foreground/50',
                    )}
                  />
                  <EngineIcon engine={db.engine} className="h-3.5 w-3.5 shrink-0 text-sidebar-foreground/60" />
                  <span className="flex-1 truncate font-mono text-[13px] text-sidebar-foreground">{db.name}</span>
                  {databases.length > 1 && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemoveDatabase(db.id);
                      }}
                      className="opacity-0 transition-opacity group-hover:opacity-100 cursor-pointer"
                      aria-label={`Remove ${db.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-sidebar-foreground/50 hover:text-destructive" />
                    </button>
                  )}
                </div>
                <p className="mt-1 pl-[26px] font-mono text-[10px] text-sidebar-foreground/45">
                  {engineLabels[db.engine]} · {db.tables} tables
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-sidebar-border px-3 py-3">
        <button
          type="button"
          onClick={onOpenSettings}
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground cursor-pointer"
        >
          <Settings className="h-4 w-4" />
          Settings
        </button>
        <button
          type="button"
          onClick={onToggleTheme}
          className="h-8 w-8 rounded-md text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent cursor-pointer"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
      {userName && (
        <div className="flex items-center justify-between border-t border-sidebar-border px-3 py-2">
          <span className="truncate text-xs font-medium text-sidebar-foreground">{userName}</span>
          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              className="rounded p-1 text-sidebar-foreground/50 transition-colors hover:text-destructive cursor-pointer"
              title="Đăng xuất"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      )}
    </aside>
  );
}
