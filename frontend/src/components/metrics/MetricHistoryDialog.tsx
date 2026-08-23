'use client';

import { RotateCcw } from 'lucide-react';
import { useMemo, useState } from 'react';

import { MetricRollbackConfirmDialog } from '@/components/metrics/MetricRollbackConfirmDialog';
import { MetricVersionDiff } from '@/components/metrics/MetricVersionDiff';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  getMetricHistoryApi,
  MetricHistory as MetricHistoryData,
  MetricVersion as MetricVersionData,
  rollbackMetricApi,
  SemanticApiError,
} from '@/lib/api';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { renderMetricYaml } from '@/lib/metrics';

interface MetricHistoryDialogProps {
  history: MetricHistoryData;
  dbId: number;
  canManage: boolean;
  onClose: () => void;
  onMetricsChanged?: () => Promise<void> | void;
}

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
  onClose,
  onMetricsChanged,
}: MetricHistoryDialogProps) {
  const initial = useMemo(() => sortVersionsDesc(history.versions), [history]);
  const [versions, setVersions] = useState<MetricVersionData[]>(initial);
  const [baseVersion, setBaseVersion] = useState<number | null>(initial[1]?.version ?? null);
  const [compareVersion, setCompareVersion] = useState<number | null>(initial[0]?.version ?? null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const sorted = useMemo(() => sortVersionsDesc(versions), [versions]);
  const currentVersion = sorted[0]?.version ?? 0;
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
    setBaseVersion(nextSorted[1]?.version ?? null);
    setCompareVersion(nextSorted[0]?.version ?? null);
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

        <VersionList versions={sorted} />

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
        Đưa metric trở lại{' '}
        <span className="font-mono font-semibold text-foreground">v{baseVersion}</span> và xóa mọi
        phiên bản mới hơn.
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

function VersionList({ versions }: { versions: MetricVersionData[] }) {
  return (
    <div className="space-y-3">
      {versions.map((version) => (
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
  );
}
