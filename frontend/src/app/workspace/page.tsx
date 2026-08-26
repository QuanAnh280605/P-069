'use client';

import { CheckCircle2, ClipboardCheck, Database, Loader2, Plus } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { AIStudioView } from '@/components/views/AIStudioView';
import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
import type { ExplorerInitialSelection } from '@/components/views/MetricExplorerView';
import { NotificationCenter } from '@/components/workspace/NotificationCenter';
import { WorkspaceApp } from '@/components/workspace/WorkspaceApp';
import { SchemaDriftBanner } from '@/components/workspace/SchemaDriftBanner';
import type { ViewId, WorkspaceDatabase } from '@/components/workspace/shared';
import { streamNotifications } from '@/lib/notificationStream';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { useWorkspace } from '@/context/WorkspaceContext';
import {
  AppNotification,
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
  getSchemaReviewApi,
  getSyncStatusApi,
  triggerSyncApi,
  ImportedSchemaRecord,
  ImportedSchemaSummary,
  listChatSessionsApi,
  listImportedSchemas,
  listLiveTargetDbs,
  listNotificationsApi,
  markNotificationReadApi,
  markNotificationsReadApi,
  listMetricsApi,
  LiveDbRecord,
  LiveDbSummary,
  MetricDefinition,
  MetricRecord,
  MetricSuggestion,
  METRIC_WRITE_PERMISSION_MESSAGE,
  isPermissionDenied,
  restoreMetricApi,
  SchemaSyncStatus,
  SemanticCatalog,
  SemanticLayerData,
  updateChatSessionTitleApi,
  updateMetricApi,
} from '@/lib/api';
import {
  resolveDrillDownDateFilters,
  type DashboardDatePreset,
  type DashboardWidgetConfig,
} from '@/lib/dashboard';

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

const SchemaReviewView = dynamic(
  () => import('@/components/views/SchemaReviewView').then((m) => m.SchemaReviewView),
  {
    loading: () => (
      <div className="flex flex-1 items-center justify-center p-8 text-xs font-semibold text-muted-foreground gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        Đang tải Schema Review...
      </div>
    ),
    ssr: false,
  },
);

