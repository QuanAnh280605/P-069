'use client';

import { BarChart3, CheckCircle2, Database, LogOut, Moon, PlusCircle, Search, Settings, Share2, Sparkles, Sun, Trash2 } from 'lucide-react';
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
  listImportedSchemas,
  listLiveTargetDbs,
  listMetricsApi,
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
  const activeLayer = useMemo(() => layers.find((item) => item.id === selectedId) || layers[0] || null, [layers, selectedId]);
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
    void loadConnections(token).then((items) => {
      setLayers(items);
      setSelectedId((current) => current || items[0]?.id || null);
    }).catch((error) => notify(error instanceof Error ? error.message : 'Không thể tải database'));
  }, [notify, token]);

  const refreshSemanticData = useCallback(async () => {
    if (!activeLayerId || !semanticDbId) return;
    const dbId = String(semanticDbId);
    try {
      const [metrics, nextCatalog] = await Promise.all([listMetricsApi(dbId), getSemanticCatalogApi(dbId)]);
      setCatalog(nextCatalog);
      setLayers((current) => current.map((item) => item.id === activeLayerId ? { ...item, metrics } : item));
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Không thể tải Semantic Layer');
    }
  }, [activeLayerId, semanticDbId, notify]);

  useEffect(() => { void refreshSemanticData(); }, [refreshSemanticData]);

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
    setEditingMetric(metric || null); setEditingSuggestion(suggestion || null); setMetricOpen(true);
  };

  if (isLoading || !token) {
    return (
      <div className='flex min-h-screen items-center justify-center bg-slate-50 text-xs font-semibold text-slate-500 dark:bg-[#0B0F19] dark:text-slate-400'>
        Đang xác thực tài khoản và chuyển hướng đến trang đăng nhập...
      </div>
    );
  }

  return <div className={`flex h-screen overflow-hidden ${theme === 'dark' ? 'bg-[#0B0F19] text-slate-100' : 'bg-slate-50 text-slate-900'}`}>{toast && <div className='fixed right-6 top-6 z-60 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-semibold text-white shadow-xl'><CheckCircle2 className='mr-2 inline h-4 w-4 text-emerald-400' />{toast}</div>}<Sidebar layers={layers} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setTab('studio'); }} onConnect={() => setConnectOpen(true)} onDelete={async (layer) => { if (!token || !window.confirm(`Xóa database ${layer.db_name}?`)) return; await deleteDatabaseApi(layer.id, token); deleteLayer(layer.id); setLayers((current) => current.filter((item) => item.id !== layer.id)); }} onSettings={() => setSettingsOpen(true)} onTheme={toggleTheme} dark={theme === 'dark'} userName={user?.name} onLogout={logout} />
    <main className='flex min-w-0 flex-1 flex-col'>{activeLayer ? <><WorkspaceHeader layer={activeLayer} tab={tab} onTab={setTab} /><div className='flex-1 overflow-y-auto p-4 md:p-5'>{tab === 'studio' && <AIStudioView layer={activeLayer} theme={theme} onMetricsChanged={refreshSemanticData} onEditMetricRequest={(item) => openEditor(undefined, item)} />}{tab === 'metrics' && <MetricsCatalogView dbId={activeLayer.semantic_db_id} metrics={activeLayer.metrics} onDeleteMetric={removeMetric} onEditMetric={(item) => openEditor(item)} onOpenStudio={() => setTab('studio')} onApproveAll={approve} onApproveMetric={approveSingleMetric} />}{tab === 'explorer' && <MetricExplorerView dbId={activeLayer.semantic_db_id} metrics={activeLayer.metrics} catalog={catalog} theme={theme} />}{tab === 'export' && <ExportPlaygroundView dbId={activeLayer.semantic_db_id} />}</div></> : <EmptyWorkspace onConnect={() => setConnectOpen(true)} />}</main>
    <ConnectDbModal isOpen={connectOpen} onClose={() => setConnectOpen(false)} onSuccess={() => token && loadConnections(token).then((items) => { setLayers(items); setSelectedId(items[0]?.id || null); })} /><SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} /><MetricModal isOpen={metricOpen} onClose={() => setMetricOpen(false)} onSave={saveDefinition} tables={activeLayer?.tables || []} initialDefinition={editingMetric?.definition || editingSuggestion?.definition} initialName={editingMetric?.name} /></div>;
}

