'use client';

import {
  BarChart3,
  Check,
  CheckCircle2,
  Database,
  Edit2,
  LogOut,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  PlusCircle,
  Search,
  Settings,
  Share2,
  Sparkles,
  Sun,
  Trash2,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { ConnectDbModal } from '@/components/modals/ConnectDbModal';
import { MetricModal } from '@/components/modals/MetricModal';
import { SettingsModal } from '@/components/modals/SettingsModal';
import { AIStudioView } from '@/components/views/AIStudioView';
import { ExportPlaygroundView } from '@/components/views/ExportPlaygroundView';
import { MetricExplorerView } from '@/components/views/MetricExplorerView';
import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
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

export default function DashboardPage() {
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

  // 📝 Persistent Target Database descriptions
  const [dbDescriptions, setDbDescriptions] = useState<Record<string, string>>(() => {
    if (typeof window !== 'undefined') {
      try {
        return JSON.parse(localStorage.getItem('semantic_db_descriptions') || '{}');
      } catch {
        return {};
      }
    }
    return {};
  });

  const handleUpdateDescription = (layerId: string, description: string) => {
    setDbDescriptions((prev) => {
      const next = { ...prev, [layerId]: description.trim() };
      try {
        localStorage.setItem('semantic_db_descriptions', JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const activeLayer = useMemo(
    () => layers.find((item) => item.id === selectedId) || layers[0] || null,
    [layers, selectedId]
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
      .catch((error) => notify(error instanceof Error ? error.message : 'Không thể tải database'));
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
        current.map((item) => (item.id === activeLayerId ? { ...item, metrics } : item))
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

  if (isLoading || !token) {
    return (
      <div className='flex min-h-screen items-center justify-center bg-slate-50 text-xs font-semibold text-slate-500 dark:bg-[#0B0F19] dark:text-slate-400'>
        Đang xác thực tài khoản và chuyển hướng đến trang đăng nhập...
      </div>
    );
  }

  return (
    <div
      className={`flex h-screen overflow-hidden ${
        theme === 'dark' ? 'bg-[#0B0F19] text-slate-100' : 'bg-slate-50 text-slate-900'
      }`}
    >
      {toast && (
        <div className="fixed right-6 top-6 z-60 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-semibold text-white shadow-xl">
          <CheckCircle2 className="mr-2 inline h-4 w-4 text-emerald-400" />
          {toast}
        </div>
      )}

      {/* 🧭 Collapsible Left Sidebar */}
      <Sidebar
        layers={layers}
        selectedId={selectedId}
        collapsed={sidebarCollapsed}
        descriptions={dbDescriptions}
        onUpdateDescription={handleUpdateDescription}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        onSelect={(id) => {
          setSelectedId(id);
          setTab('studio');
        }}
        onConnect={() => setConnectOpen(true)}
        onDelete={async (layer) => {
          if (!token || !window.confirm(`Xóa database ${layer.db_name}?`)) return;
          await deleteDatabaseApi(layer.id, token);
          deleteLayer(layer.id);
          setLayers((current) => current.filter((item) => item.id !== layer.id));
        }}
        onSettings={() => setSettingsOpen(true)}
        onTheme={toggleTheme}
        dark={theme === 'dark'}
        userName={user?.name}
        onLogout={logout}
      />

      {/* 🖥️ Main Workspace Content */}
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {activeLayer ? (
          <>
            <WorkspaceHeader
              layer={activeLayer}
              description={dbDescriptions[activeLayer.id]}
              tab={tab}
              sidebarCollapsed={sidebarCollapsed}
              onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
              onTab={setTab}
            />
            <div className="flex-1 overflow-y-auto p-4 md:p-5">
              {tab === 'studio' && (
                <AIStudioView
                  layer={activeLayer}
                  theme={theme}
                  onMetricsChanged={refreshSemanticData}
                  onEditMetricRequest={(item) => openEditor(undefined, item)}
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
                />
              )}
              {tab === 'explorer' && (
                <MetricExplorerView
                  dbId={activeLayer.semantic_db_id}
                  metrics={activeLayer.metrics}
                  catalog={catalog}
                  theme={theme}
                />
              )}
              {tab === 'export' && <ExportPlaygroundView dbId={activeLayer.semantic_db_id} />}
            </div>
          </>
        ) : (
          <EmptyWorkspace onConnect={() => setConnectOpen(true)} />
        )}
      </main>

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
      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <MetricModal
        isOpen={metricOpen}
        onClose={() => setMetricOpen(false)}
        onSave={saveDefinition}
        tables={activeLayer?.tables || []}
        initialDefinition={editingMetric?.definition || editingSuggestion?.definition}
        initialName={editingMetric?.name}
      />
    </div>
  );
}

async function loadConnections(token: string): Promise<SemanticLayerData[]> {
  const [live, imported] = await Promise.all([
    listLiveTargetDbs(token).catch(() => [] as LiveDbSummary[]),
    listImportedSchemas(token).catch(() => [] as ImportedSchemaSummary[]),
  ]);
  const liveResults = await Promise.allSettled(live.map((item) => getLiveTargetDb(item.id, token)));
  const liveFull = liveResults
    .filter((r): r is PromiseFulfilledResult<LiveDbRecord> => r.status === 'fulfilled')
    .map((r) => r.value);

  const dumpResults = await Promise.allSettled(imported.map((item) => getImportedSchema(item.id, token)));
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
        'live'
      )
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
        'sql_dump'
      )
    ),
  ];
}

// ---------------------------------------------------------------------------
// 📂 Left Sidebar Component with Collapse & Database Description Editing
// ---------------------------------------------------------------------------

function Sidebar({
  layers,
  selectedId,
  collapsed,
  descriptions,
  onUpdateDescription,
  onToggleCollapse,
  onSelect,
  onConnect,
  onDelete,
  onSettings,
  onTheme,
  dark,
  userName,
  onLogout,
}: {
  layers: SemanticLayerData[];
  selectedId: string | null;
  collapsed: boolean;
  descriptions: Record<string, string>;
  onUpdateDescription: (layerId: string, description: string) => void;
  onToggleCollapse: () => void;
  onSelect: (id: string) => void;
  onConnect: () => void;
  onDelete: (layer: SemanticLayerData) => void;
  onSettings: () => void;
  onTheme: () => void;
  dark: boolean;
  userName?: string;
  onLogout: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftDesc, setDraftDesc] = useState<string>('');

  const startEdit = (layerId: string, currentDesc: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(layerId);
    setDraftDesc(currentDesc || '');
  };

  const saveEdit = (layerId: string, e?: React.MouseEvent | React.FormEvent) => {
    e?.stopPropagation();
    onUpdateDescription(layerId, draftDesc);
    setEditingId(null);
  };

  const cancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  // Mini Collapsed Sidebar (Rail mode)
  if (collapsed) {
    return (
      <aside className="flex w-16 shrink-0 flex-col items-center justify-between border-r border-slate-200 bg-white py-4 shadow-sm transition-all duration-300 dark:border-slate-800 dark:bg-[#0E1526]">
        {/* Top: Expand button & Brand icon */}
        <div className="flex flex-col items-center gap-3">
          <button
            type="button"
            onClick={onToggleCollapse}
            className="rounded-xl p-2 text-indigo-600 hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-950/50 cursor-pointer transition-all"
            title="Mở rộng Sidebar (Expand)"
          >
            <PanelLeftOpen className="h-5 w-5" />
          </button>

          <button
            type="button"
            onClick={onConnect}
            className="rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 p-2.5 text-white shadow-md shadow-indigo-500/20 hover:scale-105 active:scale-95 transition-all cursor-pointer"
            title="Thêm kết nối mới"
          >
            <PlusCircle className="h-4 w-4" />
          </button>
        </div>

        {/* Middle: Database icons list */}
        <div className="flex-1 space-y-2 overflow-y-auto py-4 px-1">
          {layers.map((layer) => {
            const isSelected = selectedId === layer.id;
            const desc = descriptions[layer.id];
            return (
              <button
                key={`${layer.source_type}-${layer.id}`}
                type="button"
                onClick={() => onSelect(layer.id)}
                className={`relative flex h-10 w-10 items-center justify-center rounded-xl transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/30'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                }`}
                title={`${layer.db_name} (${layer.source_type === 'live' ? 'LIVE DB' : 'SQL DUMP'})${
                  desc ? `\nMô tả: ${desc}` : ''
                }`}
              >
                <Database className="h-4.5 w-4.5" />
                {isSelected && (
                  <span className="absolute -left-1 top-2.5 h-5 w-1 rounded-r bg-indigo-400" />
                )}
              </button>
            );
          })}
        </div>

        {/* Bottom: Theme & Settings */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={onTheme}
            className="rounded-xl p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 cursor-pointer"
            title="Chuyển theme"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <button
            type="button"
            onClick={onSettings}
            className="rounded-xl p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 cursor-pointer"
            title="Cấu hình"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </aside>
    );
  }

  // Full Expanded Sidebar
  return (
    <aside className="flex w-80 shrink-0 flex-col border-r border-slate-200 bg-white transition-all duration-300 dark:border-slate-800 dark:bg-[#0E1526]">
      {/* Header */}
      <div className="flex items-center justify-between border-b p-4 dark:border-slate-800">
        <Link href="/" className="flex items-center gap-2 font-extrabold text-indigo-600 dark:text-indigo-400">
          <Database className="h-5 w-5" />
          <span>S206 SEMANTIC</span>
        </Link>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onTheme}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 cursor-pointer"
            title="Chuyển theme"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <button
            type="button"
            onClick={onToggleCollapse}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200 cursor-pointer transition-all"
            title="Thu gọn sidebar"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Add Connection */}
      <div className="p-3">
        <button
          type="button"
          onClick={onConnect}
          className="gradient-btn w-full rounded-xl py-2.5 text-xs font-bold text-white shadow-sm hover:opacity-95 active:scale-98 transition-all cursor-pointer flex items-center justify-center gap-1.5"
        >
          <PlusCircle className="h-4 w-4" />
          <span>Thêm kết nối mới</span>
        </button>
      </div>

      {/* Target Databases List */}
      <div className="flex-1 space-y-2 overflow-y-auto px-3">
        <div className="px-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
          Target Databases ({layers.length})
        </div>

        {layers.map((layer) => {
          const isSelected = selectedId === layer.id;
          const desc = descriptions[layer.id] || '';
          const isEditingThis = editingId === layer.id;

          return (
            <div
              key={`${layer.source_type}-${layer.id}`}
              onClick={() => onSelect(layer.id)}
              className={`group rounded-xl border p-3 text-left transition-all cursor-pointer ${
                isSelected
                  ? 'border-indigo-400 bg-indigo-50/70 shadow-xs dark:border-indigo-800 dark:bg-indigo-950/40'
                  : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 dark:border-slate-800/80 dark:bg-slate-900/40 dark:hover:bg-slate-800/60'
              }`}
            >
              {/* Header row: Name, Badges & Delete */}
              <div className="flex items-start justify-between gap-1.5">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <Database className={`h-3.5 w-3.5 ${isSelected ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-400'}`} />
                    <strong className="truncate text-xs font-bold text-slate-900 dark:text-slate-100">
                      {layer.db_name}
                    </strong>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-500 dark:text-slate-400">
                    <span
                      className={`rounded px-1.5 py-0.2 font-semibold ${
                        layer.source_type === 'live'
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                          : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                      }`}
                    >
                      {layer.source_type === 'live' ? 'LIVE DB' : 'SQL DUMP'}
                    </span>
                    <span>•</span>
                    <span>{layer.metrics.length} metrics</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(layer);
                  }}
                  className="rounded p-1 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all cursor-pointer"
                  title="Xóa database này"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* 📝 Database Description Section */}
              <div className="mt-2.5 border-t border-slate-100 pt-2 dark:border-slate-800/60">
                {isEditingThis ? (
                  <div className="space-y-1.5" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="text"
                      autoFocus
                      value={draftDesc}
                      onChange={(e) => setDraftDesc(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveEdit(layer.id, e);
                        if (e.key === 'Escape') cancelEdit(e as unknown as React.MouseEvent);
                      }}
                      placeholder="Nhập mô tả cho DB (Enter để lưu)..."
                      className="w-full rounded-lg border border-indigo-300 bg-white px-2 py-1 text-[11px] text-slate-800 outline-none focus:ring-1 focus:ring-indigo-500 dark:border-indigo-700 dark:bg-slate-950 dark:text-slate-100"
                    />
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={(e) => saveEdit(layer.id, e)}
                        className="inline-flex items-center gap-1 rounded bg-indigo-600 px-2 py-0.5 text-[10px] font-bold text-white hover:bg-indigo-700 cursor-pointer"
                      >
                        <Check className="h-2.5 w-2.5" /> Lưu
                      </button>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        className="rounded px-1.5 py-0.5 text-[10px] text-slate-500 hover:text-slate-800 dark:hover:text-white cursor-pointer"
                      >
                        Hủy
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between gap-1 text-[11px]">
                    {desc ? (
                      <p
                        className="line-clamp-2 text-slate-600 dark:text-slate-400 italic text-[11px] leading-tight"
                        title={desc}
                      >
                        {desc}
                      </p>
                    ) : (
                      <span className="text-[10px] text-slate-400 italic">Chưa có mô tả</span>
                    )}
                    <button
                      type="button"
                      onClick={(e) => startEdit(layer.id, desc, e)}
                      className="rounded p-1 text-slate-400 hover:text-indigo-600 opacity-60 group-hover:opacity-100 transition-all cursor-pointer shrink-0"
                      title={desc ? 'Sửa mô tả' : 'Thêm mô tả'}
                    >
                      <Pencil className="h-2.5 w-2.5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Settings & User Info */}
      <div className="space-y-2 border-t p-3 dark:border-slate-800">
        <button
          type="button"
          onClick={onSettings}
          className="flex w-full items-center gap-2 rounded-lg p-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 cursor-pointer"
        >
          <Settings className="h-4 w-4" />
          <span>Cấu hình hệ thống</span>
        </button>

        {userName && (
          <div className="flex items-center justify-between rounded-xl bg-slate-100 p-2 text-xs font-medium dark:bg-slate-900">
            <span className="truncate">{userName}</span>
            <button
              type="button"
              onClick={onLogout}
              className="rounded p-1 text-slate-400 hover:text-red-600 cursor-pointer"
              title="Đăng xuất"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// 🧭 Workspace Header
// ---------------------------------------------------------------------------

function WorkspaceHeader({
  layer,
  description,
  tab,
  sidebarCollapsed,
  onToggleSidebar,
  onTab,
}: {
  layer: SemanticLayerData;
  description?: string;
  tab: WorkspaceTab;
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onTab: (tab: WorkspaceTab) => void;
}) {
  const tabs: Array<[WorkspaceTab, string, React.ReactNode]> = [
    ['studio', 'AI Studio', <Sparkles key="s" className="h-3.5 w-3.5" />],
    ['metrics', `Catalog (${layer.metrics.length})`, <BarChart3 key="m" className="h-3.5 w-3.5" />],
    ['explorer', 'Explorer', <Search key="q" className="h-3.5 w-3.5" />],
    ['export', 'Export', <Share2 key="e" className="h-3.5 w-3.5" />],
  ];

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-[#0B0F19]">
      <div className="flex items-center gap-3">
        {sidebarCollapsed && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-bold text-indigo-600 hover:bg-indigo-50 dark:border-slate-800 dark:bg-slate-900 dark:text-indigo-400 cursor-pointer transition-all"
            title="Mở rộng Sidebar"
          >
            <PanelLeftOpen className="h-4 w-4" />
            <span>Sidebar</span>
          </button>
        )}

        <div>
          <div className="flex items-center gap-2">
            <strong className="text-sm font-bold text-slate-900 dark:text-slate-100">
              {layer.db_name}
            </strong>
            <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {layer.source_type === 'live' ? 'LIVE DB' : 'SQL DUMP'}
            </span>
          </div>
          {description && (
            <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400 italic">
              {description}
            </p>
          )}
        </div>
      </div>

      <nav className="flex rounded-xl bg-slate-100 p-1 dark:bg-slate-900">
        {tabs.map(([id, label, icon]) => (
          <button
            key={id}
            type="button"
            onClick={() => onTab(id)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all cursor-pointer ${
              tab === id
                ? 'bg-white text-indigo-600 shadow-sm dark:bg-slate-800 dark:text-indigo-400'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            {icon}
            {label}
          </button>
        ))}
      </nav>
    </header>
  );
}

function EmptyWorkspace({ onConnect }: { onConnect: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="rounded-2xl bg-indigo-50 p-4 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400">
        <Database className="h-12 w-12" />
      </div>
      <div>
        <h1 className="text-xl font-extrabold text-slate-900 dark:text-slate-100">
          Bắt đầu với Semantic Layer Studio
        </h1>
        <p className="mt-1 text-xs text-slate-500 max-w-sm">
          Kết nối tới Live Database hoặc tải lên tệp SQL Dump để tự động tạo Semantic Layer và định nghĩa các chỉ số.
        </p>
      </div>
      <button
        type="button"
        onClick={onConnect}
        className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-md shadow-indigo-500/20 hover:bg-indigo-700 transition-all cursor-pointer"
      >
        Thêm kết nối Database
      </button>
    </div>
  );
}