const MetricsDashboardView = dynamic(
  () => import('@/components/views/MetricsDashboardView').then((m) => m.MetricsDashboardView),
  {
    loading: () => (
      <div className="flex flex-1 items-center justify-center p-8 text-xs font-semibold text-muted-foreground gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        Đang tải Bảng điều khiển chỉ số...
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

const SyncAuditLogsModal = dynamic(
  () => import('@/components/modals/SyncAuditLogsModal').then((m) => m.SyncAuditLogsModal),
  { ssr: false },
);

type WorkspaceTab = 'studio' | 'schema' | 'metrics' | 'explorer' | 'dashboard' | 'export';

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
    case 'schema':
      return 'schema';
    case 'metrics':
      return 'catalog';
    case 'explorer':
      return 'explorer';
    case 'dashboard':
      return 'dashboard';
    case 'export':
      return 'export';
  }
}

function viewIdToTab(view: ViewId): WorkspaceTab {
  switch (view) {
    case 'ai-studio':
      return 'studio';
    case 'schema':
      return 'schema';
    case 'catalog':
      return 'metrics';
    case 'explorer':
      return 'explorer';
    case 'dashboard':
      return 'dashboard';
    case 'export':
      return 'export';
  }
}

export default function WorkspacePage() {
  const router = useRouter();
  const { user, token, logout, isLoading } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { currentWorkspace, permissions, role } = useWorkspace();
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
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [catalogRefreshKey, setCatalogRefreshKey] = useState(0);
  // Latest-ref so the SSE subscription stays stable across tab/layer changes.
  const refreshSemanticDataRef = useRef<() => Promise<void>>(async () => { });
  const [pendingSchema, setPendingSchema] = useState<{ tables: number; columns: number }>({
    tables: 0,
    columns: 0,
  });
  const [explorerInitialSelection, setExplorerInitialSelection] =
    useState<ExplorerInitialSelection | null>(null);
  const explorerSelectionKey = useRef(0);
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [syncStatus, setSyncStatus] = useState<SchemaSyncStatus | null>(null);
  const [hasHealedLogs, setHasHealedLogs] = useState(false);
  const [lastReadLogId, setLastReadLogId] = useState<number | null>(null);
  const lastNotifiedLogIdRef = useRef<number | null>(null);

  // Chat sessions state lifted to page level
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(false);

  const activeLayer = useMemo(
    () => layers.find((item) => item.id === selectedId) || layers[0] || null,
    [layers, selectedId],
  );
  const activeLayerId = activeLayer?.id;
  const semanticDbId = activeLayer?.semantic_db_id || (activeLayer ? Number(activeLayer.id) : undefined);
  const canUseDataAssistant = Boolean(permissions.can_use_data_assistant);
  const canUseMetricStudio = Boolean(permissions.can_use_metric_studio);
  const canManageSchema = Boolean(permissions.can_manage_schema);
  const canManageMetrics = Boolean(permissions.can_manage_metrics ?? permissions.can_create_metrics);
  const canSubmitMetric = Boolean(permissions.can_submit_metric);
  const canApproveMetrics = Boolean(permissions.can_approve_metrics);
  const canEditDashboard = Boolean(permissions.can_manage_metrics || role === 'data_lead' || role === 'admin');
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

  const autoSyncingRef = useRef(false);

  const checkSync = useCallback(async () => {
    if (!semanticDbId) return;
    try {
      const res = await getSyncStatusApi(semanticDbId);

      // Instant 100% Automatic Self-Healing: Trigger immediately if drift detected!
      if (!res.in_sync && !autoSyncingRef.current) {
        autoSyncingRef.current = true;
        try {
          const syncResult = await triggerSyncApi(semanticDbId);
          const dbId = String(semanticDbId);

          const [updatedStatus, metrics, review] = await Promise.all([
            getSyncStatusApi(semanticDbId),
            listMetricsApi(dbId, true),
            getSchemaReviewApi(dbId).catch(() => ({ pending_tables: 0, pending_columns: 0 })),
          ]);

          setSyncStatus(updatedStatus);
          setHasHealedLogs(
            updatedStatus.sync_status === 'healed' || updatedStatus.latest_log?.status === 'healed',
          );
          setLayers((current) =>
            current.map((item) =>
              item.id === activeLayerId || item.semantic_db_id === semanticDbId
                ? { ...item, metrics }
                : item,
            ),
          );
          setPendingSchema({ tables: review.pending_tables, columns: review.pending_columns });

          const summary = syncResult.log.changes_summary;
          const parts: string[] = [];
          const addedTables = summary?.added_tables || [];
          const droppedTables = summary?.dropped_tables || [];
          const renamedTables = summary?.renamed_tables || [];
          const addedColumns = summary?.added_columns || [];
          const droppedColumns = summary?.dropped_columns || [];
          const renamedColumns = summary?.renamed_columns || [];
          const healedMetrics = summary?.healed_metrics || [];
          const brokenMetrics = summary?.broken_metrics || [];

          if (addedTables.length > 0) parts.push(`Phát hiện ${addedTables.length} bảng mới (+${addedTables.join(', ')})`);
          if (droppedTables.length > 0) parts.push(`Xóa ${droppedTables.length} bảng (-${droppedTables.join(', ')})`);
          if (renamedTables.length > 0) parts.push(`${renamedTables.length} bảng đổi tên`);
          if (addedColumns.length > 0) parts.push(`Thêm ${addedColumns.length} cột mới`);
          if (droppedColumns.length > 0) parts.push(`Xóa ${droppedColumns.length} cột`);
          if (renamedColumns.length > 0) parts.push(`${renamedColumns.length} cột đổi tên`);
          if (healedMetrics.length > 0) parts.push(`${healedMetrics.length} chỉ số tự vá`);
          if (brokenMetrics.length > 0) parts.push(`${brokenMetrics.length} chỉ số cần rà soát`);

          const summaryText = parts.length > 0 ? parts.join(', ') : 'Cấu trúc đồng bộ thành công';
          notify(`AI vừa tự động đồng bộ: ${summaryText}!`);
          lastNotifiedLogIdRef.current = syncResult.log.id;
        } finally {
          autoSyncingRef.current = false;
        }
        return;
      }

      setSyncStatus(res);
      const isHealed = res.sync_status === 'healed' || res.latest_log?.status === 'healed';
      setHasHealedLogs(isHealed);

      if (
        isHealed &&
        res.latest_log?.status === 'healed' &&
        res.latest_log.id !== lastNotifiedLogIdRef.current
      ) {
        if (lastNotifiedLogIdRef.current !== null) {
          const dbId = String(semanticDbId);
          const [metrics, review] = await Promise.all([
            listMetricsApi(dbId, true).catch(() => null),
            getSchemaReviewApi(dbId).catch(() => null),
          ]);
          if (metrics) {
            setLayers((current) =>
              current.map((item) =>
                item.id === activeLayerId || item.semantic_db_id === semanticDbId
                  ? { ...item, metrics }
                  : item,
              ),
            );
          }
          if (review) {
            setPendingSchema({ tables: review.pending_tables, columns: review.pending_columns });
          }

          const summary = res.latest_log.changes_summary;
          const addedTables = summary?.added_tables || [];
          const droppedTables = summary?.dropped_tables || [];
          const healedCount = summary?.healed_metrics?.length || 0;
          const renamedCount = summary?.renamed_columns?.length || 0;
          const parts: string[] = [];
          if (addedTables.length > 0) parts.push(`Thêm bảng +${addedTables.join(', ')}`);
          if (droppedTables.length > 0) parts.push(`Xóa bảng -${droppedTables.join(', ')}`);
          if (renamedCount > 0) parts.push(`${renamedCount} cột đổi tên`);
          if (healedCount > 0) parts.push(`${healedCount} chỉ số tự vá`);
          if (parts.length > 0) {
            notify(`Đã tự động cập nhật: ${parts.join(', ')}!`);
          }
        }
        lastNotifiedLogIdRef.current = res.latest_log.id;
      }
    } catch {
      // Ignore if not applicable
    }
  }, [activeLayerId, notify, semanticDbId]);

  useEffect(() => {
    if (semanticDbId) {
      void checkSync();
      const interval = window.setInterval(() => {
        void checkSync();
      }, 3000);
      const onFocus = () => void checkSync();
      window.addEventListener('focus', onFocus);
      return () => {
        window.clearInterval(interval);
        window.removeEventListener('focus', onFocus);
      };
    }
  }, [checkSync, semanticDbId]);

  useEffect(() => {
    if (!token) return;
    void listNotificationsApi().then((data) => {
      setNotifications(data.items);
      setUnreadNotifications(data.unread_count);
    });
  }, [token, currentWorkspace?.id]);

  useEffect(() => {
    if (!token) return;
    return streamNotifications((payload) => {
      setNotifications(payload.items);
      setUnreadNotifications(payload.unread_count);
      // A new metric-request notification may have changed catalog data.
      setCatalogRefreshKey((current) => current + 1);
      // Approved requests create metrics the catalog must show without a reload.
      void refreshSemanticDataRef.current();
    });
  }, [token]);

  const openCatalog = useCallback(() => {
    // Already-on-catalog clicks do not remount the view, so nudge a refetch.
    setCatalogRefreshKey((current) => current + 1);
    setTab('metrics');
  }, []);

  const markAllNotificationsRead = useCallback(async () => {
    await markNotificationsReadApi();
    setUnreadNotifications(0);
    setNotifications((current) =>
      current.map((item) => ({ ...item, read_at: item.read_at || new Date().toISOString() })),
    );
  }, []);

  const markNotificationRead = useCallback(async (item: AppNotification) => {
    if (item.read_at) return;
    setNotifications((current) =>
      current.map((entry) => (entry.id === item.id ? { ...entry, read_at: new Date().toISOString() } : entry)),
    );
    setUnreadNotifications((current) => Math.max(0, current - 1));
    await markNotificationReadApi(item.id);
  }, []);

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

  const handleDashboardDrillDown = useCallback(
    (widget: DashboardWidgetConfig, datePreset: DashboardDatePreset | null) => {
      const dateFilters = resolveDrillDownDateFilters(widget, datePreset, new Date());
      explorerSelectionKey.current += 1;
      setExplorerInitialSelection({
        metricId: widget.metric_id,
        dimensionColId: widget.dimension_col_id ?? null,
        timeGrain: widget.time_grain ?? null,
        dateFilters,
        requestKey: explorerSelectionKey.current,
      });
      setTab('explorer');
    },
    [],
  );

  const refreshSemanticData = useCallback(async () => {
    if (!activeLayerId || !semanticDbId) return;
    const dbId = String(semanticDbId);
    try {
      const metrics = await listMetricsApi(dbId, true);
      setLayers((current) =>
        current.map((item) => (item.id === activeLayerId ? { ...item, metrics } : item)),
      );
      if (tab === 'explorer' || tab === 'dashboard') {
        const nextCatalog = await getSemanticCatalogApi(dbId);
        setCatalog(nextCatalog);
      }
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Không thể tải Semantic Layer');
    }
  }, [activeLayerId, semanticDbId, notify, tab]);

  useEffect(() => {
    refreshSemanticDataRef.current = refreshSemanticData;
  }, [refreshSemanticData]);

  // Load catalog on-demand when user opens Explorer or Dashboard tabs
  useEffect(() => {
    if ((tab === 'explorer' || tab === 'dashboard') && semanticDbId) {
      const dbId = String(semanticDbId);
      if (!catalog || catalog.db_id !== Number(semanticDbId)) {
        void getSemanticCatalogApi(dbId)
          .then((nextCatalog) => setCatalog(nextCatalog))
          .catch(() => { });
      }
    }
  }, [tab, semanticDbId, catalog]);

  const refreshSchemaReview = useCallback(async () => {
    if (!semanticDbId || !canManageSchema) {
      setPendingSchema({ tables: 0, columns: 0 });
      return;
    }
    try {
      const review = await getSchemaReviewApi(String(semanticDbId));
      setPendingSchema({ tables: review.pending_tables, columns: review.pending_columns });
    } catch {
      setPendingSchema({ tables: 0, columns: 0 });
    }
  }, [canManageSchema, semanticDbId]);

  useEffect(() => {
    void refreshSchemaReview();
  }, [refreshSchemaReview]);

  const saveDefinition = async (definition: MetricDefinition, changeReason?: string) => {
    const canSave = editingMetric ? canManageMetrics : canSubmitMetric;
    if (!canSave) {
      notify(METRIC_WRITE_PERMISSION_MESSAGE);
      throw new Error(METRIC_WRITE_PERMISSION_MESSAGE);
    }
    if (!activeLayer?.semantic_db_id) throw new Error('Semantic database chưa sẵn sàng');
    const dbId = String(activeLayer.semantic_db_id);
    try {
      let draftVersion: number | null = null;
      if (editingMetric) {
        const result = await updateMetricApi(dbId, editingMetric.metric_id, definition, changeReason);
        draftVersion = result.pendingVersion?.version ?? null;
      } else
        await createMetricApi(dbId, {
          definition,
          source: editingSuggestion ? 'ai' : 'manual',
        });
      await refreshSemanticData();
      notify(
        draftVersion !== null
          ? `Đã lưu bản sửa thành phiên bản v${draftVersion} chờ phê duyệt. Định nghĩa đang publish vẫn được dùng cho truy vấn.`
          : canManageMetrics
            ? 'Đã lưu metric.'
            : 'Đã gửi metric. Trạng thái: Chưa được xác minh.',
      );
    } catch (error) {
      if (isPermissionDenied(error)) notify(METRIC_WRITE_PERMISSION_MESSAGE);
      throw error;
    }
  };

  const removeMetric = async (metricId: number) => {
    if (!activeLayer?.semantic_db_id) return;
    try {
      await deleteMetricApi(String(activeLayer.semantic_db_id), metricId);
      await refreshSemanticData();
      notify('Đã chuyển metric vào Thùng rác.');
    } catch (error) {
      if (isPermissionDenied(error)) {
        notify(METRIC_WRITE_PERMISSION_MESSAGE);
      } else {
        notify(error instanceof Error ? error.message : 'Không thể xóa metric');
      }
    }
  };

  const restoreMetric = async (metricId: number) => {
    if (!canManageMetrics) return notify(METRIC_WRITE_PERMISSION_MESSAGE);
    if (!activeLayer?.semantic_db_id) return;
    try {
      await restoreMetricApi(String(activeLayer.semantic_db_id), metricId);
      await refreshSemanticData();
      notify('Đã khôi phục metric thành công.');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Không thể khôi phục metric');
    }
  };

  const permanentDeleteMetric = async (metricId: number) => {
    if (!canManageMetrics) return notify(METRIC_WRITE_PERMISSION_MESSAGE);
    if (!activeLayer?.semantic_db_id) return;
    try {
      await deleteMetricApi(String(activeLayer.semantic_db_id), metricId, true);
      await refreshSemanticData();
      notify('Đã xóa vĩnh viễn metric khỏi hệ thống.');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Không thể xóa vĩnh viễn metric');
    }
  };

  const emptyTrash = async () => {
    if (!canManageMetrics) return notify(METRIC_WRITE_PERMISSION_MESSAGE);
    if (!activeLayer?.semantic_db_id) return;
    const trashItems = activeLayer.metrics.filter((m) => Boolean(m.is_deleted));
    if (trashItems.length === 0) return;
    if (
      !window.confirm(
        `Bạn có chắc chắn muốn dọn sạch tất cả ${trashItems.length} chỉ số trong thùng rác? Hành động này không thể hoàn tác!`,
      )
    ) {
      return;
    }
    try {
      await Promise.all(
        trashItems.map((m) =>
          deleteMetricApi(String(activeLayer.semantic_db_id), m.metric_id, true),
        ),
      );
      await refreshSemanticData();
      notify(`Đã dọn sạch ${trashItems.length} chỉ số khỏi thùng rác.`);
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Không thể dọn sạch thùng rác');
    }
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
    ? activeLayer.metrics.filter((m) => !m.is_deleted && m.status !== 'approved').length
    : 0;
  const pendingSchemaCount = pendingSchema.tables + pendingSchema.columns;

  const isLatestLogUnread =
    syncStatus?.latest_log?.id != null && syncStatus.latest_log.id !== lastReadLogId;

  const healedChangesCount = isLatestLogUnread
    ? (syncStatus?.latest_log?.changes_summary?.added_tables?.length || 0) +
      (syncStatus?.latest_log?.changes_summary?.dropped_tables?.length || 0) +
      (syncStatus?.latest_log?.changes_summary?.renamed_tables?.length || 0) +
      (syncStatus?.latest_log?.changes_summary?.renamed_columns?.length || 0) +
      (syncStatus?.latest_log?.changes_summary?.healed_metrics?.length || 0) +
      (syncStatus?.latest_log?.changes_summary?.broken_metrics?.length || 0)
    : 0;

  const pendingDriftCount =
    healedChangesCount > 0
      ? healedChangesCount
      : hasHealedLogs && isLatestLogUnread
        ? 1
        : syncStatus && !syncStatus.in_sync && canManageSchema
          ? (syncStatus.drift_preview?.renamed_columns?.length || 0) +
            (syncStatus.drift_preview?.added_tables?.length || 0) +
            (syncStatus.drift_preview?.dropped_tables?.length || 0) || 1
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
      pendingSchemaCount={pendingSchemaCount}
      pendingDriftCount={pendingDriftCount}
      collapsed={sidebarCollapsed}
      userName={user?.name}
      chatSessions={sessions}
      activeChatSessionId={activeSessionId}
      loadingChatSessions={loadingSessions}
      canChat={canChat}
      chatMode={studioMode}
      onSelectView={(v) => {
        setExplorerInitialSelection(null);
        if (v === 'ai-studio' && !canChat) {
          setTab('metrics');
          return;
        }
        setTab(viewIdToTab(v));
      }}
      onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      onToggleTheme={toggleTheme}
      onSelectDatabase={(id) => {
        setExplorerInitialSelection(null);
        setSelectedId(id);
        const nextLayer = layers.find((item) => item.id === id);
        const nextCanChat = Boolean(
          permissions.can_use_chat &&
          (canUseDataAssistant || canUseMetricStudio) &&
          nextLayer?.source_type === 'live',
        );
        setTab(nextCanChat ? 'studio' : 'metrics');
      }}
      onRemoveDatabase={
        canManageSchema
          ? async (id) => {
            const layer = layers.find((l) => l.id === id);
            if (!layer || !token || !window.confirm(`Xóa database ${layer.db_name}?`)) return;
            await deleteDatabaseApi(layer.id, token);
            deleteLayer(layer.id);
            setLayers((current) => current.filter((item) => item.id !== layer.id));
          }
          : undefined
      }
      onConnectDatabase={canManageSchema ? () => setConnectOpen(true) : undefined}
      onOpenSettings={() => setSettingsOpen(true)}
      onOpenWorkspaceManagement={
        permissions.can_manage_members ? () => setWorkspaceManagementOpen(true) : undefined
      }
      onOpenSyncLogs={() => {
        setLastReadLogId(syncStatus?.latest_log?.id ?? 0);
        setSyncModalOpen(true);
      }}
      onLogout={logout}
      onSelectChatSession={canChat ? selectSession : undefined}
      onNewChatSession={canChat ? newChat : undefined}
      onDeleteChatSession={canChat ? removeSession : undefined}
      onRenameChatSession={canChat ? handleRenameSession : undefined}
      notifications={notifications}
      unreadNotifications={unreadNotifications}
      onOpenCatalog={openCatalog}
      onMarkAllNotificationsRead={markAllNotificationsRead}
      onMarkNotificationRead={markNotificationRead}
    >
      {toast && (
        <div className="fixed right-6 top-6 z-60 rounded-xl bg-card border border-border px-4 py-2.5 text-xs font-semibold text-foreground shadow-2xl animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="mr-2 inline h-4 w-4 text-emerald-500" />
          {toast}
        </div>
      )}

      {activeLayer ? (
        <>
          {(pendingCount > 0 || pendingSchemaCount > 0) && canApproveMetrics && (
            <div className="mx-6 mt-6 flex items-center justify-between gap-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-700 shadow-sm dark:text-amber-300">
              <div>
                <h3 className="text-sm font-semibold">Cần phê duyệt Schema &amp; Chỉ số</h3>
                <p className="mt-1 text-xs opacity-90">
                  {pendingSchemaCount > 0 && (
                    <>
                      {pendingSchema.tables} bảng và {pendingSchema.columns} cột đang chờ review tên
                      nghiệp vụ.{' '}
                    </>
                  )}
                  {pendingCount > 0 && <>{pendingCount} chỉ số đang chờ duyệt để chính thức sử dụng.</>}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {pendingSchemaCount > 0 && (
                  <Button
                    onClick={() => setTab('schema')}
                    variant="outline"
                    size="sm"
                    className="gap-2 text-xs font-semibold"
                  >
                    <ClipboardCheck className="h-4 w-4" />
                    Review Schema ({pendingSchemaCount})
                  </Button>
                )}
                {pendingCount > 0 && (
                  <Button onClick={approve} className="gap-2 text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white dark:bg-amber-500 dark:hover:bg-amber-600 dark:text-amber-950" size="sm">
                    <CheckCircle2 className="h-4 w-4" />
                    Duyệt {pendingCount} Chỉ số
                  </Button>
                )}
              </div>
            </div>
          )}
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
              onOpenCatalog={openCatalog}
              refreshKey={catalogRefreshKey}
            />
          )}
          {tab === 'schema' && (
            <SchemaReviewView
              dbId={activeLayer.semantic_db_id}
              database={layerToDatabase(activeLayer)}
              canManageSchema={canManageSchema}
              canApproveSchema={canApproveMetrics}
              onNotify={notify}
              onReviewChanged={refreshSchemaReview}
            />
          )}
          {tab === 'metrics' && (
            <MetricsCatalogView
              dbId={activeLayer.semantic_db_id}
              metrics={activeLayer.metrics}
              database={layerToDatabase(activeLayer)}
              canManageMetrics={canManageMetrics}
              canApproveMetrics={canApproveMetrics}
              canSubmitMetric={canSubmitMetric}
              onAddMetric={canManageMetrics ? () => openEditor() : undefined}
              onSubmitMetric={canSubmitMetric ? () => openEditor() : undefined}
              onDeleteMetric={canManageMetrics ? removeMetric : undefined}
              onPermanentDeleteMetric={canManageMetrics ? permanentDeleteMetric : undefined}
              onEmptyTrash={canManageMetrics ? emptyTrash : undefined}
              onRestoreMetric={canManageMetrics ? restoreMetric : undefined}
              onEditMetric={canManageMetrics ? (item) => openEditor(item) : undefined}
              onOpenStudio={canUseMetricStudio ? () => setTab('studio') : undefined}
              onApproveAll={canApproveMetrics ? approve : undefined}
              onApproveMetric={canApproveMetrics ? approveSingleMetric : undefined}
              onMetricsChanged={refreshSemanticData}
              refreshKey={catalogRefreshKey}
              onOpenSyncLogs={() => setSyncModalOpen(true)}
              hasHealedLogs={hasHealedLogs}
            />
          )}
          {tab === 'explorer' && (
            <MetricExplorerView
              dbId={activeLayer.semantic_db_id}
              metrics={activeLayer.metrics}
              catalog={catalog}
              theme={theme}
              database={layerToDatabase(activeLayer)}
              initialSelection={explorerInitialSelection}
            />
          )}
          {tab === 'dashboard' && activeLayer.semantic_db_id != null && (
            <MetricsDashboardView
              dbId={activeLayer.semantic_db_id}
              metrics={activeLayer.metrics}
              catalog={catalog}
              database={layerToDatabase(activeLayer)}
              canEdit={canEditDashboard}
              onDrillDown={handleDashboardDrillDown}
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
          {canManageSchema && (
            <Button onClick={() => setConnectOpen(true)} className="gap-2 text-xs">
              <Plus className="h-4 w-4" />
              Thêm kết nối Database
            </Button>
          )}
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
          onOpenSyncLogs={() => setSyncModalOpen(true)}
        />
      )}
      {syncModalOpen && semanticDbId && activeLayer && (
        <SyncAuditLogsModal
          isOpen={syncModalOpen}
          onClose={() => setSyncModalOpen(false)}
          databaseId={semanticDbId}
          databaseName={activeLayer.db_name}
          onSyncComplete={() => {
            void checkSync();
            if (token) void loadLayerDetail(activeLayer, token);
          }}
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
      ? await listMetricsApi(String(fullLayer.semantic_db_id), true).catch(() => [])
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
