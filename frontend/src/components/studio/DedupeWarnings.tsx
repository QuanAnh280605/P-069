'use client';

import {
  AlertTriangle,
  Calculator,
  CheckCircle2,
  ChevronDown,
  Code2,
  Database,
  Eye,
  Filter,
  Info,
  Table2,
  X,
} from 'lucide-react';
import { useState } from 'react';

import { DuplicateMetricNotice, MetricConflictInfo, MetricDefinition } from '@/lib/api';
import { statusLabel } from '@/lib/metrics';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';

// ---------------------------------------------------------------------------
// ⚠️ Conflict clarify strip (same name as a saved metric, different formula)
// ---------------------------------------------------------------------------

interface ConflictWarningStripProps {
  conflict: MetricConflictInfo;
  onRename: () => void;
  onUseExisting: () => void;
}

export function ConflictWarningStrip({ conflict, onRename, onUseExisting }: ConflictWarningStripProps) {
  const suggestedName = conflict.suggested_name?.trim() || '';
  return (
    <div className="space-y-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
        <div className="space-y-0.5">
          <p className="font-bold leading-relaxed">
            {conflict.clarify_question || 'Tên metric bị trùng với metric đã có'}
          </p>
          <p className="text-[11px] text-amber-700 dark:text-amber-300">
            Metric đang lưu:{' '}
            <strong>&quot;{conflict.existing_metric_name}&quot;</strong>
            {conflict.existing_metric_status ? ` (trạng thái: ${statusLabel(conflict.existing_metric_status)})` : ''}
            {suggestedName ? <> — gợi ý tên mới: <strong>&quot;{suggestedName}&quot;</strong></> : null}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 pl-6">
        <button
          type="button"
          disabled={!suggestedName}
          onClick={onRename}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-md bg-amber-600 px-3 py-1.5 text-xs font-bold text-white shadow-xs transition-all hover:bg-amber-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Đổi tên
        </button>
        <button
          type="button"
          onClick={onUseExisting}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-amber-500/40 bg-card px-3 py-1.5 text-xs font-medium text-foreground shadow-xs transition-all hover:bg-accent"
        >
          Dùng metric có sẵn
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 🔁 Duplicate notice card (proposal already exists — preview & let user decide)
// ---------------------------------------------------------------------------

/** Notice extended with FE-only UI state (stored on the chat message). */
export interface ChatDuplicateNotice extends DuplicateMetricNotice {
  /** FE-only: the user confirmed reusing the existing metric. */
  resolved?: boolean;
}

interface DuplicateNoticeCardProps {
  notice: ChatDuplicateNotice;
  onDismiss: () => void;
  onUseExisting?: () => void;
}

export function DuplicateNoticeCard({ notice, onDismiss, onUseExisting }: DuplicateNoticeCardProps) {
  const [showExisting, setShowExisting] = useState(false);

  if (notice.resolved) {
    return (
      <div className="relative rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-3.5 pr-10 text-xs text-emerald-800 dark:text-emerald-300">
        <DismissNoticeButton onDismiss={onDismiss} />
        <div className="flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <div className="space-y-1">
            <p className="font-medium leading-relaxed">
              Đã chọn dùng metric có sẵn &quot;{notice.existing_metric_name}&quot; — không tạo metric mới. Xem trong
              danh sách metric của Semantic Layer.
            </p>
            <p className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
              🎯 Hãy cùng tạo metric tiếp theo nhé!
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative rounded-lg border border-border bg-secondary/30 p-3.5 pr-10 text-xs text-foreground">
      <DismissNoticeButton onDismiss={onDismiss} />
      <div className="flex items-start gap-2">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="space-y-0.5">
          <p className="font-medium leading-relaxed">{notice.user_message}</p>
          {notice.similarity_reason ? (
            <p className="text-[11px] text-muted-foreground">{notice.similarity_reason}</p>
          ) : null}
        </div>
      </div>

      {showExisting && notice.existing_definition ? (
        <ExistingMetricPreview
          definition={notice.existing_definition}
          yaml={notice.existing_yaml || ''}
          status={notice.existing_metric_status}
        />
      ) : null}

      <div className="mt-2.5 flex flex-wrap items-center gap-2 pl-6">
        {notice.existing_definition ? (
          <button
            type="button"
            onClick={() => setShowExisting((prev) => !prev)}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-semibold text-muted-foreground transition-all hover:bg-secondary hover:text-foreground"
          >
            <Eye className="h-3.5 w-3.5 text-primary" />
            <span>{showExisting ? 'Ẩn metric có sẵn' : 'Xem metric có sẵn'}</span>
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showExisting ? 'rotate-180' : ''}`} />
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => onUseExisting?.()}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground shadow-xs transition-all hover:bg-accent"
        >
          Dùng metric có sẵn
        </button>
      </div>
    </div>
  );
}

function DismissNoticeButton({ onDismiss }: { onDismiss: () => void }) {
  return (
    <button
      type="button"
      onClick={onDismiss}
      aria-label="Đóng thông báo trùng lặp"
      className="absolute right-2.5 top-2.5 inline-flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-all hover:bg-secondary hover:text-foreground"
    >
      <X className="h-3.5 w-3.5" />
    </button>
  );
}

// ---------------------------------------------------------------------------
// 👁 Read-only preview of the saved (existing) metric — shown inside the chat
// ---------------------------------------------------------------------------

interface ExistingMetricPreviewProps {
  definition: MetricDefinition;
  yaml: string;
  status: string | null;
}

function ExistingMetricPreview({ definition, yaml, status }: ExistingMetricPreviewProps) {
  const [showYaml, setShowYaml] = useState(false);
  const metric = definition.metric;
  return (
    <div className="mt-2.5 ml-6 space-y-2.5 rounded-lg border border-border bg-background p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
          Metric có sẵn trong hệ thống
        </p>
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-bold text-muted-foreground">
          {statusLabel(status ?? metric.status)}
        </span>
      </div>
      <p className="text-sm font-bold text-foreground">{metric.name}</p>

      <div className="space-y-1.5 text-[11px] text-muted-foreground">
        <p className="flex items-center gap-1.5">
          <Calculator className="h-3.5 w-3.5 shrink-0 text-primary" />
          <span className="font-mono font-bold text-primary">
            {metric.formula.function}({metric.formula.expression})
          </span>
        </p>
        <p className="flex items-center gap-1.5">
          <Table2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-0.5 font-semibold text-emerald-700 dark:text-emerald-300">
            <Database className="h-3 w-3" />
            {metric.base_entity}
          </span>
        </p>
        {metric.filters && metric.filters.length > 0 ? (
          <p className="flex flex-wrap items-center gap-1.5">
            <Filter className="h-3.5 w-3.5 shrink-0 text-amber-500" />
            {metric.filters.map((filter, idx) => (
              <span
                key={idx}
                className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 font-mono font-medium text-amber-800 dark:text-amber-300"
              >
                {filter.field} {filter.operator} {String(filter.value)}
              </span>
            ))}
          </p>
        ) : null}
      </div>

      {yaml ? (
        <div>
          <button
            type="button"
            onClick={() => setShowYaml((prev) => !prev)}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-semibold text-muted-foreground transition-all hover:bg-secondary hover:text-foreground"
          >
            <Code2 className="h-3.5 w-3.5 text-primary" />
            <span>{showYaml ? 'Ẩn mã YAML' : 'Xem mã YAML'}</span>
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showYaml ? 'rotate-180' : ''}`} />
          </button>
          {showYaml ? (
            <div className="mt-2">
              <YamlCodeViewer yaml={yaml} title="Metric có sẵn (YAML)" />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