async function loadConnections(token: string): Promise<SemanticLayerData[]> {
  const [live, imported] = await Promise.all([listLiveTargetDbs(token), listImportedSchemas(token)]);
  const liveFull = await Promise.all(live.map((item) => getLiveTargetDb(item.id, token)));
  const dumpFull = await Promise.all(imported.map((item) => getImportedSchema(item.id, token)));
  return [...liveFull.map((item) => convertRawSchemaToLayer(item.id, item.display_name, item.dialect, item.raw_schema, undefined, item.updated_at, item.semantic_db_id, 'live')), ...dumpFull.map((item) => convertRawSchemaToLayer(item.id, item.display_name, item.dialect, item.raw_schema, undefined, item.updated_at, item.semantic_db_id, 'sql_dump'))];
}

function Sidebar({ layers, selectedId, onSelect, onConnect, onDelete, onSettings, onTheme, dark, userName, onLogout }: { layers: SemanticLayerData[]; selectedId: string | null; onSelect: (id: string) => void; onConnect: () => void; onDelete: (layer: SemanticLayerData) => void; onSettings: () => void; onTheme: () => void; dark: boolean; userName?: string; onLogout: () => void }) {
  return <aside className='flex w-72 shrink-0 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-[#0E1526]'><div className='flex items-center justify-between border-b p-4 dark:border-slate-800'><Link href='/' className='flex items-center gap-2 font-extrabold text-indigo-600'><Database className='h-5 w-5' />S206 SEMANTIC</Link><button onClick={onTheme}>{dark ? <Sun className='h-4 w-4' /> : <Moon className='h-4 w-4' />}</button></div><div className='p-3'><button onClick={onConnect} className='gradient-btn w-full rounded-xl py-2.5 text-xs font-bold text-white'><PlusCircle className='mr-1 inline h-4 w-4' />Thêm kết nối</button></div><div className='flex-1 space-y-1 overflow-y-auto px-3'>{layers.map((layer) => <button key={`${layer.source_type}-${layer.id}`} onClick={() => onSelect(layer.id)} className={`group flex w-full items-center justify-between rounded-xl border p-3 text-left ${selectedId === layer.id ? 'border-indigo-400 bg-indigo-50 dark:bg-indigo-950/50' : 'border-slate-200 dark:border-slate-800'}`}><span className='min-w-0'><strong className='block truncate text-xs'>{layer.db_name}</strong><small className='text-[10px] text-slate-500'>{layer.source_type === 'live' ? 'LIVE DB' : 'SQL DUMP'} · {layer.metrics.length} metrics</small></span><Trash2 onClick={(event) => { event.stopPropagation(); onDelete(layer); }} className='h-3.5 w-3.5 opacity-0 group-hover:opacity-100' /></button>)}</div><div className='space-y-2 border-t p-3 dark:border-slate-800'><button onClick={onSettings} className='text-xs'><Settings className='mr-1 inline h-4 w-4' />Cấu hình</button>{userName && <div className='flex justify-between rounded-xl bg-slate-100 p-2 text-xs dark:bg-slate-900'><span>{userName}</span><button onClick={onLogout}><LogOut className='h-4 w-4' /></button></div>}</div></aside>;
}

function WorkspaceHeader({ layer, tab, onTab }: { layer: SemanticLayerData; tab: WorkspaceTab; onTab: (tab: WorkspaceTab) => void }) {
  const tabs: Array<[WorkspaceTab, string, React.ReactNode]> = [['studio', 'AI Studio', <Sparkles key='s' className='h-3.5 w-3.5' />], ['metrics', `Catalog (${layer.metrics.length})`, <BarChart3 key='m' className='h-3.5 w-3.5' />], ['explorer', 'Explorer', <Search key='q' className='h-3.5 w-3.5' />], ['export', 'Export', <Share2 key='e' className='h-3.5 w-3.5' />]];
  return <header className='flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-[#0B0F19]'><div><strong className='text-sm'>{layer.db_name}</strong><span className='ml-2 rounded bg-slate-100 px-2 py-1 text-[10px] dark:bg-slate-800'>{layer.source_type === 'live' ? 'LIVE' : 'SQL DUMP'}</span></div><nav className='flex rounded-xl bg-slate-100 p-1 dark:bg-slate-900'>{tabs.map(([id, label, icon]) => <button key={id} onClick={() => onTab(id)} className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold ${tab === id ? 'bg-white text-indigo-600 shadow-sm dark:bg-slate-800' : 'text-slate-500'}`}>{icon}{label}</button>)}</nav></header>;
}

function EmptyWorkspace({ onConnect }: { onConnect: () => void }) { return <div className='flex flex-1 flex-col items-center justify-center gap-4'><Database className='h-12 w-12 text-indigo-500' /><h1 className='text-xl font-bold'>Bắt đầu với Semantic Layer</h1><button onClick={onConnect} className='rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white'>Thêm kết nối Database</button></div>; }
