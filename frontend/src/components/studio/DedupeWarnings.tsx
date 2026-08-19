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
  onKeepName: () => void;
}

export function ConflictWarningStrip({ conflict, onRename, onUseExisting, onKeepName }: ConflictWarningStripProps) {
  const suggestedName = conflict.suggested_name?.trim() || '';
  return (
    <div className="space-y-2 rounded-xl border border-amber-300/80 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
        <div className="space-y-0.5">
          <p className="font-bold leading-relaxed">
            {conflict.clarify_question || 'Tên metric bị trùng với metric đã có'}
          </p>
          <p className="text-[11px] text-amber-800 dark:text-amber-300">
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
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-bold text-white shadow-xs transition-all hover:bg-amber-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Đổi tên
        </button>
        <button
          type="button"
          onClick={onUseExisting}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-900 shadow-2xs transition-all hover:bg-amber-100 dark:border-amber-900/60 dark:bg-amber-900/40 dark:text-amber-200 dark:hover:bg-amber-900/70"
        >
          Dùng metric có sẵn
        </button>
        <button
          type="button"
          onClick={onKeepName}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-amber-800 underline-offset-2 transition-all hover:underline dark:text-amber-300"
        >
          Giữ nguyên tên
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
      <div className="relative rounded-xl border border-emerald-200 bg-emerald-50/80 p-3.5 pr-10 text-xs text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300">
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
    <div className="relative rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 pr-10 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-300">
      <DismissNoticeButton onDismiss={onDismiss} />
      <div className="flex items-start gap-2">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-400 dark:text-slate-500" />
        <div className="space-y-0.5">
          <p className="font-medium leading-relaxed">{notice.user_message}</p>
          {notice.similarity_reason ? (
            <p className="text-[11px] text-slate-500 dark:text-slate-400">{notice.similarity_reason}</p>
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
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-slate-600 transition-all hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <Eye className="h-3.5 w-3.5 text-indigo-500" />
            <span>{showExisting ? 'Ẩn metric có sẵn' : 'Xem metric có sẵn'}</span>
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showExisting ? 'rotate-180' : ''}`} />
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => onUseExisting?.()}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-2xs transition-all hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
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
      className="absolute right-2.5 top-2.5 inline-flex h-6 w-6 cursor-pointer items-center justify-center rounded-lg text-slate-400 transition-all hover:bg-slate-200/70 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
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
    <div className="mt-2.5 ml-6 space-y-2.5 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900/70">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Metric có sẵn trong hệ thống
        </p>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {statusLabel(status ?? metric.status)}
        </span>
      </div>
      <p className="text-sm font-bold text-slate-900 dark:text-slate-100">{metric.name}</p>

      <div className="space-y-1.5 text-[11px] text-slate-600 dark:text-slate-300">
        <p className="flex items-center gap-1.5">
          <Calculator className="h-3.5 w-3.5 shrink-0 text-indigo-500" />
          <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
            {metric.formula.function}({metric.formula.expression})
          </span>
        </p>
        <p className="flex items-center gap-1.5">
          <Table2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
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
                className="rounded-md border border-amber-200 bg-amber-50/80 px-2 py-0.5 font-mono font-medium text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/60 dark:text-amber-300"
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
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-semibold text-slate-600 transition-all hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <Code2 className="h-3.5 w-3.5 text-indigo-500" />
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
