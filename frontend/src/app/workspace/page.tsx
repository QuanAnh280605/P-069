'use client';

import {
  CheckCircle2,
  Bell,
  Database,
  Loader2,
  Plus,
} from 'lucide-react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { AIStudioView } from '@/components/views/AIStudioView';
import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
import { WorkspaceApp } from '@/components/workspace/WorkspaceApp';
import type { ViewId, WorkspaceDatabase } from '@/components/workspace/shared';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { useWorkspace } from '@/context/WorkspaceContext';
import {
  approveMetricsApi,
  approveSingleMetricApi,
  ChatSessionItem,
  convertRawSchemaToLayer,
  createMetricApi,
  deleteChatSessionApi,
  deleteDatabaseApi,
  deleteLayer,
  deleteMetricApi,
  getImportedSchema,
  getLiveTargetDb,
  getSemanticCatalogApi,
  ImportedSchemaRecord,
  ImportedSchemaSummary,
  listChatSessionsApi,
  listImportedSchemas,
  listLiveTargetDbs,
  listNotificationsApi,
  markNotificationsReadApi,
  listMetricsApi,
  LiveDbRecord,
  LiveDbSummary,
  MetricDefinition,
  MetricRecord,
  MetricSuggestion,
  METRIC_WRITE_PERMISSION_MESSAGE,
  isPermissionDenied,
  SemanticCatalog,
  SemanticLayerData,
  updateChatSessionTitleApi,
  updateMetricApi,
} from '@/lib/api';

// Dynamic imports for heavy views & modals to optimize initial bundle size & LCP
const MetricExplorerView = dynamic(
  () => import('@/components/views/MetricExplorerView').then((m) => m.MetricExplorerView),
  {
    loading: () => (
      <div className="flex flex-1 items-center justify-center p-8 text-xs font-semibold text-muted-foreground gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        Đang tải Trình khám phá chỉ số...
      </div>
    ),
    ssr: false,
  },
);

const ExportPlaygroundView = dynamic(
  () => import('@/components/views/ExportPlaygroundView').then((m) => m.ExportPlaygroundView),
  {
    loading: () => (
      <div className="flex flex-1 items-center justify-center p-8 text-xs font-semibold text-muted-foreground gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        Đang tải Xuất dữ liệu...
      </div>
    ),
    ssr: false,
  },
);

const ConnectDbModal = dynamic(
  () => import('@/components/modals/ConnectDbModal').then((m) => m.ConnectDbModal),
  { ssr: false },
);

const SettingsModal = dynamic(
  () => import('@/components/modals/SettingsModal').then((m) => m.SettingsModal),
  { ssr: false },
);

const WorkspaceManagementModal = dynamic(
  () => import('@/components/modals/WorkspaceManagementModal').then((m) => m.WorkspaceManagementModal),
  { ssr: false },
);

const MetricModal = dynamic(
  () => import('@/components/modals/MetricModal').then((m) => m.MetricModal),
  { ssr: false },
);

type WorkspaceTab = 'studio' | 'metrics' | 'explorer' | 'export';

function layerToDatabase(layer: SemanticLayerData): WorkspaceDatabase {
  return {
    id: layer.id,
    name: layer.db_name,
    engine: layer.db_type === 'auto' ? 'dump' : layer.db_type,
    status: 'connected',
    tables: layer.tables?.length || layer.table_count || 0,
  };
}

function tabToViewId(tab: WorkspaceTab): ViewId {
  switch (tab) {
    case 'studio':
      return 'ai-studio';
    case 'metrics':
      return 'catalog';
    case 'explorer':
      return 'explorer';
    case 'export':
      return 'export';
  }
}

function viewIdToTab(view: ViewId): WorkspaceTab {
  switch (view) {
    case 'ai-studio':
      return 'studio';
    case 'catalog':
      return 'metrics';
    case 'explorer':
      return 'explorer';
    case 'export':
      return 'export';
  }
}

