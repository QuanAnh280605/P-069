'use client';

import {
  CheckCircle2,
  Database,
  Plus,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { ConnectDbModal } from '@/components/modals/ConnectDbModal';
import { MetricModal } from '@/components/modals/MetricModal';
import { SettingsModal } from '@/components/modals/SettingsModal';
import { WorkspaceManagementModal } from '@/components/modals/WorkspaceManagementModal';
import { AIStudioView } from '@/components/views/AIStudioView';
import { ExportPlaygroundView } from '@/components/views/ExportPlaygroundView';
import { MetricExplorerView } from '@/components/views/MetricExplorerView';
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
  createChatSessionApi,
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
  listMetricsApi,
  LiveDbRecord,
  LiveDbSummary,
  MetricDefinition,
  MetricRecord,
  MetricSuggestion,
  SemanticCatalog,
  SemanticLayerData,
  updateChatSessionTitleApi,
  updateMetricApi,
} from '@/lib/api';

type WorkspaceTab = 'studio' | 'metrics' | 'explorer' | 'export';

function layerToDatabase(layer: SemanticLayerData): WorkspaceDatabase {
  return {
    id: layer.id,
    name: layer.db_name,
    engine: layer.db_type === 'auto' ? 'dump' : layer.db_type,
    status: 'connected',
    tables: layer.tables.length,
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
  const [workspaceModalOpen, setWorkspaceModalOpen] = useState(false);
  const [editingMetric, setEditingMetric] = useState<MetricRecord | null>(null);
  const [editingSuggestion, setEditingSuggestion] = useState<MetricSuggestion | null>(null);
  const [toast, setToast] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);

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
  const canChat = Boolean(semanticDbId && activeLayer?.source_type === 'live');

  const notify = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 3000);
  }, []);

  const updateChatUrl = (sessionId: string | null) => {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (sessionId) url.searchParams.set('chat', sessionId);
    else url.searchParams.delete('chat');
    window.history.replaceState({}, '', url);
  };


  useEffect(() => {
    if (!isLoading && !token) {
      router.replace('/login');
    }
  }, [isLoading, token, router]);

  useEffect(() => {
    if (!token || !currentWorkspace) return;
    setLayers([]);
    setSelectedId(null);
    setCatalog(null);
    void loadConnections(token)
      .then((items) => {
        setLayers(items);
        setSelectedId(items[0]?.id || null);
      })
      .catch((error) =>
        notify(error instanceof Error ? error.message : 'Không thể tải danh sách database'),
      );
  }, [currentWorkspace?.id, notify, token]);

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

  const newChat = useCallback(async () => {
    if (!semanticDbId) return;
    try {
      const created = await createChatSessionApi(String(semanticDbId), 'Cuộc trò chuyện mới');
      setSessions((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      selectSession(created.id);
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Không thể tạo cuộc trò chuyện mới');
    }
  }, [notify, selectSession, semanticDbId]);

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
      const [metrics, nextCatalog] = await Promise.all([
        listMetricsApi(dbId),
        getSemanticCatalogApi(dbId),
      ]);
      setCatalog(nextCatalog);
      setLayers((current) =>
        current.map((item) => (item.id === activeLayerId ? { ...item, metrics } : item)),
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Không thể tải Semantic Layer');
    }
  }, [activeLayerId, semanticDbId, notify]);

  useEffect(() => {
    void refreshSemanticData();
  }, [refreshSemanticData]);

  const saveDefinition = async (definition: MetricDefinition) => {
    if (!activeLayer?.semantic_db_id) throw new Error('Semantic database chưa sẵn sàng');
    const dbId = String(activeLayer.semantic_db_id);
    if (editingMetric) await updateMetricApi(dbId, editingMetric.metric_id, definition);
    else await createMetricApi(dbId, { definition, source: editingSuggestion ? 'ai' : 'manual' });
    await refreshSemanticData();
    notify('Đã lưu Metric Definition dạng JSON.');
  };

  const removeMetric = async (metricId: number) => {
    if (!activeLayer?.semantic_db_id) return;
    await deleteMetricApi(String(activeLayer.semantic_db_id), metricId);
    await refreshSemanticData();
    notify('Đã xóa metric.');
  };

  const approve = async () => {
    if (!activeLayer?.semantic_db_id) return;
    const response = await approveMetricsApi(activeLayer.semantic_db_id);
    await refreshSemanticData();
    notify(`Đã phê duyệt ${response.approved_count} metric.`);
  };

  const approveSingleMetric = async (metricId: number) => {
    if (!activeLayer?.semantic_db_id) return;
    await approveSingleMetricApi(String(activeLayer.semantic_db_id), metricId);
    await refreshSemanticData();
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
      canChat={Boolean(activeLayer?.source_type === 'live' && semanticDbId)}
      onSelectView={(v) => setTab(viewIdToTab(v))}
      onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      onToggleTheme={toggleTheme}
      onSelectDatabase={(id) => {
        setSelectedId(id);
        setTab('studio');
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
      onOpenWorkspaceManagement={() => setWorkspaceManagementOpen(true)}
      onLogout={logout}
      onSelectChatSession={selectSession}
      onNewChatSession={newChat}
      onDeleteChatSession={removeSession}
      onRenameChatSession={handleRenameSession}
    >
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
              onSelectSession={selectSession}
              onNewChat={newChat}
              onMetricsChanged={refreshSemanticData}
              onEditMetricRequest={(item) => openEditor(undefined, item)}
              onOpenCatalog={() => setTab('metrics')}
            />
          )}
          {tab === 'metrics' && (
            <MetricsCatalogView
              dbId={activeLayer.semantic_db_id}
              metrics={activeLayer.metrics}
              database={layerToDatabase(activeLayer)}
              onDeleteMetric={removeMetric}
              onEditMetric={(item) => openEditor(item)}
              onOpenStudio={() => setTab('studio')}
              onApproveAll={approve}
              onApproveMetric={approveSingleMetric}
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

      <ConnectDbModal
        isOpen={connectOpen}
        onClose={() => setConnectOpen(false)}
        onSuccess={async () => {
          if (!token) return;
          const items = await loadConnections(token);
          setLayers(items);
          if (items.length) setSelectedId(items[items.length - 1].id);
        }}
      />
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        databaseCount={layers.length}
        metricCount={activeLayer?.metrics.length}
      />
      <WorkspaceManagementModal
        isOpen={workspaceModalOpen}
        onClose={() => setWorkspaceModalOpen(false)}
      />
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
      />
      <WorkspaceManagementModal
        isOpen={workspaceManagementOpen}
        onClose={() => setWorkspaceManagementOpen(false)}
      />
    </WorkspaceApp>
  );
}

async function loadConnections(token: string): Promise<SemanticLayerData[]> {
  const [liveDbs, dumpSchemas] = await Promise.all([
    listLiveTargetDbs(token).catch(() => [] as LiveDbSummary[]),
    listImportedSchemas(token).catch(() => [] as ImportedSchemaSummary[]),
  ]);

  const liveLayers = await Promise.all(
    liveDbs.map(async (db) => {
      try {
        const detail: LiveDbRecord = await getLiveTargetDb(db.id, token);
        const semanticDbId = detail.semantic_db_id;
        const metrics = semanticDbId ? await listMetricsApi(String(semanticDbId)) : [];
        return convertRawSchemaToLayer(
          detail.id,
          detail.display_name,
          detail.dialect,
          detail.raw_schema,
          undefined,
          detail.updated_at,
          semanticDbId,
          'live',
        );
      } catch {
        return null;
      }
    }),
  );

  const dumpLayers = await Promise.all(
    dumpSchemas.map(async (dump) => {
      try {
        const detail: ImportedSchemaRecord = await getImportedSchema(dump.id, token);
        const semanticDbId = detail.semantic_db_id;
        const metrics = semanticDbId ? await listMetricsApi(String(semanticDbId)) : [];
        return convertRawSchemaToLayer(
          dump.id,
          dump.display_name,
          'auto',
          detail.raw_schema,
          undefined,
          detail.updated_at,
          semanticDbId,
          'sql_dump',
        );
      } catch {
        return null;
      }
    }),
  );

  return [...liveLayers, ...dumpLayers].filter(Boolean) as SemanticLayerData[];
}
