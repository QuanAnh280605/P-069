'use client';

import type { AppNotification, ChatSessionItem } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { ViewId, WorkspaceDatabase } from '@/components/workspace/shared';
import { WorkspaceSidebar } from '@/components/workspace/WorkspaceSidebar';

interface WorkspaceAppProps {
  databases: WorkspaceDatabase[];
  activeDbId: string | null;
  view: ViewId;
  theme: 'light' | 'dark';
  pendingCount: number;
  pendingSchemaCount?: number;
  collapsed: boolean;
  userName?: string;
  chatSessions?: ChatSessionItem[];
  activeChatSessionId?: string | null;
  loadingChatSessions?: boolean;
  canChat?: boolean;
  chatMode?: 'data_assistant' | 'metric_studio';
  notifications?: AppNotification[];
  unreadNotifications?: number;
  onOpenCatalog?: () => void;
  onMarkAllNotificationsRead?: () => Promise<void> | void;
  onMarkNotificationRead?: (item: AppNotification) => Promise<void> | void;
  onSelectView: (view: ViewId) => void;
  onToggleCollapse: () => void;
  onToggleTheme: () => void;
  onSelectDatabase: (id: string) => void;
  onRemoveDatabase?: (id: string) => void;
  onConnectDatabase?: () => void;
  onOpenSettings: () => void;
  onOpenWorkspaceManagement?: () => void;
  onLogout?: () => void;
  onSelectChatSession?: (sessionId: string) => void;
  onNewChatSession?: () => void;
  onDeleteChatSession?: (sessionId: string) => void;
  onRenameChatSession?: (sessionId: string, newTitle: string) => Promise<void> | void;
  children: React.ReactNode;
}

export function WorkspaceApp({
  databases,
  activeDbId,
  view,
  theme,
  pendingCount,
  pendingSchemaCount,
  collapsed,
  userName,
  chatSessions,
  activeChatSessionId,
  loadingChatSessions,
  canChat,
  chatMode,
  notifications,
  unreadNotifications,
  onOpenCatalog,
  onMarkAllNotificationsRead,
  onMarkNotificationRead,
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
        pendingSchemaCount={pendingSchemaCount}
        collapsed={collapsed}
        userName={userName}
        chatSessions={chatSessions}
        activeChatSessionId={activeChatSessionId}
        loadingChatSessions={loadingChatSessions}
        canChat={canChat}
        chatMode={chatMode}
        notifications={notifications}
        unreadNotifications={unreadNotifications}
        onOpenCatalog={onOpenCatalog}
        onMarkAllNotificationsRead={onMarkAllNotificationsRead}
        onMarkNotificationRead={onMarkNotificationRead}
        onSelectView={onSelectView}
        onToggleCollapse={onToggleCollapse}
        onToggleTheme={onToggleTheme}
        onSelectDatabase={onSelectDatabase}
        onRemoveDatabase={onRemoveDatabase}
        onConnectDatabase={onConnectDatabase}
        onOpenSettings={onOpenSettings}
        onOpenWorkspaceManagement={onOpenWorkspaceManagement}
        onLogout={onLogout}
        onSelectChatSession={onSelectChatSession}
        onNewChatSession={onNewChatSession}
        onDeleteChatSession={onDeleteChatSession}
        onRenameChatSession={onRenameChatSession}
      />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
