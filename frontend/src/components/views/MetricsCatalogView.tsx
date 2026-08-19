'use client';

import {
  Check,
  CheckCheck,
  CheckCircle2,
  Clock3,
  Edit2,
  History,
  Search,
  ShieldAlert,
  Sigma,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getMetricHistoryApi, MetricHistory as MetricHistoryData, MetricRecord } from '@/lib/api';
import { cn } from '@/lib/utils';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { StatusPill, type WorkspaceDatabase } from '@/components/workspace/shared';
import { ViewHeader } from '@/components/workspace/ViewHeader';
import { metricName, renderMetricYaml } from '@/lib/metrics';

interface MetricsCatalogViewProps {
  dbId?: number | null;
  metrics: MetricRecord[];
  onDeleteMetric?: (id: number) => Promise<void> | void;
  onEditMetric?: (metric: MetricRecord) => void;
  onOpenStudio?: () => void;
  onApproveAll?: () => Promise<void>;
  onApproveMetric?: (id: number) => Promise<void> | void;
  canManageMetrics?: boolean;
  database?: WorkspaceDatabase | null;
}

export function MetricsCatalogView(props: MetricsCatalogViewProps) {
  const [search, setSearch] = useState('');
  const [approving, setApproving] = useState(false);
  const [history, setHistory] = useState<MetricHistoryData | null>(null);
  const [filterTab, setFilterTab] = useState<'all' | 'pending' | 'approved'>('all');

  const filtered = useMemo(
    () =>
      props.metrics.filter((item) =>
        metricName(item).toLowerCase().includes(search.toLowerCase()),
      ),
    [props.metrics, search],
  );

  const pendingMetrics = useMemo(
    () =>
      filtered.filter(
        (item) => item.status === 'pending_approval' || item.status === 'needs_review',
      ),
    [filtered],
  );

  const approvedMetrics = useMemo(
    () => filtered.filter((item) => item.status === 'approved'),
    [filtered],
  );

  const totalPending = props.metrics.filter(
    (item) => item.status === 'pending_approval' || item.status === 'needs_review',
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
    if (props.dbId) setHistory(await getMetricHistoryApi(String(props.dbId), metricId));
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background text-foreground">
      <ViewHeader
        title="Metrics Catalog"
        description="Human-in-the-loop review of every business metric before it enters the semantic layer."
        database={props.database}
        actions={
          <div className="flex items-center gap-2">
            {props.onOpenStudio && (
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 text-xs cursor-pointer"
                onClick={props.onOpenStudio}
              >
                <Sparkles className="h-3.5 w-3.5" />
                Sinh với AI
              </Button>
            )}
            {props.onApproveAll && (
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

      {props.canManageMetrics === false && (
        <div role="status" className="border-b border-amber-500/30 bg-amber-500/10 px-6 py-2.5 text-xs text-amber-700 dark:text-amber-300">
          Chế độ chỉ xem: bạn không có quyền lưu, chỉnh sửa, xóa hoặc phê duyệt metric. Hãy liên hệ Data Lead nếu cần thay đổi.
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
            { key: 'all' as const, label: 'Tất cả', count: filtered.length },
            { key: 'pending' as const, label: 'Chờ phê duyệt', count: pendingMetrics.length },
            { key: 'approved' as const, label: 'Đã phê duyệt', count: approvedMetrics.length },
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
                {props.canManageMetrics === false
                  ? 'Chưa có metric đã phê duyệt để xem. Hãy liên hệ Data Lead để tạo và phê duyệt metric.'
                  : 'Hãy sử dụng Metric Studio để tự động phân tích schema và đề xuất các chỉ số.'}
              </p>
            </div>
            {props.onOpenStudio && (
              <Button size="sm" onClick={props.onOpenStudio} className="gap-1.5 text-xs cursor-pointer">
                <Sparkles className="h-3.5 w-3.5" />
                Mở AI Studio
              </Button>
            )}
          </div>
        ) : filterTab === 'all' ? (
          <div className="space-y-6">
            {/* Section 1: Pending Approval */}
            <section className="space-y-3">
              <div className="flex items-center justify-between border-b border-border pb-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md border border-border bg-secondary text-amber-500">
                    <Clock3 className="h-3.5 w-3.5" />
                  </span>
                  <div>
                    <h2 className="font-semibold text-sm text-foreground">
                      1. Metrics Đang Chờ Phê Duyệt
                    </h2>
                    <p className="text-[11px] text-muted-foreground">
                      Các chỉ số do AI đề xuất hoặc vừa chỉnh sửa, cần HITL review và phê duyệt
                    </p>
                  </div>
                </div>
                <span className="rounded-full border border-border bg-secondary px-2.5 py-0.5 font-mono text-[10px] text-secondary-foreground">
                  {pendingMetrics.length} chỉ số
                </span>
              </div>

              {pendingMetrics.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border bg-card/50 p-6 text-center text-xs text-muted-foreground">
                  ✨ Không có metric nào đang chờ duyệt.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
                  {pendingMetrics.map((metric) => (
                    <MetricCard
                      key={metric.metric_id}
                      metric={metric}
                      onEdit={props.onEditMetric}
                      onDelete={props.onDeleteMetric}
                      onHistory={showHistory}
                      onApprove={props.onApproveMetric}
                    />
                  ))}
                </div>
              )}
            </section>

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
                  Chưa có metric nào được phê duyệt. Hãy duyệt các metric ở phần trên.
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
                  {approvedMetrics.map((metric) => (
                    <MetricCard
                      key={metric.metric_id}
                      metric={metric}
                      onEdit={props.onEditMetric}
                      onDelete={props.onDeleteMetric}
                      onHistory={showHistory}
                      onApprove={props.onApproveMetric}
                    />
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {(filterTab === 'pending' ? pendingMetrics : approvedMetrics).map((metric) => (
              <MetricCard
                key={metric.metric_id}
                metric={metric}
                onEdit={props.onEditMetric}
                onDelete={props.onDeleteMetric}
                onHistory={showHistory}
                onApprove={props.onApproveMetric}
              />
            ))}
          </div>
        )}
      </div>

      {history && <HistoryDialog history={history} onClose={() => setHistory(null)} />}
    </div>
  );
}

function MetricCard({
  metric,
  onEdit,
  onDelete,
  onHistory,
  onApprove,
}: {
  metric: MetricRecord;
  onEdit?: (item: MetricRecord) => void;
  onDelete?: (id: number) => Promise<void> | void;
  onHistory: (id: number) => Promise<void>;
  onApprove?: (id: number) => Promise<void> | void;
}) {
  const definition = metric.definition;
  const isPending = metric.status === 'pending_approval' || metric.status === 'needs_review';

  return (
    <article className="group flex cursor-pointer flex-col justify-between rounded-lg border border-border bg-card p-4 transition-colors hover:border-foreground/25 shadow-2xs space-y-3">
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate font-medium text-foreground">{metricName(metric)}</h3>
            <p className="truncate font-mono text-[11px] text-muted-foreground">
              v{metric.version} · {metric.definition?.metric?.name || metric.name}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <StatusPill status={metric.status} />
            <span className="font-mono text-[10px] text-muted-foreground">
              {metric.status === 'approved' ? 'Đã duyệt' : 'Chờ duyệt'}
            </span>
          </div>
        </div>

        {definition ? (
          <>
            <div className="rounded-md border border-border bg-secondary/50 px-2.5 py-1.5">
              <code className="font-mono text-[11px] text-foreground">
                {definition.metric.formula.function}({definition.metric.formula.expression}) · Bảng: {definition.metric.base_entity}
              </code>
            </div>
            {definition.metric.excluded_notes && (
              <p className="line-clamp-2 text-xs text-muted-foreground">
                {definition.metric.excluded_notes}
              </p>
            )}
            <details className="text-xs pt-1">
              <summary className="cursor-pointer font-mono text-[11px] text-muted-foreground hover:text-foreground">
                Xem YAML definition
              </summary>
              <div className="mt-2 overflow-hidden rounded-md border border-border">
                <YamlCodeViewer yaml={renderMetricYaml(definition)} />
              </div>
            </details>
          </>
        ) : (
          <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-600 dark:text-amber-400">
            <ShieldAlert className="mr-1 inline h-3.5 w-3.5" />
            Metric legacy chưa có canonical definition.
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-border pt-3">
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-foreground cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              void onHistory(metric.metric_id);
            }}
            title="Xem lịch sử phiên bản"
          >
            <History className="h-3.5 w-3.5" />
          </Button>

          {onEdit && (
            <Button
              size="sm"
              variant="ghost"
              className="h-8 gap-1 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onEdit(metric);
              }}
            >
              <Edit2 className="h-3 w-3" />
              {definition ? 'Chỉnh sửa' : 'Chuẩn hóa'}
            </Button>
          )}

          {onDelete && (
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-destructive cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm(`Xóa metric ${metricName(metric)}?`)) {
                  void onDelete(metric.metric_id);
                }
              }}
              title="Xóa metric"
              aria-label={`Delete ${metricName(metric)}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>

        {isPending && onApprove && (
          <Button
            size="sm"
            className="h-8 gap-1.5 text-xs cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              void onApprove(metric.metric_id);
            }}
            title="Phê duyệt chỉ số này"
          >
            <Check className="h-3.5 w-3.5" />
            Duyệt chỉ số này
          </Button>
        )}
      </div>
    </article>
  );
}

function HistoryDialog({ history, onClose }: { history: MetricHistoryData; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-xl border border-border bg-background p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <h3 className="font-semibold text-foreground text-sm">Lịch sử · {history.metric_name}</h3>
          <Button variant="ghost" size="sm" onClick={onClose} className="h-7 text-xs cursor-pointer">
            Đóng
          </Button>
        </div>
        <div className="mt-4 space-y-3">
          {history.versions.map((version) => (
            <div key={version.version} className="rounded-lg border border-border bg-card p-3">
              <p className="mb-2 font-mono text-xs font-semibold text-foreground">
                Version {version.version} · {new Date(version.created_at).toLocaleString()}
              </p>
              {version.definition ? (
                <YamlCodeViewer yaml={renderMetricYaml(version.definition)} />
              ) : (
                <p className="text-xs text-amber-500">Phiên bản legacy không có definition.</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
