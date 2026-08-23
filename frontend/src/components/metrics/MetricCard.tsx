'use client';

import { Check, Edit2, History, ShieldAlert, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { MetricRecord } from '@/lib/api';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { StatusPill } from '@/components/workspace/shared';
import { metricName, renderMetricYaml } from '@/lib/metrics';

interface MetricCardProps {
  metric: MetricRecord;
  onEdit?: (item: MetricRecord) => void;
  onDelete?: (id: number) => Promise<void> | void;
  onHistory: (id: number) => Promise<void>;
  onApprove?: (id: number) => Promise<void> | void;
}

export function MetricCard({ metric, onEdit, onDelete, onHistory, onApprove }: MetricCardProps) {
  const definition = metric.definition;
  const isPending = metric.status !== 'approved';

  return (
    <article className="group flex cursor-pointer flex-col justify-between rounded-lg border border-border bg-card p-4 transition-colors hover:border-foreground/25 shadow-2xs space-y-3">
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="truncate font-medium text-foreground">{metricName(metric)}</h3>
            <p className="truncate font-mono text-[11px] text-muted-foreground">
              v{metric.version} · {metric.definition?.metric?.name || metric.name}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
            <StatusPill status={metric.status} />
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
