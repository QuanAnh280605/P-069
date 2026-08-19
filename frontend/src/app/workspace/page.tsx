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
import { AIStudioView } from '@/components/views/AIStudioView';
import { ExportPlaygroundView } from '@/components/views/ExportPlaygroundView';
import { MetricExplorerView } from '@/components/views/MetricExplorerView';
import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
import { WorkspaceApp } from '@/components/workspace/WorkspaceApp';
import type { ViewId, WorkspaceDatabase } from '@/components/workspace/shared';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import {
  approveMetricsApi,
  approveSingleMetricApi,
  convertRawSchemaToLayer,
  createMetricApi,
  deleteDatabaseApi,
  deleteLayer,
  deleteMetricApi,
  getImportedSchema,
  getLiveTargetDb,
  getSemanticCatalogApi,
  ImportedSchemaRecord,
  ImportedSchemaSummary,
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
  const [layers, setLayers] = useState<SemanticLayerData[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<WorkspaceTab>('studio');
  const [catalog, setCatalog] = useState<SemanticCatalog | null>(null);
  const [connectOpen, setConnectOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [metricOpen, setMetricOpen] = useState(false);
  const [editingMetric, setEditingMetric] = useState<MetricRecord | null>(null);
  const [editingSuggestion, setEditingSuggestion] = useState<MetricSuggestion | null>(null);
  const [toast, setToast] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);

  const activeLayer = useMemo(
    () => layers.find((item) => item.id === selectedId) || layers[0] || null,
    [layers, selectedId],
  );
  const activeLayerId = activeLayer?.id;
  const semanticDbId = activeLayer?.semantic_db_id;

  const notify = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 3000);
  }, []);

  useEffect(() => {
    if (!isLoading && !token) {
      router.replace('/login');
    }
  }, [isLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    void loadConnections(token)
      .then((items) => {
        setLayers(items);
        setSelectedId((current) => current || items[0]?.id || null);
      })
      .catch((error) =>
        notify(error instanceof Error ? error.message : 'Không thể tải danh sách database'),
      );
  }, [notify, token]);

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
      onLogout={logout}
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
              onMetricsChanged={refreshSemanticData}
              onEditMetricRequest={(item) => openEditor(undefined, item)}
              onOpenCatalog={() => setTab('metrics')}
            />
          )}
          {tab === 'metrics' && (
            <MetricsCatalogView
              dbId={activeLayer.semantic_db_id}
              metrics={activeLayer.metrics}
              onDeleteMetric={removeMetric}
              onEditMetric={(item) => openEditor(item)}
              onOpenStudio={() => setTab('studio')}
              onApproveAll={approve}
              onApproveMetric={approveSingleMetric}
              database={layerToDatabase(activeLayer)}
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
        <EmptyWorkspace onConnect={() => setConnectOpen(true)} />
      )}

      <ConnectDbModal
        isOpen={connectOpen}
        onClose={() => setConnectOpen(false)}
        onSuccess={() =>
          token &&
          loadConnections(token).then((items) => {
            setLayers(items);
            setSelectedId(items[0]?.id || null);
          })
        }
      />
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        databaseCount={layers.length}
        metricCount={activeLayer?.metrics.length || 0}
      />
      <MetricModal
        isOpen={metricOpen}
        onClose={() => setMetricOpen(false)}
        onSave={saveDefinition}
        tables={activeLayer?.tables || []}
        initialDefinition={editingMetric?.definition || editingSuggestion?.definition}
        initialName={editingMetric?.name}
        status={editingMetric?.status}
      />
    </WorkspaceApp>
  );
}

async function loadConnections(token: string): Promise<SemanticLayerData[]> {
  const [live, imported] = await Promise.all([
    listLiveTargetDbs(token).catch(() => [] as LiveDbSummary[]),
    listImportedSchemas(token).catch(() => [] as ImportedSchemaSummary[]),
  ]);
  const liveResults = await Promise.allSettled(
    live.map((item) => getLiveTargetDb(item.id, token)),
  );
  const liveFull = liveResults
    .filter((r): r is PromiseFulfilledResult<LiveDbRecord> => r.status === 'fulfilled')
    .map((r) => r.value);

  const dumpResults = await Promise.allSettled(
    imported.map((item) => getImportedSchema(item.id, token)),
  );
  const dumpFull = dumpResults
    .filter((r): r is PromiseFulfilledResult<ImportedSchemaRecord> => r.status === 'fulfilled')
    .map((r) => r.value);

  return [
    ...liveFull.map((item) =>
      convertRawSchemaToLayer(
        item.id,
        item.display_name,
        item.dialect,
        item.raw_schema,
        undefined,
        item.updated_at,
        item.semantic_db_id,
        'live',
      ),
    ),
    ...dumpFull.map((item) =>
      convertRawSchemaToLayer(
        item.id,
        item.display_name,
        item.dialect,
        item.raw_schema,
        undefined,
        item.updated_at,
        item.semantic_db_id,
        'sql_dump',
      ),
    ),
  ];
}

function EmptyWorkspace({ onConnect }: { onConnect: () => void }) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-4 p-8 text-center bg-background">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-secondary text-primary shadow-xs">
        <Database className="h-8 w-8" />
      </div>
      <div>
        <h1 className="font-display text-2xl text-foreground">
          Bắt đầu với Semantic Layer Studio
        </h1>
        <p className="mt-1 max-w-sm text-xs text-muted-foreground">
          Kết nối tới Live Database hoặc tải lên tệp SQL Dump để tự động tạo Semantic Layer và định nghĩa các chỉ số.
        </p>
      </div>
      <Button onClick={onConnect} className="gap-1.5 text-xs">
        <Plus className="h-4 w-4" />
        Thêm kết nối Database
      </Button>
    </div>
  );
}
