'use client';

import { Check, RotateCcw, X } from 'lucide-react';
import { useMemo, useState } from 'react';

import { MetricRollbackConfirmDialog } from '@/components/metrics/MetricRollbackConfirmDialog';
import { MetricVersionDiff } from '@/components/metrics/MetricVersionDiff';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  approveSingleMetricApi,
  getMetricHistoryApi,
  MetricHistory as MetricHistoryData,
  MetricVersion as MetricVersionData,
  MetricVersionStatus,
  rejectMetricVersionApi,
  rollbackMetricApi,
  SemanticApiError,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { renderMetricYaml } from '@/lib/metrics';

interface MetricHistoryDialogProps {
  history: MetricHistoryData;
  dbId: number;
  canManage: boolean;
  /** Whether the viewer may approve or reject the copy-on-write draft. */
  canApprove?: boolean;
  onClose: () => void;
  onMetricsChanged?: () => Promise<void> | void;
}

const VERSION_STATUS_META: Record<MetricVersionStatus, { label: string; className: string }> = {
  pending_approval: {
    label: 'Chờ duyệt',
    className: 'border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400',
  },
  needs_review: {
    label: 'Cần xem xét',
    className: 'border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400',
  },
  approved: {
    label: 'Đã duyệt',
    className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  },
  superseded: {
    label: 'Đã thay thế',
    className: 'border-border bg-secondary text-muted-foreground',
  },
  rejected: {
    label: 'Bị từ chối',
    className: 'border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400',
  },
};

const OPEN_STATUSES: MetricVersionStatus[] = ['pending_approval', 'needs_review'];

function sortVersionsDesc(versions: MetricVersionData[]): MetricVersionData[] {
  return [...versions].sort((a, b) => b.version - a.version);
}

function resolveRollbackError(error: unknown): string {
  if (error instanceof SemanticApiError && error.message) return error.message;
  return 'Không thể khôi phục phiên bản. Vui lòng thử lại.';
}

