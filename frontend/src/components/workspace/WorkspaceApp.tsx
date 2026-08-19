'use client';

import { cn } from '@/lib/utils';
import type { ViewId, WorkspaceDatabase } from '@/components/workspace/shared';
import { WorkspaceSidebar } from '@/components/workspace/WorkspaceSidebar';

interface WorkspaceAppProps {
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
  children: React.ReactNode;
}

export function WorkspaceApp({
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
  children,
}: WorkspaceAppProps) {
  return (
    <div
      role="region"
      aria-label="Workspace"
      className={cn(
        theme === 'dark' ? 'dark' : '',
        'flex h-screen w-full overflow-hidden bg-background text-foreground',
      )}
    >
      <WorkspaceSidebar
        databases={databases}
        activeDbId={activeDbId}
        view={view}
        theme={theme}
        pendingCount={pendingCount}
        collapsed={collapsed}
        userName={userName}
        onSelectView={onSelectView}
        onToggleCollapse={onToggleCollapse}
        onToggleTheme={onToggleTheme}
        onSelectDatabase={onSelectDatabase}
        onRemoveDatabase={onRemoveDatabase}
        onConnectDatabase={onConnectDatabase}
        onOpenSettings={onOpenSettings}
        onLogout={onLogout}
      />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
