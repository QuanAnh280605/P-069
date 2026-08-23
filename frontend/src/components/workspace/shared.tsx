import type { MetricStatus } from '@/lib/api';
import { Database, HardDrive, Server } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ViewId = 'ai-studio' | 'catalog' | 'explorer' | 'export';

export type DbEngine = 'postgresql' | 'mysql' | 'sqlite' | 'sqlserver' | 'dump';

export interface WorkspaceDatabase {
  id: string;
  name: string;
  engine: DbEngine;
  status: 'connected' | 'idle' | 'error';
  tables: number;
}

export const engineLabels: Record<DbEngine, string> = {
  postgresql: 'PostgreSQL',
  mysql: 'MySQL',
  sqlite: 'SQLite',
  sqlserver: 'SQL Server',
  dump: 'SQL Dump',
};

export function EngineIcon({ engine, className }: { engine: DbEngine; className?: string }) {
  if (engine === 'dump') return <HardDrive className={className} />;
  if (engine === 'sqlserver') return <Server className={className} />;
  return <Database className={className} />;
}

export const statusMeta: Record<string, { label: string; dot: string }> = {
  pending_approval: { label: 'Chờ duyệt', dot: 'bg-amber-500' },
  pending: { label: 'Chờ duyệt', dot: 'bg-amber-500' },
  approved: { label: 'Đã duyệt', dot: 'bg-emerald-500' },
  needs_review: { label: 'Cần xem xét', dot: 'bg-blue-500' },
  unverified: { label: 'Chưa được xác minh', dot: 'bg-amber-500' },
  review: { label: 'Cần xem xét', dot: 'bg-blue-500' },
  draft: { label: 'Bản nháp', dot: 'bg-muted-foreground/50' },
};

export function StatusPill({ status }: { status: MetricStatus | string }) {
  const meta = statusMeta[status] || { label: status, dot: 'bg-amber-500' };
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-border bg-secondary px-2.5 py-0.5 font-mono text-[11px] text-secondary-foreground">
      <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', meta.dot)} />
      {meta.label}
    </span>
  );
}

export function SectionLabel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground',
        className,
      )}
    >
      {children}
    </span>
  );
}
