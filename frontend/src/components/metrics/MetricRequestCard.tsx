'use client';

import { Check, Edit2, Trash2, User } from 'lucide-react';

import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { Button } from '@/components/ui/button';
import { StatusPill } from '@/components/workspace/shared';
import { MetricRequest } from '@/lib/api';
import { renderMetricYaml } from '@/lib/metrics';

interface MetricRequestCardProps {
  request: MetricRequest;
  onEdit?: (request: MetricRequest) => void;
  onApprove: (request: MetricRequest) => void;
  onReject: (request: MetricRequest) => void;
}

export function MetricRequestCard({
  request,
  onEdit,
  onApprove,
  onReject,
}: MetricRequestCardProps) {
  const definition = request.definition;
  const name = definition?.metric?.name || `Metric #${request.id}`;
  const formulaStr = definition?.metric?.formula
    ? `${definition.metric.formula.function}(${definition.metric.formula.expression || ''})`
    : 'N/A';
  const entityStr = definition?.metric?.base_entity || 'N/A';

  return (
    <article className="group flex flex-col justify-between rounded-lg border border-border bg-card p-4 transition-colors hover:border-foreground/25 shadow-2xs space-y-3">
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1 flex items-start gap-2.5">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <h3 className="truncate font-medium text-foreground text-sm">{name}</h3>
                <span
                  className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 shrink-0"
                  title="Member đề xuất"
                >
                  <User className="h-2.5 w-2.5" />
                  Member đề xuất
                </span>
              </div>
              <p className="truncate font-mono text-[11px] text-muted-foreground mt-0.5">
                Đề xuất bởi Member · Bảng: {entityStr}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
            <StatusPill status="pending_approval" />
          </div>
        </div>

        {definition ? (
          <>
            <div className="rounded-md border border-border bg-secondary/50 px-2.5 py-1.5">
              <code className="font-mono text-[11px] text-foreground">
                {formulaStr} · Bảng: {entityStr}
              </code>
            </div>
            {definition.metric?.excluded_notes && (
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
            Chưa có definition.
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-border pt-3">
        <div className="flex items-center gap-1">
          {onEdit && (
            <Button
              size="sm"
              variant="ghost"
              className="h-8 gap-1 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
              onClick={() => onEdit(request)}
              title="Chỉnh sửa định nghĩa trong modal"
            >
              <Edit2 className="h-3 w-3" />
              Chỉnh sửa
            </Button>
          )}

          <Button
            size="sm"
            variant="ghost"
            className="h-8 gap-1 text-xs text-muted-foreground hover:text-destructive cursor-pointer"
            onClick={() => {
              if (window.confirm(`Từ chối đề xuất metric "${name}"?`)) {
                void onReject(request);
              }
            }}
            title="Từ chối đề xuất này"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Từ chối
          </Button>
        </div>

        <Button
          size="sm"
          className="h-8 gap-1.5 text-xs cursor-pointer"
          onClick={() => void onApprove(request)}
          title="Phê duyệt và tạo metric này"
        >
          <Check className="h-3.5 w-3.5" />
          Duyệt & tạo
        </Button>
      </div>
    </article>
  );
}