export default function WorkspacePage() {
  const router = useRouter();
  const { user, token, logout, isLoading } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { currentWorkspace, permissions } = useWorkspace();
  const [layers, setLayers] = useState<SemanticLayerData[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<WorkspaceTab>('studio');
  const [catalog, setCatalog] = useState<SemanticCatalog | null>(null);
  const [connectOpen, setConnectOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [workspaceManagementOpen, setWorkspaceManagementOpen] = useState(false);
  const [metricOpen, setMetricOpen] = useState(false);
  const [editingMetric, setEditingMetric] = useState<MetricRecord | null>(null);
  const [editingSuggestion, setEditingSuggestion] = useState<MetricSuggestion | null>(null);
  const [toast, setToast] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [notifications, setNotifications] = useState<Array<{ id: number; title: string; body: string; read_at?: string | null }>>([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);

  // Chat sessions state lifted to page level
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(false);

  const activeLayer = useMemo(
    () => layers.find((item) => item.id === selectedId) || layers[0] || null,
    [layers, selectedId],
  );
  const activeLayerId = activeLayer?.id;
  const semanticDbId = activeLayer?.semantic_db_id;
  const canUseDataAssistant = Boolean(permissions.can_use_data_assistant);
  const canUseMetricStudio = Boolean(permissions.can_use_metric_studio);
  const canManageMetrics = Boolean(permissions.can_create_metrics);
  const canApproveMetrics = Boolean(permissions.can_approve_metrics);
  const canChat = Boolean(
    permissions.can_use_chat &&
      (canUseDataAssistant || canUseMetricStudio) &&
      semanticDbId &&
      activeLayer?.source_type === 'live',
  );
  const studioMode = canUseMetricStudio ? 'metric_studio' : 'data_assistant';

  const notify = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 3000);
  }, []);

  useEffect(() => {
    if (!token) return;
    void listNotificationsApi().then((data) => {
      setNotifications(data.items);
      setUnreadNotifications(data.unread_count);
    });
  }, [token, currentWorkspace?.id]);

  const openNotifications = async () => {
    setShowNotifications((current) => !current);
    if (unreadNotifications) {
      await markNotificationsReadApi();
      setUnreadNotifications(0);
      setNotifications((current) => current.map((item) => ({ ...item, read_at: item.read_at || new Date().toISOString() })));
    }
  };

  useEffect(() => {
    if (!canChat && tab === 'studio') setTab('metrics');
  }, [canChat, tab]);

  useEffect(() => {
    if (!isLoading && !token) {
      router.replace('/login');
    }
  }, [isLoading, token, router]);

  // Load summary connections list quickly
  useEffect(() => {
    if (!token || !currentWorkspace) return;
    setLayers([]);
    setSelectedId(null);
    setCatalog(null);
    void loadConnectionSummaries(token)
      .then((items) => {
        setLayers(items);
        if (items.length > 0) {
          setSelectedId(items[0].id);
        }
      })
      .catch((error) =>
        notify(error instanceof Error ? error.message : 'Không thể tải danh sách database'),
      );
  }, [currentWorkspace?.id, notify, token]);

  // Lazy-load details for active database if not loaded
  useEffect(() => {
    if (!token || !activeLayer || activeLayer.is_loaded) return;
    void loadLayerDetail(activeLayer, token).then((detailed) => {
      setLayers((current) =>
        current.map((item) => (item.id === detailed.id ? detailed : item)),
      );
    });
  }, [token, activeLayer, activeLayerId]);

  const loadSessions = useCallback(
    async (dbId: string) => {
      setLoadingSessions(true);
      try {
        const items = await listChatSessionsApi(dbId);
        setSessions(items);
        if (typeof window !== 'undefined') {
          const fromUrl = new URLSearchParams(window.location.search).get('chat');
          const matched = items.find((item) => item.id === fromUrl);
          if (matched) {
            setActiveSessionId(matched.id);
          }
        }
      } catch {
        setSessions([]);
      } finally {
        setLoadingSessions(false);
      }
    },
    [],
  );

  useEffect(() => {
    setActiveSessionId(null);
    setSessions([]);
    if (!semanticDbId || activeLayer?.source_type !== 'live') return;
    void loadSessions(String(semanticDbId));
  }, [activeLayer?.source_type, activeLayerId, loadSessions, semanticDbId]);

  const selectSession = useCallback(
    (sessionId: string) => {
      setActiveSessionId(sessionId);
      if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        url.searchParams.set('chat', sessionId);
        window.history.replaceState({}, '', url);
      }
      setTab('studio');
    },
    [],
  );

  const newChat = useCallback(() => {
    setActiveSessionId(null);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('chat');
      window.history.replaceState({}, '', url);
    }
    setTab('studio');
  }, []);

  const removeSession = useCallback(
    async (sessionId: string) => {
      if (!semanticDbId) return;
      try {
        await deleteChatSessionApi(String(semanticDbId), sessionId);
        setSessions((current) => current.filter((item) => item.id !== sessionId));
        if (activeSessionId === sessionId) {
          setActiveSessionId(null);
          if (typeof window !== 'undefined') {
            const url = new URL(window.location.href);
            url.searchParams.delete('chat');
            window.history.replaceState({}, '', url);
          }
        }
        notify('Đã xóa cuộc trò chuyện.');
      } catch (error) {
        notify(error instanceof Error ? error.message : 'Không thể xóa cuộc trò chuyện');
      }
    },
    [activeSessionId, notify, semanticDbId],
  );

  const handleRenameSession = useCallback(
    async (sessionId: string, newTitle: string) => {
      if (!semanticDbId || !newTitle.trim()) return;
      try {
        const updated = await updateChatSessionTitleApi(
          String(semanticDbId),
          sessionId,
          newTitle.trim(),
        );
        setSessions((current) =>
          current.map((item) => (item.id === sessionId ? { ...item, title: updated.title } : item)),
        );
        notify('Đã đổi tên cuộc trò chuyện.');
      } catch (error) {
        notify(error instanceof Error ? error.message : 'Không thể đổi tên cuộc trò chuyện');
      }
    },
    [notify, semanticDbId],
  );

  const refreshSemanticData = useCallback(async () => {
    if (!activeLayerId || !semanticDbId) return;
    const dbId = String(semanticDbId);
    try {
      const metrics = await listMetricsApi(dbId);
      setLayers((current) =>
        current.map((item) => (item.id === activeLayerId ? { ...item, metrics } : item)),
      );
      if (tab === 'explorer') {
        const nextCatalog = await getSemanticCatalogApi(dbId);
        setCatalog(nextCatalog);
      }
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Không thể tải Semantic Layer');
    }
  }, [activeLayerId, semanticDbId, notify, tab]);

  // Load catalog on-demand when user opens Explorer tab
  useEffect(() => {
    if (tab === 'explorer' && semanticDbId) {
      const dbId = String(semanticDbId);
      if (!catalog || catalog.db_id !== Number(semanticDbId)) {
        void getSemanticCatalogApi(dbId)
          .then((nextCatalog) => setCatalog(nextCatalog))
          .catch(() => {});
      }
    }
  }, [tab, semanticDbId, catalog]);

  const saveDefinition = async (definition: MetricDefinition) => {
    if (!canManageMetrics) {
      notify(METRIC_WRITE_PERMISSION_MESSAGE);
      throw new Error(METRIC_WRITE_PERMISSION_MESSAGE);
    }
    if (!activeLayer?.semantic_db_id) throw new Error('Semantic database chưa sẵn sàng');
    const dbId = String(activeLayer.semantic_db_id);
    try {
      if (editingMetric) await updateMetricApi(dbId, editingMetric.metric_id, definition);
      else await createMetricApi(dbId, { definition, source: editingSuggestion ? 'ai' : 'manual' });
      await refreshSemanticData();
      notify('Đã lưu Metric Definition dạng JSON.');
    } catch (error) {
      if (isPermissionDenied(error)) notify(METRIC_WRITE_PERMISSION_MESSAGE);
      throw error;
    }
  };

  const removeMetric = async (metricId: number) => {
    if (!activeLayer?.semantic_db_id) return;
    await deleteMetricApi(String(activeLayer.semantic_db_id), metricId);
    setLayers((current) =>
      current.map((item) =>
        item.id === activeLayerId
          ? { ...item, metrics: item.metrics.filter((m) => m.metric_id !== metricId) }
          : item,
      ),
    );
    notify('Đã xóa metric.');
  };

  const approve = async () => {
    if (!activeLayer?.semantic_db_id) return;
    const response = await approveMetricsApi(activeLayer.semantic_db_id);
    setLayers((current) =>
      current.map((item) =>
        item.id === activeLayerId
          ? {
              ...item,
              metrics: item.metrics.map((m) => ({ ...m, status: 'approved' })),
            }
          : item,
      ),
    );
    notify(`Đã phê duyệt ${response.approved_count} metric.`);
  };

  const approveSingleMetric = async (metricId: number) => {
    if (!activeLayer?.semantic_db_id) return;
    await approveSingleMetricApi(String(activeLayer.semantic_db_id), metricId);
    setLayers((current) =>
      current.map((item) =>
        item.id === activeLayerId
          ? {
              ...item,
              metrics: item.metrics.map((m) => (m.metric_id === metricId ? { ...m, status: 'approved' } : m)),
            }
          : item,
      ),
    );
    notify('Đã phê duyệt chỉ số thành công.');
  };

  const openEditor = (metric?: MetricRecord, suggestion?: MetricSuggestion) => {
    setEditingMetric(metric || null);
    setEditingSuggestion(suggestion || null);
    setMetricOpen(true);
  };

  const pendingCount = activeLayer
    ? activeLayer.metrics.filter((m) => m.status !== 'approved').length
    : 0;

  if (isLoading || !token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-xs font-semibold text-muted-foreground">
        Đang xác thực tài khoản...
      </div>
    );
  }

  return (
    <WorkspaceApp
      databases={layers.map(layerToDatabase)}
      activeDbId={selectedId}
      view={tabToViewId(tab)}
      theme={theme}
      pendingCount={pendingCount}
      collapsed={sidebarCollapsed}
      userName={user?.name}
      chatSessions={sessions}
      activeChatSessionId={activeSessionId}
      loadingChatSessions={loadingSessions}
      canChat={canChat}
      chatMode={studioMode}
      onSelectView={(v) => {
        if (v === 'ai-studio' && !canChat) {
          setTab('metrics');
          return;
        }
        setTab(viewIdToTab(v));
      }}
      onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      onToggleTheme={toggleTheme}
      onSelectDatabase={(id) => {
        setSelectedId(id);
        const nextLayer = layers.find((item) => item.id === id);
        const nextCanChat = Boolean(
          permissions.can_use_chat &&
            (canUseDataAssistant || canUseMetricStudio) &&
            nextLayer?.source_type === 'live',
        );
        setTab(nextCanChat ? 'studio' : 'metrics');
      }}
      onRemoveDatabase={async (id) => {
        const layer = layers.find((l) => l.id === id);
        if (!layer || !token || !window.confirm(`Xóa database ${layer.db_name}?`)) return;
        await deleteDatabaseApi(layer.id, token);
        deleteLayer(layer.id);
        setLayers((current) => current.filter((item) => item.id !== layer.id));
      }}
      onConnectDatabase={() => setConnectOpen(true)}
      onOpenSettings={() => setSettingsOpen(true)}
      onOpenWorkspaceManagement={
        permissions.can_manage_members ? () => setWorkspaceManagementOpen(true) : undefined
      }
      onLogout={logout}
      onSelectChatSession={canChat ? selectSession : undefined}
      onNewChatSession={canChat ? newChat : undefined}
      onDeleteChatSession={canChat ? removeSession : undefined}
      onRenameChatSession={canChat ? handleRenameSession : undefined}
    >
      <div className="fixed right-6 top-16 z-60">
        <Button size="icon" variant="outline" className="relative" onClick={() => void openNotifications()} aria-label="Thông báo">
          <Bell className="h-4 w-4" />
          {unreadNotifications > 0 && <span className="absolute -right-1 -top-1 rounded-full bg-primary px-1.5 text-[10px] text-primary-foreground">{unreadNotifications}</span>}
        </Button>
        {showNotifications && (
          <div className="absolute right-0 mt-2 w-80 rounded-lg border border-border bg-card p-3 shadow-xl">
            <p className="mb-2 text-sm font-semibold">Thông báo</p>
            {notifications.length ? notifications.map((item) => <div key={item.id} className="border-t border-border py-2 text-xs"><p className="font-medium">{item.title}</p><p className="text-muted-foreground">{item.body}</p></div>) : <p className="text-xs text-muted-foreground">Chưa có thông báo.</p>}
          </div>
        )}
      </div>
      {toast && (
        <div className="fixed right-6 top-6 z-60 rounded-xl bg-card border border-border px-4 py-2.5 text-xs font-semibold text-foreground shadow-2xl animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="mr-2 inline h-4 w-4 text-emerald-500" />
          {toast}
        </div>
      )}

      {activeLayer ? (
        <>
          {tab === 'studio' && (
            <AIStudioView
              layer={activeLayer}
              theme={theme}
              sessions={sessions}
              setSessions={setSessions}
              activeSessionId={activeSessionId}
              setActiveSessionId={setActiveSessionId}
              loadingSessions={loadingSessions}
              mode={studioMode}
              onSelectSession={selectSession}
              onNewChat={canChat ? newChat : undefined}
              onMetricsChanged={refreshSemanticData}
              onNotify={notify}
              onEditMetricRequest={canManageMetrics ? (item) => openEditor(undefined, item) : undefined}
              onOpenCatalog={() => setTab('metrics')}
            />
          )}
          {tab === 'metrics' && (
            <MetricsCatalogView
              dbId={activeLayer.semantic_db_id}
              metrics={activeLayer.metrics}
              database={layerToDatabase(activeLayer)}
              canManageMetrics={canManageMetrics}
              onDeleteMetric={canManageMetrics ? removeMetric : undefined}
              onEditMetric={canManageMetrics ? (item) => openEditor(item) : undefined}
              onOpenStudio={canUseMetricStudio ? () => setTab('studio') : undefined}
              onApproveAll={canApproveMetrics ? approve : undefined}
              onApproveMetric={canApproveMetrics ? approveSingleMetric : undefined}
            />
          )}
          {tab === 'explorer' && (
            <MetricExplorerView
              dbId={activeLayer.semantic_db_id}
              metrics={activeLayer.metrics}
              catalog={catalog}
              theme={theme}
              database={layerToDatabase(activeLayer)}
            />
          )}
          {tab === 'export' && (
            <ExportPlaygroundView
              dbId={activeLayer.semantic_db_id}
              metrics={activeLayer.metrics}
              database={layerToDatabase(activeLayer)}
            />
          )}
        </>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center bg-background text-foreground">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-border bg-secondary text-primary">
            <Database className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">Chưa chọn Target Database</h2>
            <p className="mt-1 max-w-sm text-xs text-muted-foreground">
              Kết nối tới Live Database hoặc tải lên tệp SQL Dump để tự động tạo Semantic Layer và
              định nghĩa các chỉ số.
            </p>
          </div>
          <Button onClick={() => setConnectOpen(true)} className="gap-2 text-xs">
            <Plus className="h-4 w-4" />
            Thêm kết nối Database
          </Button>
        </div>
      )}

      {connectOpen && (
        <ConnectDbModal
          isOpen={connectOpen}
          onClose={() => setConnectOpen(false)}
          onSuccess={async () => {
            if (!token) return;
            const items = await loadConnectionSummaries(token);
            setLayers(items);
            if (items.length) setSelectedId(items[items.length - 1].id);
          }}
        />
      )}
      {settingsOpen && (
        <SettingsModal
          isOpen={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          databaseCount={layers.length}
          metricCount={activeLayer?.metrics.length}
        />
      )}
      {metricOpen && (
        <MetricModal
          isOpen={metricOpen}
          onClose={() => {
            setMetricOpen(false);
            setEditingMetric(null);
            setEditingSuggestion(null);
          }}
          onSave={saveDefinition}
          tables={activeLayer?.tables || []}
          initialDefinition={editingMetric?.definition || editingSuggestion?.definition}
          initialName={editingMetric?.name}
          canSave={canManageMetrics}
          saveDisabledReason={METRIC_WRITE_PERMISSION_MESSAGE}
        />
      )}
      {workspaceManagementOpen && (
        <WorkspaceManagementModal
          isOpen={workspaceManagementOpen}
          onClose={() => setWorkspaceManagementOpen(false)}
        />
      )}
    </WorkspaceApp>
  );
}

