import { Check, Edit2, History, RotateCcw, ShieldAlert, Sparkles, Trash2, User } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { MetricRecord } from '@/lib/api';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { StatusPill } from '@/components/workspace/shared';
import { metricName, renderMetricYaml } from '@/lib/metrics';

interface MetricCardProps {
  metric: MetricRecord;
  selected?: boolean;
  onToggleSelect?: (id: number) => void;
  onEdit?: (item: MetricRecord) => void;
  onDelete?: (id: number) => Promise<void> | void;
  onPermanentDelete?: (id: number) => Promise<void> | void;
  onHistory: (id: number) => Promise<void>;
  onApprove?: (id: number) => Promise<void> | void;
  onRestore?: (id: number) => Promise<void> | void;
}

export function MetricCard({
  metric,
  selected = false,
  onToggleSelect,
  onEdit,
  onDelete,
  onPermanentDelete,
  onHistory,
  onApprove,
  onRestore,
}: MetricCardProps) {
  const definition = metric.definition;
  const isDeleted = Boolean(metric.is_deleted);
  const isPending = metric.status !== 'approved' || Boolean(metric.has_pending_version);

  return (
    <article
      className={`group flex cursor-pointer flex-col justify-between rounded-lg border p-4 transition-colors hover:border-foreground/25 shadow-2xs space-y-3 ${
        selected ? 'border-primary bg-primary/5 ring-1 ring-primary/30' : 'border-border bg-card'
      }`}
      onClick={() => {
        if (onToggleSelect) onToggleSelect(metric.metric_id);
      }}
    >
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1 flex items-start gap-2.5">
            {onToggleSelect && (
              <input
                type="checkbox"
                checked={selected}
                onChange={(e) => {
                  e.stopPropagation();
                  onToggleSelect(metric.metric_id);
                }}
                className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary cursor-pointer accent-primary shrink-0"
                aria-label={`Select ${metricName(metric)}`}
              />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <h3 className="truncate font-medium text-foreground">{metricName(metric)}</h3>
                <span
                  className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                    metric.source === 'manual'
                      ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
                      : 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20'
                  }`}
                  title={metric.source === 'manual' ? 'Tạo thủ công' : 'AI đề xuất'}
                >
                  {metric.source === 'manual' ? (
                    <>
                      <User className="h-2.5 w-2.5" />
                      Thủ công
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-2.5 w-2.5" />
                      AI
                    </>
                  )}
                </span>
              </div>
              <p className="truncate font-mono text-[11px] text-muted-foreground">
                v{metric.version} · {metric.definition?.metric?.name || metric.name}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
            {isDeleted ? (
              <span className="inline-flex items-center rounded-full bg-destructive/15 px-2 py-0.5 text-[11px] font-medium text-destructive border border-destructive/30">
                Đã xóa
              </span>
            ) : (
              <>
                {metric.has_pending_version && (
                  <span className="inline-flex items-center rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-500 border border-amber-500/30">
                    ⚡ v{metric.pending_version_number || (metric.version || 1) + 1} chờ duyệt
                  </span>
                )}
                <StatusPill status={metric.status} />
              </>
            )}
          </div>
        </div>

        {definition ? (
          <>
            <div className="rounded-md border border-border bg-secondary/50 px-2.5 py-1.5">
              <code className="font-mono text-[11px] text-foreground">
                {definition.metric.formula.function}({definition.metric.formula.expression}) · Bảng:{' '}
                {definition.metric.base_entity}
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

          {!isDeleted && onEdit && (
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

          {!isDeleted && onDelete && (
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-muted-foreground hover:text-destructive cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm(`Chuyển metric "${metricName(metric)}" vào Thùng rác?`)) {
                  void onDelete(metric.metric_id);
                }
              }}
              title="Chuyển vào Thùng rác"
              aria-label={`Delete ${metricName(metric)}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>

        {isDeleted && (
          <div className="flex items-center gap-2">
            {onPermanentDelete && (
              <Button
                size="sm"
                variant="ghost"
                className="h-8 gap-1.5 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn metric "${metricName(metric)}"? Hành động này không thể hoàn tác!`)) {
                    void onPermanentDelete(metric.metric_id);
                  }
                }}
                title="Xóa vĩnh viễn khỏi hệ thống"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Xóa vĩnh viễn
              </Button>
            )}
            {onRestore && (
              <Button
                size="sm"
                variant="outline"
                className="h-8 gap-1.5 text-xs text-primary hover:text-primary cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  void onRestore(metric.metric_id);
                }}
                title="Khôi phục metric"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Khôi phục
              </Button>
            )}
          </div>
        )}

        {!isDeleted && isPending && onApprove && (
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
