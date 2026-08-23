'use client';

import {
  AlertTriangle,
  CheckCheck,
  CheckCircle2,
  Clock3,
  Search,
  Sigma,
  Sparkles,
  Send,
} from 'lucide-react';
import { useMemo, useState } from 'react';

import { MetricCard } from '@/components/metrics/MetricCard';
import { MetricHistoryDialog } from '@/components/metrics/MetricHistoryDialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getMetricHistoryApi, MetricHistory as MetricHistoryData, MetricRecord } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { WorkspaceDatabase } from '@/components/workspace/shared';
import { ViewHeader } from '@/components/workspace/ViewHeader';
import { metricName } from '@/lib/metrics';

interface MetricsCatalogViewProps {
  dbId?: number | null;
  metrics: MetricRecord[];
  onDeleteMetric?: (id: number) => Promise<void> | void;
  onEditMetric?: (metric: MetricRecord) => void;
  onOpenStudio?: () => void;
  onApproveAll?: () => Promise<void>;
  onApproveMetric?: (id: number) => Promise<void> | void;
  onSubmitMetric?: () => void;
  onMetricsChanged?: () => Promise<void> | void;
  canSubmitMetric?: boolean;
  canManageMetrics?: boolean;
  canApproveMetrics?: boolean;
  database?: WorkspaceDatabase | null;
}

export function MetricsCatalogView(props: MetricsCatalogViewProps) {
  const [search, setSearch] = useState('');
  const [approving, setApproving] = useState(false);
  const [history, setHistory] = useState<MetricHistoryData | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [filterTab, setFilterTab] = useState<'all' | 'pending' | 'submitted' | 'approved'>('all');
  const canManage = Boolean(props.canManageMetrics);
  const canApprove = Boolean(props.canApproveMetrics);
  const isMemberSubmitter = props.canSubmitMetric === true && !canManage;
  const visibleMetrics = useMemo(
    () =>
      canManage || isMemberSubmitter
        ? props.metrics
        : props.metrics.filter((item) => item.status === 'approved'),
    [canManage, isMemberSubmitter, props.metrics],
  );

  const filtered = useMemo(
    () =>
      visibleMetrics.filter((item) =>
        metricName(item).toLowerCase().includes(search.toLowerCase()),
      ),
    [search, visibleMetrics],
  );

  const pendingMetrics = useMemo(
    () =>
      filtered.filter(
        (item) =>
          item.status === 'pending_approval' ||
          item.status === 'needs_review' ||
          (canManage && item.status === 'unverified'),
      ),
    [canManage, filtered],
  );

  const submittedMetrics = useMemo(
    () => filtered.filter((item) => item.status === 'unverified'),
    [filtered],
  );

  const approvedMetrics = useMemo(
    () => filtered.filter((item) => item.status === 'approved'),
    [filtered],
  );

  const totalPending = visibleMetrics.filter(
    (item) =>
      item.status === 'pending_approval' ||
      item.status === 'needs_review' ||
      (canManage && item.status === 'unverified'),
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

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background text-foreground">
      <ViewHeader
        title="Metrics Catalog"
        description="Human-in-the-loop review of every business metric before it enters the semantic layer."
        database={props.database}
        actions={
          <div className="flex items-center gap-2">
            {isMemberSubmitter && props.onSubmitMetric && (
              <Button size="sm" className="gap-1.5 text-xs" onClick={props.onSubmitMetric}>
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
                <CheckCheck className="h-4 w-4" />
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

      {/* Search & Filter Toolbar */}
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
          ].map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilterTab(f.key)}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors cursor-pointer',
                filterTab === f.key
                  ? 'bg-primary text-primary-foreground font-semibold'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {`${f.label} (${f.count})`}
            </button>
          ))}
        </div>
      </div>

      {/* Main Catalog Body */}
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        {filtered.length === 0 ? (
          <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-3 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-secondary text-muted-foreground">
              <Sigma className="h-6 w-6" />
            </div>
            <div>
              <p className="font-semibold text-foreground text-sm">Chưa có Metric Definition nào</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {!canManage
                  ? 'Chưa có metric nào để hiển thị trong catalog.'
                  : 'Hãy sử dụng Metric Studio để tự động phân tích schema và đề xuất các chỉ số.'}
              </p>
            </div>
            {props.onOpenStudio && (
              <Button
                size="sm"
                onClick={props.onOpenStudio}
                className="gap-1.5 text-xs cursor-pointer"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Mở AI Studio
              </Button>
            )}
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
          onClose={() => setHistory(null)}
          onMetricsChanged={props.onMetricsChanged}
        />
      )}
    </div>
  );
}