// Fast summary connection loader: only 2 parallel API calls instead of N+1 cascade
async function loadConnectionSummaries(token: string): Promise<SemanticLayerData[]> {
  const [liveDbs, dumpSchemas] = await Promise.all([
    listLiveTargetDbs(token).catch(() => [] as LiveDbSummary[]),
    listImportedSchemas(token).catch(() => [] as ImportedSchemaSummary[]),
  ]);

  const liveStubs: SemanticLayerData[] = liveDbs.map((db) => ({
    id: String(db.id),
    db_name: db.display_name,
    db_type: db.dialect,
    status: 'Saved',
    updated_at: db.updated_at,
    tables: [],
    semantic_db_id: db.semantic_db_id,
    source_type: 'live',
    metrics: [],
    table_count: db.table_count,
    is_loaded: false,
  }));

  const dumpStubs: SemanticLayerData[] = dumpSchemas.map((dump) => ({
    id: String(dump.id),
    db_name: dump.display_name,
    db_type: 'auto',
    status: 'Saved',
    updated_at: dump.updated_at,
    tables: [],
    semantic_db_id: dump.semantic_db_id,
    source_type: 'sql_dump',
    metrics: [],
    table_count: dump.table_count,
    is_loaded: false,
  }));

  return [...liveStubs, ...dumpStubs];
}

