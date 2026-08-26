'use client';

import {
  AlertTriangle,
  CheckCheck,
  CheckCircle2,
  Clock3,
  Plus,
  RotateCcw,
  Search,
  Send,
  Sigma,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { MetricCard } from '@/components/metrics/MetricCard';
import { MetricHistoryDialog } from '@/components/metrics/MetricHistoryDialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  approveMetricRequestApi,
  getMetricHistoryApi,
  listMetricRequestsApi,
  MetricDefinition,
  MetricHistory as MetricHistoryData,
  MetricRecord,
  MetricRequest,
  rejectMetricRequestApi,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import type { WorkspaceDatabase } from '@/components/workspace/shared';
import { ViewHeader } from '@/components/workspace/ViewHeader';
import { metricName } from '@/lib/metrics';

interface MetricsCatalogViewProps {
  dbId?: number | null;
  metrics: MetricRecord[];
  onAddMetric?: () => void;
  onDeleteMetric?: (id: number) => Promise<void> | void;
  onPermanentDeleteMetric?: (id: number) => Promise<void> | void;
  onEmptyTrash?: () => Promise<void> | void;
  onRestoreMetric?: (id: number) => Promise<void> | void;
  onEditMetric?: (metric: MetricRecord) => void;
  onOpenStudio?: () => void;
  onApproveAll?: () => Promise<void>;
  onApproveMetric?: (id: number) => Promise<void> | void;
  onSubmitMetric?: () => void;
  onMetricsChanged?: () => Promise<void> | void;
  canSubmitMetric?: boolean;
  refreshKey?: number;
  canManageMetrics?: boolean;
  canApproveMetrics?: boolean;
  database?: WorkspaceDatabase | null;
  onOpenSyncLogs?: () => void;
  hasHealedLogs?: boolean;
}

export function MetricsCatalogView(props: MetricsCatalogViewProps) {
  const [search, setSearch] = useState('');
  const [approving, setApproving] = useState(false);
  const [history, setHistory] = useState<MetricHistoryData | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [requests, setRequests] = useState<MetricRequest[]>([]);
  const [editingRequestId, setEditingRequestId] = useState<number | null>(null);
  const [editedDefinition, setEditedDefinition] = useState('');
  const [filterTab, setFilterTab] = useState<'all' | 'pending' | 'submitted' | 'approved' | 'trash'>('all');
  const canManage = Boolean(props.canManageMetrics);
  const canApprove = Boolean(props.canApproveMetrics);
  const isMemberSubmitter = props.canSubmitMetric === true && !canManage;

  const visibleMetrics = useMemo(
    () =>
      canManage || isMemberSubmitter
        ? props.metrics
        : props.metrics.filter((m) => m.status === 'approved'),
    [canManage, isMemberSubmitter, props.metrics],
  );

  useEffect(() => {
    if (!canManage || !props.dbId) return;
    void listMetricRequestsApi(String(props.dbId)).then(setRequests).catch(() => setRequests([]));
  }, [canManage, props.dbId, props.refreshKey]);

  const resolveRequest = async (
    request: MetricRequest,
    approved: boolean,
    definition?: MetricDefinition,
  ) => {
    if (!props.dbId) return;
    const result = approved
      ? await approveMetricRequestApi(String(props.dbId), request.id, definition)
      : await rejectMetricRequestApi(String(props.dbId), request.id);
    setRequests((current) => current.map((item) => (item.id === result.id ? result : item)));
    await props.onMetricsChanged?.();
  };

  const approveEditedRequest = async (request: MetricRequest) => {
    try {
      await resolveRequest(request, true, JSON.parse(editedDefinition) as MetricDefinition);
      setEditingRequestId(null);
    } catch {
      window.alert('Definition JSON không hợp lệ hoặc không thể được duyệt.');
    }
  };

  const filtered = useMemo(
    () =>
      visibleMetrics.filter((item) =>
        metricName(item).toLowerCase().includes(search.toLowerCase()),
      ),
    [search, visibleMetrics],
  );

  // Active (non-deleted) metrics
  const activeMetrics = useMemo(() => filtered.filter((item) => !item.is_deleted), [filtered]);

  const pendingMetrics = useMemo(
    () =>
      activeMetrics.filter(
        (item) =>
          item.status === 'pending_approval' ||
          item.status === 'needs_review' ||
          Boolean(item.has_pending_version) ||
          (canManage && item.status === 'unverified'),
      ),
    [canManage, activeMetrics],
  );

  const submittedMetrics = useMemo(
    () => activeMetrics.filter((item) => item.status === 'unverified'),
    [activeMetrics],
  );

  const approvedMetrics = useMemo(
    () => activeMetrics.filter((item) => item.status === 'approved'),
    [activeMetrics],
  );

  const trashMetrics = useMemo(
    () => filtered.filter((item) => Boolean(item.is_deleted)),
    [filtered],
  );

  const totalPending = visibleMetrics.filter(
    (item) =>
      !item.is_deleted &&
      (item.status === 'pending_approval' ||
        item.status === 'needs_review' ||
        Boolean(item.has_pending_version) ||
        (canManage && item.status === 'unverified')),
  ).length;

  const approveAll = async () => {
    if (!props.onApproveAll) return;
    setApproving(true);
    try {
      await props.onApproveAll();
    } finally {
      setApproving(false);
    }
  };

  const showHistory = async (metricId: number) => {
    if (!props.dbId) return;
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      setHistory(await getMetricHistoryApi(String(props.dbId), metricId));
    } catch {
      setHistoryError('Không thể tải lịch sử phiên bản. Vui lòng thử lại.');
    } finally {
      setHistoryLoading(false);
    }
  };

  const [selectedTrashIds, setSelectedTrashIds] = useState<number[]>([]);

  const toggleSelectTrash = (id: number) => {
    setSelectedTrashIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const handleSelectAllTrash = () => {
    if (selectedTrashIds.length === trashMetrics.length) {
      setSelectedTrashIds([]);
    } else {
      setSelectedTrashIds(trashMetrics.map((m) => m.metric_id));
    }
  };

  const handleBatchPermanentDelete = async () => {
    if (!props.onPermanentDeleteMetric || selectedTrashIds.length === 0) return;
    if (
      !window.confirm(
        `Bạn có chắc chắn muốn xóa vĩnh viễn ${selectedTrashIds.length} chỉ số đã chọn? Hành động này không thể hoàn tác!`,
      )
    ) {
      return;
    }
    for (const id of selectedTrashIds) {
      await props.onPermanentDeleteMetric(id);
    }
    setSelectedTrashIds([]);
  };

  const handleBatchRestore = async () => {
    if (!props.onRestoreMetric || selectedTrashIds.length === 0) return;
    for (const id of selectedTrashIds) {
      await props.onRestoreMetric(id);
    }
    setSelectedTrashIds([]);
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background text-foreground">
      <ViewHeader
        eyebrow="Catalog"
        title="Metrics Catalog"
        description="Human-in-the-loop review of every business metric before it enters the semantic layer."
        database={props.database}
        onOpenSyncLogs={props.onOpenSyncLogs}
        hasHealedLogs={props.hasHealedLogs}
        actions={
          <div className="flex items-center gap-2">
            {canManage && props.onAddMetric && (
              <Button
                size="sm"
                className="gap-1.5 text-xs cursor-pointer"
                onClick={props.onAddMetric}
              >
                <Plus className="h-3.5 w-3.5" />
                Thêm thủ công
              </Button>
            )}
            {isMemberSubmitter && props.onSubmitMetric && (
              <Button size="sm" className="gap-1.5 text-xs cursor-pointer" onClick={props.onSubmitMetric}>
                <Send className="h-3.5 w-3.5" />
                Gửi metric
              </Button>
            )}
            {props.onOpenStudio && (
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 text-xs cursor-pointer"
                onClick={props.onOpenStudio}
              >
                <Sparkles className="h-3.5 w-3.5" />
                {isMemberSubmitter ? 'Đề xuất với AI' : 'Sinh với AI'}
              </Button>
            )}
            {canApprove && props.onApproveAll && (
              <Button
                size="sm"
                className="gap-1.5 text-xs cursor-pointer"
                onClick={() => void approveAll()}
                disabled={!totalPending || approving}
              >
                <CheckCheck className="h-3.5 w-3.5" />
                {approving ? 'Đang duyệt...' : `Duyệt tất cả (${totalPending})`}
              </Button>
            )}
          </div>
        }
      />

      {!canManage && !props.canSubmitMetric && (
        <div
          role="status"
          className="border-b border-amber-500/30 bg-amber-500/10 px-6 py-2.5 text-xs text-amber-700 dark:text-amber-300"
        >
          Chế độ chỉ xem: catalog chỉ hiển thị các metric đã được phê duyệt.
        </div>
      )}

      {canManage && requests.some((item) => item.status === 'pending') && (
        <section className="border-b border-border bg-secondary/10 px-6 py-4">
          <h2 className="mb-3 text-sm font-semibold text-foreground">
            Yêu cầu metric từ Member ({requests.filter((item) => item.status === 'pending').length})
          </h2>
          <div className="grid gap-3 lg:grid-cols-2">
            {requests.filter((item) => item.status === 'pending').map((request) => (
              <article key={request.id} className="rounded-lg border border-border bg-card p-3 text-xs">
                <p className="font-semibold text-foreground">{request.definition.metric.name}</p>
                <p className="mt-1 font-mono text-muted-foreground">
                  {request.definition.metric.formula.function}({request.definition.metric.formula.expression})
                </p>
                {editingRequestId === request.id && (
                  <textarea
                    aria-label="Definition metric request"
                    className="mt-2 min-h-36 w-full rounded border border-border bg-background p-2 font-mono text-[11px]"
                    value={editedDefinition}
                    onChange={(event) => setEditedDefinition(event.target.value)}
                  />
                )}
                <div className="mt-3 flex gap-2">
                  {editingRequestId === request.id ? (
                    <Button size="sm" className="h-7 text-xs" onClick={() => void approveEditedRequest(request)}>
                      Duyệt definition đã sửa
                    </Button>
                  ) : (
                    <Button size="sm" className="h-7 text-xs" onClick={() => void resolveRequest(request, true)}>
                      Duyệt & tạo
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs"
                    onClick={() => {
                      setEditingRequestId(request.id);
                      setEditedDefinition(JSON.stringify(request.definition, null, 2));
                    }}
                  >
                    Chỉnh sửa definition
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => void resolveRequest(request, false)}>
                    Từ chối
                  </Button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm kiếm metric…"
            className="h-9 pl-9 text-xs"
          />
        </div>

        <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
          {[
            {
              key: 'all' as const,
              label: 'Tất cả',
              count:
                (isMemberSubmitter ? submittedMetrics.length : pendingMetrics.length) +
                approvedMetrics.length,
            },
            ...(canManage
              ? [
                {
                  key: 'pending' as const,
                  label: 'Chờ phê duyệt',
                  count: pendingMetrics.length,
                },
              ]
              : []),
            ...(isMemberSubmitter
              ? [
                {
                  key: 'submitted' as const,
                  label: 'Đã gửi',
                  count: submittedMetrics.length,
                },
              ]
              : []),
            {
              key: 'approved' as const,
              label: 'Đã phê duyệt',
              count: approvedMetrics.length,
            },
            ...(canManage
              ? [
                {
                  key: 'trash' as const,
                  label: 'Thùng rác',
                  count: trashMetrics.length,
                },
              ]
              : []),
          ].map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => {
                setFilterTab(f.key);
                setSelectedTrashIds([]);
              }}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors cursor-pointer',
                filterTab === f.key
                  ? 'bg-primary text-primary-foreground font-semibold'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {f.label}
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.2 text-[10px] font-mono',
                  filterTab === f.key
                    ? 'bg-primary-foreground/20 text-primary-foreground'
                    : 'bg-secondary text-secondary-foreground',
                )}
              >
                ({f.count})
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Main Catalog Body */}
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        {filterTab === 'trash' ? (
          <div>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-md border border-border bg-secondary text-destructive">
                  <Trash2 className="h-3.5 w-3.5" />
                </span>
                <div>
                  <h2 className="font-semibold text-sm text-foreground">Thùng rác</h2>
                  <p className="text-[11px] text-muted-foreground">
                    Các chỉ số đã xóa khỏi Semantic Layer. Bạn có thể khôi phục lại hoặc xóa vĩnh viễn.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {trashMetrics.length > 0 && (
                  <label className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer select-none bg-secondary/50 px-2.5 py-1 rounded-md border border-border">
                    <input
                      type="checkbox"
                      checked={
                        selectedTrashIds.length === trashMetrics.length && trashMetrics.length > 0
                      }
                      onChange={handleSelectAllTrash}
                      className="h-3.5 w-3.5 rounded border-border text-primary focus:ring-primary cursor-pointer accent-primary"
                    />
                    <span>
                      {selectedTrashIds.length > 0
                        ? `Đã chọn ${selectedTrashIds.length}/${trashMetrics.length}`
                        : 'Chọn tất cả'}
                    </span>
                  </label>
                )}

                {selectedTrashIds.length > 0 ? (
                  <>
                    {canManage && props.onPermanentDeleteMetric && (
                      <Button
                        size="sm"
                        variant="destructive"
                        className="h-7 text-xs cursor-pointer gap-1"
                        onClick={() => void handleBatchPermanentDelete()}
                      >
                        <Trash2 className="h-3 w-3" />
                        Xóa đã chọn ({selectedTrashIds.length})
                      </Button>
                    )}
                    {canManage && props.onRestoreMetric && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs text-primary hover:text-primary cursor-pointer gap-1"
                        onClick={() => void handleBatchRestore()}
                      >
                        <RotateCcw className="h-3 w-3" />
                        Khôi phục đã chọn ({selectedTrashIds.length})
                      </Button>
                    )}
                  </>
                ) : (
                  canManage &&
                  props.onEmptyTrash &&
                  trashMetrics.length > 0 && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 text-[11px] text-destructive hover:text-destructive hover:bg-destructive/10 cursor-pointer gap-1"
                      onClick={props.onEmptyTrash}
                    >
                      <Trash2 className="h-3 w-3" />
                      Dọn sạch thùng rác
                    </Button>
                  )
                )}

                <span className="rounded-full border border-border bg-secondary px-2.5 py-0.5 font-mono text-[10px] text-secondary-foreground">
                  {trashMetrics.length} chỉ số
                </span>
              </div>
            </div>

            {trashMetrics.length === 0 ? (
              <div className="flex h-full min-h-[250px] flex-col items-center justify-center gap-2 text-center">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-secondary text-muted-foreground">
                  <Trash2 className="h-5 w-5" />
                </div>
                <p className="text-xs text-muted-foreground">Thùng rác trống. Không có chỉ số nào bị xóa.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
                {trashMetrics.map((metric) => (
                  <MetricCard
                    key={metric.metric_id}
                    metric={metric}
                    selected={selectedTrashIds.includes(metric.metric_id)}
                    onToggleSelect={toggleSelectTrash}
                    onHistory={showHistory}
                    onRestore={props.onRestoreMetric}
                    onPermanentDelete={canManage ? props.onPermanentDeleteMetric : undefined}
                  />
                ))}
              </div>
            )}
          </div>
        ) : activeMetrics.length === 0 ? (
          <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-3 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-secondary text-muted-foreground">
              <Sigma className="h-6 w-6" />
            </div>
            <div>
              <p className="font-semibold text-foreground text-sm">Chưa có Metric Definition nào</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {!canManage
                  ? 'Chưa có metric nào để hiển thị trong catalog.'
                  : 'Hãy thêm thủ công hoặc sử dụng AI Studio để tự động phân tích schema và đề xuất các chỉ số.'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {canManage && props.onAddMetric && (
                <Button
                  size="sm"
                  onClick={props.onAddMetric}
                  className="gap-1.5 text-xs cursor-pointer"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Thêm thủ công
                </Button>
              )}
              {props.onOpenStudio && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={props.onOpenStudio}
                  className="gap-1.5 text-xs cursor-pointer"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Mở AI Studio
                </Button>
              )}
            </div>
          </div>
        ) : filterTab === 'all' ? (
          <div className="space-y-6">
            {(canManage || isMemberSubmitter) && (
              <section className="space-y-3">
                <div className="flex items-center justify-between border-b border-border pb-2">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-md border border-border bg-secondary text-amber-500">
                      <Clock3 className="h-3.5 w-3.5" />
                    </span>
                    <div>
                      <h2 className="font-semibold text-sm text-foreground">
                        {isMemberSubmitter ? '1. Đã gửi' : '1. Metrics Đang Chờ Phê Duyệt'}
                      </h2>
                      <p className="text-[11px] text-muted-foreground">
                        {isMemberSubmitter
                          ? 'Các metric bạn đã gửi đang chờ Data Lead xem xét'
                          : 'Các chỉ số cần Data Lead review và phê duyệt'}
                      </p>
                    </div>
                  </div>
                  <span className="rounded-full border border-border bg-secondary px-2.5 py-0.5 font-mono text-[10px] text-secondary-foreground">
                    {isMemberSubmitter ? submittedMetrics.length : pendingMetrics.length} chỉ số
                  </span>
                </div>

                {(isMemberSubmitter ? submittedMetrics : pendingMetrics).length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border bg-card/50 p-6 text-center text-xs text-muted-foreground">
                    Không có metric nào đang chờ duyệt.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
                    {(isMemberSubmitter ? submittedMetrics : pendingMetrics).map((metric) => (
                      <MetricCard
                        key={metric.metric_id}
                        metric={metric}
                        onEdit={canManage ? props.onEditMetric : undefined}
                        onDelete={canManage ? props.onDeleteMetric : undefined}
                        onHistory={showHistory}
                        onApprove={canApprove ? props.onApproveMetric : undefined}
                      />
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* Section 2: Approved */}
            <section className="space-y-3">
              <div className="flex items-center justify-between border-b border-border pb-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md border border-border bg-secondary text-emerald-500">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  </span>
                  <div>
                    <h2 className="font-semibold text-sm text-foreground">
                      2. Metrics Đã Phê Duyệt (Official Metrics)
                    </h2>
                    <p className="text-[11px] text-muted-foreground">
                      Các chỉ số chuẩn hóa đã sẵn sàng để truy vấn trong Metric Explorer và Export
                    </p>
                  </div>
                </div>
                <span className="rounded-full border border-border bg-secondary px-2.5 py-0.5 font-mono text-[10px] text-secondary-foreground">
                  {approvedMetrics.length} chỉ số
                </span>
              </div>

              {approvedMetrics.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border bg-card/50 p-6 text-center text-xs text-muted-foreground">
                  {canApprove
                    ? 'Chưa có metric nào được phê duyệt. Hãy duyệt các metric ở phần trên.'
                    : 'Chưa có metric nào được phê duyệt.'}
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
                  {approvedMetrics.map((metric) => (
                    <MetricCard
                      key={metric.metric_id}
                      metric={metric}
                      onEdit={canManage ? props.onEditMetric : undefined}
                      onDelete={canManage ? props.onDeleteMetric : undefined}
                      onHistory={showHistory}
                      onApprove={canApprove ? props.onApproveMetric : undefined}
                    />
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {(filterTab === 'pending'
              ? pendingMetrics
              : filterTab === 'submitted'
                ? submittedMetrics
                : approvedMetrics
            ).map((metric) => (
              <MetricCard
                key={metric.metric_id}
                metric={metric}
                onEdit={canManage ? props.onEditMetric : undefined}
                onDelete={canManage ? props.onDeleteMetric : undefined}
                onHistory={showHistory}
                onApprove={canApprove ? props.onApproveMetric : undefined}
              />
            ))}
          </div>
        )}
      </div>

      {historyLoading && (
        <div
          role="status"
          className="fixed bottom-6 left-6 z-50 rounded-lg border border-border bg-card px-4 py-2 text-xs text-muted-foreground shadow-lg"
        >
          Đang tải lịch sử phiên bản...
        </div>
      )}
      {historyError && (
        <div
          role="alert"
          className="fixed bottom-6 left-6 z-50 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-xs text-red-600 shadow-lg dark:text-red-400"
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          {historyError}
        </div>
      )}

      {history && props.dbId && (
        <MetricHistoryDialog
          history={history}
          dbId={props.dbId}
          canManage={canManage}
          canApprove={canApprove}
          onClose={() => setHistory(null)}
          onEdit={() => {
            const item = props.metrics.find((m) => m.metric_id === history.metric_id);
            if (item && props.onEditMetric) {
              props.onEditMetric(item);
            }
          }}
          onMetricsChanged={props.onMetricsChanged}
        />
      )}
    </div>
  );
}
