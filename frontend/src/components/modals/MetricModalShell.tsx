'use client';

import { GitCommitHorizontal } from 'lucide-react';

import { DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { MetricDefinition } from '@/lib/api';
import { cn } from '@/lib/utils';
import { StatusPill } from '@/components/workspace/shared';

export type TabKey = 'definition' | 'history';

export function MetricModalHeader({
  submissionMode,
  isMemberRequest,
  initialName,
  initialDefinition,
  status,
  metricName,
  baseEntity,
}: {
  submissionMode?: boolean;
  isMemberRequest?: boolean;
  initialName?: string;
  initialDefinition?: MetricDefinition | null;
  status: string;
  metricName: string;
  baseEntity: string;
}) {
  const title = isMemberRequest
    ? 'Duyệt & Chỉnh sửa đề xuất của Member'
    : submissionMode
      ? 'Gửi Business Metric'
      : initialName || initialDefinition?.metric?.name
        ? 'Định nghĩa Business Metric'
        : 'Thêm mới Business Metric';
  return (
    <DialogHeader>
      <div className="flex flex-wrap items-center gap-3">
        <DialogTitle className="font-display text-2xl">{title}</DialogTitle>
        <StatusPill status={status} />
      </div>
      {metricName && (
        <p className="font-mono text-[11px] text-muted-foreground">
          {metricName} · {baseEntity}
        </p>
      )}
    </DialogHeader>
  );
}

function MetricTabControls({
  activeTab,
  setActiveTab,
  versionsLength,
}: {
  activeTab: TabKey;
  setActiveTab: (value: TabKey) => void;
  versionsLength: number;
}) {
  const tabs = [
    { key: 'definition' as TabKey, label: 'Definition' },
    { key: 'history' as TabKey, label: `Version history (${versionsLength})` },
  ];
  return (
    <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1 self-start">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => setActiveTab(tab.key)}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs transition-colors cursor-pointer',
            activeTab === tab.key
              ? 'bg-primary text-primary-foreground font-semibold'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function VersionHistory({ versions }: { versions: { version: number; change_reason?: string; created_at?: string }[] }) {
  if (versions.length === 0) {
    return (
      <p className="text-xs text-muted-foreground italic text-center py-6">Chưa có lịch sử phiên bản.</p>
    );
  }
  return (
    <ol className="relative space-y-4 border-l border-border pl-6">
      {versions.map((v, i) => (
        <li key={v.version} className="relative">
          <span className="absolute -left-[27px] flex h-4 w-4 items-center justify-center rounded-full border border-border bg-background">
            <GitCommitHorizontal className="h-3 w-3 text-muted-foreground" />
          </span>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-foreground">Version {v.version}</span>
            {i === 0 && (
              <span className="rounded-full bg-secondary px-2 py-0.5 font-mono text-[10px] text-secondary-foreground">
                current
              </span>
            )}
          </div>
          {v.change_reason && <p className="mt-0.5 text-sm text-foreground">{v.change_reason}</p>}
          {v.created_at && (
            <p className="font-mono text-[11px] text-muted-foreground">
              {new Date(v.created_at).toLocaleString()}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}

export { MetricTabControls, VersionHistory };
