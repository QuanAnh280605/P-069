'use client';

import { Bot, BookMarked, ChevronLeft, Compass, LogOut, Moon, PanelLeftClose, Plus, Settings, Sun, Trash2, Upload } from 'lucide-react';

import { cn } from '@/lib/utils';

import { EngineIcon, engineLabels, SectionLabel, type ViewId, type WorkspaceDatabase } from './shared';

interface WorkspaceSidebarProps {
  databases: WorkspaceDatabase[];
  activeDbId: string | null;
  view: ViewId;
  theme: 'light' | 'dark';
  pendingCount: number;
  collapsed: boolean;
  userName?: string;
  onSelectView: (view: ViewId) => void;
  onToggleCollapse: () => void;
  onToggleTheme: () => void;
  onSelectDatabase: (id: string) => void;
  onRemoveDatabase: (id: string) => void;
  onConnectDatabase: () => void;
  onOpenSettings: () => void;
  onLogout?: () => void;
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
  onSelectView,
  onToggleCollapse,
  onToggleTheme,
  onSelectDatabase,
  onRemoveDatabase,
  onConnectDatabase,
  onOpenSettings,
  onLogout,
}: WorkspaceSidebarProps) {
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

      {/* Data Sources */}
      <div className="flex min-h-0 flex-1 flex-col px-3 pt-4">
        <div className="mb-2 flex items-center justify-between px-1">
          <SectionLabel>Data Sources</SectionLabel>
          <button
            type="button"
            onClick={onConnectDatabase}
            className="rounded p-1 text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
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
                      className="opacity-0 transition-opacity group-hover:opacity-100"
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
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <Settings className="h-4 w-4" />
          Settings
        </button>
        <button
          type="button"
          onClick={onToggleTheme}
          className="h-8 w-8 rounded-md text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent"
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
              className="rounded p-1 text-sidebar-foreground/50 transition-colors hover:text-destructive"
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