// On-demand detail loader for selected database
async function loadLayerDetail(layer: SemanticLayerData, token: string): Promise<SemanticLayerData> {
  if (layer.is_loaded) return layer;
  try {
    let fullLayer = layer;
    if (layer.source_type === 'live') {
      const detail: LiveDbRecord = await getLiveTargetDb(Number(layer.id), token);
      fullLayer = convertRawSchemaToLayer(
        detail.id,
        detail.display_name,
        detail.dialect,
        detail.raw_schema,
        undefined,
        detail.updated_at,
        detail.semantic_db_id,
        'live',
      );
    } else {
      const detail: ImportedSchemaRecord = await getImportedSchema(Number(layer.id), token);
      fullLayer = convertRawSchemaToLayer(
        detail.id,
        detail.display_name,
        'auto',
        detail.raw_schema,
        undefined,
        detail.updated_at,
        detail.semantic_db_id,
        'sql_dump',
      );
    }
    const metrics = fullLayer.semantic_db_id
      ? await listMetricsApi(String(fullLayer.semantic_db_id)).catch(() => [])
      : [];
    return {
      ...fullLayer,
      table_count: fullLayer.tables.length,
      metrics,
      is_loaded: true,
    };
  } catch {
    return { ...layer, is_loaded: true };
  }
}