export function MetricHistoryDialog({
  history,
  dbId,
  canManage,
  canApprove = false,
  onClose,
  onMetricsChanged,
}: MetricHistoryDialogProps) {
  const initial = useMemo(() => sortVersionsDesc(history.versions), [history]);
  const [versions, setVersions] = useState<MetricVersionData[]>(initial);
  const [liveVersion, setLiveVersion] = useState<number>(
    history.live_version ?? initial[0]?.version ?? 0,
  );
  const [baseVersion, setBaseVersion] = useState<number | null>(initial[1]?.version ?? null);
  const [compareVersion, setCompareVersion] = useState<number | null>(initial[0]?.version ?? null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const sorted = useMemo(() => sortVersionsDesc(versions), [versions]);
  const currentVersion = liveVersion || sorted[0]?.version || 0;
  const draft = sorted.find((item) => OPEN_STATUSES.includes(item.status ?? 'superseded')) ?? null;
  const baseEntry = versions.find((version) => version.version === baseVersion) ?? null;
  const compareEntry = versions.find((version) => version.version === compareVersion) ?? null;
  const equalSelection = baseVersion !== null && baseVersion === compareVersion;
  const rollbackEligible = canManage && baseVersion !== null && baseVersion < currentVersion;

  const handleGuardedClose = (open: boolean) => {
    if (pending && !open) return;
    if (!open) onClose();
  };

  const applyRefreshed = (refreshed: MetricHistoryData) => {
    const nextSorted = sortVersionsDesc(refreshed.versions);
    setVersions(nextSorted);
    setLiveVersion(refreshed.live_version ?? nextSorted[0]?.version ?? 0);
    setBaseVersion(nextSorted[1]?.version ?? null);
    setCompareVersion(nextSorted[0]?.version ?? null);
  };

  const runDecision = async (action: 'approve' | 'reject', reason?: string) => {
    setPending(true);
    setError(null);
    try {
      if (action === 'approve') await approveSingleMetricApi(String(dbId), history.metric_id);
      else await rejectMetricVersionApi(String(dbId), history.metric_id, reason || '');
      applyRefreshed(await getMetricHistoryApi(String(dbId), history.metric_id));
      await onMetricsChanged?.();
      setNotice(
        action === 'approve'
          ? 'Đã phê duyệt bản sửa; định nghĩa mới bắt đầu phục vụ truy vấn.'
          : 'Đã từ chối bản sửa; định nghĩa đang publish giữ nguyên.',
      );
    } catch (err) {
      setError(resolveRollbackError(err));
    } finally {
      setPending(false);
    }
  };

  const handleConfirmRollback = async () => {
    if (!baseVersion) return;
    const targetVersion = baseVersion;
    setPending(true);
    setError(null);
    try {
      await rollbackMetricApi(String(dbId), history.metric_id, targetVersion);
      applyRefreshed(await getMetricHistoryApi(String(dbId), history.metric_id));
      await onMetricsChanged?.();
      setNotice(`Đã khôi phục ${history.metric_name} về phiên bản v${targetVersion}.`);
      setConfirmOpen(false);
    } catch (err) {
      setError(resolveRollbackError(err));
      setConfirmOpen(false);
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open onOpenChange={handleGuardedClose}>
      <DialogContent showCloseButton={!pending} className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-sm font-semibold">
            Lịch sử · {history.metric_name}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-wrap items-end gap-3">
          <VersionSelect
            id="diff-base"
            label="Bản gốc (cũ)"
            versions={sorted}
            value={baseVersion}
            disabled={pending}
            onChange={setBaseVersion}
          />
          <VersionSelect
            id="diff-compare"
            label="So sánh (mới)"
            versions={sorted}
            value={compareVersion}
            disabled={pending}
            onChange={setCompareVersion}
          />
        </div>

        {equalSelection ? (
          <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-600 dark:text-amber-400">
            Hãy chọn hai phiên bản khác nhau để so sánh.
          </p>
        ) : (
          baseEntry &&
          compareEntry && (
            <MetricVersionDiff
              previousDefinition={baseEntry.definition}
              currentDefinition={compareEntry.definition}
            />
          )
        )}

        {draft && (
          <DraftDecisionBar
            draft={draft}
            liveVersion={currentVersion}
            canApprove={canApprove}
            pending={pending}
            onDecide={(action, reason) => void runDecision(action, reason)}
          />
        )}

        {rollbackEligible && (
          <RollbackBar baseVersion={baseVersion} onStart={() => setConfirmOpen(true)} />
        )}

        {notice && (
          <p
            role="status"
            className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-2.5 text-xs text-emerald-600 dark:text-emerald-400"
          >
            {notice}
          </p>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-md border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-600 dark:text-red-400"
          >
            {error}
          </p>
        )}

        <VersionList versions={sorted} liveVersion={currentVersion} />

        {confirmOpen && baseVersion !== null && (
          <MetricRollbackConfirmDialog
            open
            metricName={history.metric_name}
            targetVersion={baseVersion}
            currentVersion={currentVersion}
            pending={pending}
            onConfirm={() => void handleConfirmRollback()}
            onOpenChange={(open) => {
              if (!open) setConfirmOpen(false);
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function DraftDecisionBar({
  draft,
  liveVersion,
  canApprove,
  pending,
  onDecide,
}: {
  draft: MetricVersionData;
  liveVersion: number;
  canApprove: boolean;
  pending: boolean;
  onDecide: (action: 'approve' | 'reject', reason?: string) => void;
}) {
  const [reason, setReason] = useState('');
  const [showReasonError, setShowReasonError] = useState(false);

  const handleRejectClick = () => {
    if (!reason.trim()) {
      setShowReasonError(true);
      return;
    }
    setShowReasonError(false);
    onDecide('reject', reason.trim());
  };

  return (
    <div className="space-y-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2.5">
      <p className="text-xs text-amber-700 dark:text-amber-300">
        Bản sửa <span className="font-mono font-semibold">v{draft.version}</span> đang chờ phê duyệt.
        Định nghĩa <span className="font-mono font-semibold">v{liveVersion}</span> vẫn đang phục vụ
        truy vấn cho tới khi bản sửa được duyệt.
      </p>
      {draft.changed_by_name && (
        <p className="text-[11px] text-amber-700/80 dark:text-amber-300/80">
          Người sửa: {draft.changed_by_name}
        </p>
      )}
      {canApprove ? (
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <input
              aria-label="Lý do từ chối"
              value={reason}
              disabled={pending}
              onChange={(event) => {
                setReason(event.target.value);
                if (event.target.value.trim()) setShowReasonError(false);
              }}
              placeholder="Lý do từ chối (bắt buộc khi từ chối)"
              className={cn(
                'h-8 min-w-48 flex-1 rounded-md border bg-background px-2 text-xs text-foreground',
                showReasonError ? 'border-red-500 ring-1 ring-red-500' : 'border-border',
              )}
            />
            <Button
              type="button"
              size="sm"
              disabled={pending}
              className="gap-1.5 text-xs cursor-pointer"
              onClick={() => onDecide('approve')}
            >
              <Check className="h-3.5 w-3.5" />
              Phê duyệt bản sửa
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={pending}
              className="gap-1.5 text-xs cursor-pointer text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
              onClick={handleRejectClick}
            >
              <X className="h-3.5 w-3.5" />
              Từ chối
            </Button>
          </div>
          {showReasonError && (
            <p className="text-[11px] font-medium text-red-500">
              ⚠️ Vui lòng nhập lý do từ chối trước khi bấm Từ chối.
            </p>
          )}
        </div>
      ) : (
        <p className="text-[11px] text-amber-700/80 dark:text-amber-300/80">
          Bạn không có quyền phê duyệt bản sửa này.
        </p>
      )}
    </div>
  );
}

function RollbackBar({
  baseVersion,
  onStart,
}: {
  baseVersion: number | null;
  onStart: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-secondary/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">
        Đưa metric trở lại định nghĩa của{' '}
        <span className="font-mono font-semibold text-foreground">v{baseVersion}</span> bằng cách ghi
        thêm một phiên bản mới — lịch sử cũ được giữ nguyên.
      </p>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="gap-1.5 text-xs cursor-pointer"
        onClick={onStart}
      >
        <RotateCcw className="h-3.5 w-3.5" />
        Khôi phục phiên bản này
      </Button>
    </div>
  );
}

function VersionSelect({
  id,
  label,
  versions,
  value,
  onChange,
  disabled,
}: {
  id: string;
  label: string;
  versions: MetricVersionData[];
  value: number | null;
  onChange: (version: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[11px] font-medium text-muted-foreground">
        {label}
      </label>
      <select
        id={id}
        value={value ?? ''}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-8 cursor-pointer rounded-md border border-border bg-background px-2 text-xs text-foreground"
      >
        {versions.map((version) => (
          <option key={version.version} value={version.version}>
            v{version.version} · {new Date(version.created_at).toLocaleDateString()}
          </option>
        ))}
      </select>
    </div>
  );
}

function VersionStatusBadge({ status }: { status?: MetricVersionStatus }) {
  const meta = status ? VERSION_STATUS_META[status] : undefined;
  if (!meta) return null;
  return (
    <span className={cn('rounded-full border px-2 py-0.5 font-mono text-[10px]', meta.className)}>
      {meta.label}
    </span>
  );
}

function VersionAudit({ version }: { version: MetricVersionData }) {
  const approvedAt = version.approved_at ? new Date(version.approved_at).toLocaleString() : null;
  return (
    <p className="mb-2 text-[11px] text-muted-foreground">
      Sửa bởi {version.changed_by_name || `#${version.changed_by ?? '—'}`}
      {version.parent_version ? ` · dựa trên v${version.parent_version}` : ''}
      {version.approved_by_name || approvedAt
        ? ` · duyệt bởi ${version.approved_by_name || `#${version.approved_by ?? '—'}`}${approvedAt ? ` lúc ${approvedAt}` : ''
        }`
        : ''}
    </p>
  );
}

function VersionList({ versions, liveVersion }: { versions: MetricVersionData[]; liveVersion: number }) {
  return (
    <div className="space-y-3">
      {versions.map((version) => (
        <div key={version.version} className="rounded-lg border border-border bg-card p-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <p className="font-mono text-xs font-semibold text-foreground">
              Version {version.version} · {new Date(version.created_at).toLocaleString()}
            </p>
            <VersionStatusBadge status={version.status} />
            {version.version === liveVersion && (
              <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-[10px] text-primary">
                Đang publish
              </span>
            )}
          </div>
          <VersionAudit version={version} />
          {version.change_reason && (
            <div className="mb-3 rounded-md border border-border/70 bg-secondary/50 px-3 py-2 text-xs">
              <span className="font-medium text-foreground">Ghi chú / Lý do thay đổi: </span>
              <span className="text-muted-foreground whitespace-pre-wrap">{version.change_reason}</span>
            </div>
          )}
          {version.definition ? (
            <YamlCodeViewer yaml={renderMetricYaml(version.definition)} />
          ) : (
            <p className="text-xs text-amber-500">Phiên bản legacy không có definition.</p>
          )}
        </div>
      ))}
    </div>
  );
}
