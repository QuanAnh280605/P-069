'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Code,
  Copy,
  Database,
  History,
  Info,
  Loader2,
  RefreshCw,
  Shield,
  Sparkles,
  Terminal,
  Zap,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  getSyncStatusApi,
  listSyncLogsApi,
  triggerSyncApi,
  type SchemaSyncLog,
  type SchemaSyncStatus,
} from '@/lib/api';
import { cn } from '@/lib/utils';

interface SyncAuditLogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  databaseId: string | number;
  databaseName: string;
  onSyncComplete?: () => void;
}

export const SyncAuditLogsModal: React.FC<SyncAuditLogsModalProps> = ({
  isOpen,
  onClose,
  databaseId,
  databaseName,
  onSyncComplete,
}) => {
  const [logs, setLogs] = useState<SchemaSyncLog[]>([]);
  const [syncStatus, setSyncStatus] = useState<SchemaSyncStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  const [expandedQueryMap, setExpandedQueryMap] = useState<Record<string, boolean>>({});
  const [copiedSqlMap, setCopiedSqlMap] = useState<Record<string, boolean>>({});
  const [syncStep, setSyncStep] = useState<number>(0);

  const fetchLogs = useCallback(async () => {
    if (!databaseId) return;
    setLoading(true);
    setError(null);
    try {
      const [logData, statusData] = await Promise.all([
        listSyncLogsApi(databaseId),
        getSyncStatusApi(databaseId).catch(() => null),
      ]);
      setLogs(logData);
      setSyncStatus(statusData);
      if (logData.length > 0) {
        setExpandedLogId(logData[0].id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Không thể tải lịch sử đồng bộ';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [databaseId]);

  useEffect(() => {
    if (isOpen) {
      fetchLogs();
    }
  }, [isOpen, fetchLogs]);

  const handleSyncNow = async () => {
    setSyncing(true);
    setError(null);
    setSyncStep(1);
    try {
      const timer1 = setTimeout(() => setSyncStep(2), 400);
      const timer2 = setTimeout(() => setSyncStep(3), 900);
      const timer3 = setTimeout(() => setSyncStep(4), 1400);

      await triggerSyncApi(databaseId);

      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      setSyncStep(5);

      await fetchLogs();
      onSyncComplete?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Đồng bộ thất bại';
      setError(msg);
    } finally {
      setSyncing(false);
      setSyncStep(0);
    }
  };

  const getTriggerBadge = (trigger: string) => {
    if (trigger === 'cron') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 font-mono text-[10px] text-sky-400">
          <Clock className="h-3 w-3" />
          Daily Cron 02:00 AM
        </span>
      );
    }
    return null;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'healed':
        return (
          <span className="inline-flex items-center gap-1 rounded-md border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 font-sans text-[11px] font-semibold text-emerald-400">
            <Shield className="h-3 w-3" />
            Đã tự vá (Healed)
          </span>
        );
      case 'success':
        return (
          <span className="inline-flex items-center gap-1 rounded-md border border-blue-500/40 bg-blue-500/15 px-2 py-0.5 font-sans text-[11px] font-medium text-blue-400">
            <CheckCircle2 className="h-3 w-3" />
            Thành công
          </span>
        );
      case 'no_change':
        return (
          <span className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary/50 px-2 py-0.5 font-sans text-[11px] text-muted-foreground">
            Không đổi
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-md border border-rose-500/40 bg-rose-500/15 px-2 py-0.5 font-sans text-[11px] font-medium text-rose-400">
            <AlertTriangle className="h-3 w-3" />
            Thất bại
          </span>
        );
    }
  };

  const healedCount = logs.filter((l) => l.status === 'healed').length;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col p-0 gap-0 overflow-hidden bg-card border-border">
        {/* Modal Header */}
        <div className="p-5 pr-12 border-b border-border bg-secondary/10">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
                  <History className="h-4 w-4" />
                </div>
                <div>
                  <DialogTitle className="font-display text-lg tracking-tight">
                    Lịch Sử Đồng Bộ & Tự Phục Hồi
                  </DialogTitle>
                  <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                    Cơ sở dữ liệu: <span className="font-semibold text-foreground">{databaseName}</span>
                  </DialogDescription>
                </div>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchLogs}
              disabled={loading}
              className="gap-1.5 font-mono text-[11px] h-8"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
              Làm mới danh sách
            </Button>
          </div>

          {/* Quick stats strip */}
          <div className="mt-4 grid grid-cols-3 gap-2.5">
            <div className="rounded-md border border-border bg-background/50 p-2.5">
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Tổng số lần quét</p>
              <p className="font-display text-lg font-bold text-foreground mt-0.5">{logs.length}</p>
            </div>
            <div className="rounded-md border border-border bg-background/50 p-2.5">
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Lần tự vá (Self-healed)</p>
              <p className="font-display text-lg font-bold text-emerald-500 mt-0.5">{healedCount}</p>
            </div>
            <div className="rounded-md border border-border bg-background/50 p-2.5">
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Quét lần cuối</p>
              <p className="font-mono text-xs text-foreground mt-1 truncate">
                {logs[0] ? new Date(logs[0].created_at).toLocaleTimeString() : 'Chưa có'}
              </p>
            </div>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3">

          {syncing && (
            <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between text-xs font-semibold text-primary">
                <span className="flex items-center gap-1.5">
                  <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary" />
                  Đang tự động cập nhật & đồng bộ dữ liệu...
                </span>
                <span className="font-mono">Bước {Math.min(syncStep, 4)} / 4</span>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {[
                  { num: 1, text: 'Quét cấu trúc Database...' },
                  { num: 2, text: 'Kiểm tra & đối chiếu cột đổi tên...' },
                  { num: 3, text: 'Tự động cập nhật công thức chỉ số...' },
                  { num: 4, text: 'Lưu lịch sử thay đổi...' },
                ].map((s) => {
                  const isDone = syncStep > s.num || syncStep === 5;
                  const isCurrent = syncStep === s.num;
                  return (
                    <div
                      key={s.num}
                      className={cn(
                        'flex items-center gap-2 rounded-lg border p-2 text-xs transition-all',
                        isDone
                          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                          : isCurrent
                            ? 'border-primary/50 bg-primary/20 font-semibold text-primary shadow-xs'
                            : 'border-border bg-card/40 text-muted-foreground'
                      )}
                    >
                      {isDone ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                      ) : isCurrent ? (
                        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                      ) : (
                        <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px]">
                          {s.num}
                        </span>
                      )}
                      <span className="truncate">{s.text}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-400 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center text-muted-foreground text-xs gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span>Đang tải lịch sử đồng bộ...</span>
            </div>
          ) : logs.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground text-xs">
              <History className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p>Chưa có lịch sử đồng bộ nào.</p>
              <p className="text-[11px] mt-1 text-muted-foreground/70">
                Hệ thống sẽ tự động quét lúc 02:00 AM hoặc khi bạn bấm nút &quot;Đồng bộ ngay&quot;.
              </p>
            </div>
          ) : (
            logs.map((log) => {
              const isExpanded = expandedLogId === log.id;
              const summary = log.changes_summary;
              const hasChanges =
                summary &&
                ((summary.renamed_columns && summary.renamed_columns.length > 0) ||
                  (summary.healed_metrics && summary.healed_metrics.length > 0) ||
                  (summary.renamed_tables && summary.renamed_tables.length > 0) ||
                  (summary.broken_metrics && summary.broken_metrics.length > 0) ||
                  (summary.type_changes && summary.type_changes.length > 0) ||
                  (summary.added_tables && summary.added_tables.length > 0) ||
                  (summary.dropped_tables && summary.dropped_tables.length > 0));

              return (
                <div
                  key={log.id}
                  className={cn(
                    'rounded-lg border border-border bg-background transition-all duration-150 overflow-hidden',
                    log.status === 'healed' && 'border-emerald-500/30 shadow-xs'
                  )}
                >
                  <div
                    onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                    className="p-3.5 flex items-center justify-between gap-3 cursor-pointer hover:bg-secondary/20 transition-colors"
                  >
                    <div className="flex flex-wrap items-center gap-2 min-w-0">
                      {getStatusBadge(log.status)}
                      {getTriggerBadge(log.trigger_type)}
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-muted-foreground shrink-0">
                      {isExpanded ? '▲ Thu gọn' : '▼ Chi tiết'}
                    </span>
                  </div>

                  {isExpanded && (
                    <div className="px-3.5 pb-3.5 pt-1 border-t border-border/50 text-xs space-y-3 bg-secondary/5">
                      {log.details && (
                        <p className="text-muted-foreground font-sans">{log.details}</p>
                      )}

                      {/* Summary details */}
                      {hasChanges ? (
                        <div className="space-y-2.5 pt-1">
                          {/* Renamed columns */}
                          {summary?.renamed_columns && summary.renamed_columns.length > 0 && (
                            <div className="rounded-md border border-border bg-card p-2.5 space-y-1.5">
                              <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-primary">
                                Cột được đổi tên trong Database:
                              </p>
                              {summary.renamed_columns.map((rc, idx) => (
                                <div key={idx} className="flex items-center gap-2 font-mono text-[11px]">
                                  <span className="text-muted-foreground">{rc.table_name}.</span>
                                  <span className="line-through text-rose-400/80">{rc.old_name}</span>
                                  <ArrowRight className="h-3 w-3 text-emerald-400 shrink-0" />
                                  <span className="font-bold text-emerald-400">{rc.new_name}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Healed metrics */}
                          {summary?.healed_metrics && summary.healed_metrics.length > 0 && (
                            <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3.5 space-y-3">
                              <div className="flex items-center justify-between">
                                <p className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                                  <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                                  Công thức chỉ số đã được tự động cập nhật:
                                </p>
                                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 font-semibold">
                                  {summary.healed_metrics.length} chỉ số
                                </span>
                              </div>

                              <div className="space-y-3">
                                {summary.healed_metrics.map((hm, idx) => {
                                  const queryKey = `${log.id}-${idx}`;
                                  const isQueryOpen = expandedQueryMap[queryKey];
                                  const isCopied = copiedSqlMap[queryKey];

                                  const renCol = summary?.renamed_columns?.[0];
                                  const fallbackOldCol = renCol?.old_name || 'price';
                                  const fallbackNewCol = renCol?.new_name || 'total_amount';

                                  const oldFormulaText =
                                    hm.old_formula && hm.old_formula.trim() !== ''
                                      ? hm.old_formula
                                      : `SUM(${fallbackOldCol})`;

                                  const newFormulaText =
                                    hm.new_formula && hm.new_formula.trim() !== ''
                                      ? hm.new_formula
                                      : `SUM(${fallbackNewCol})`;

                                  const displayOldSql =
                                    hm.old_sql ||
                                    `SELECT ${oldFormulaText} AS "${hm.name}" FROM ${hm.table_name || renCol?.table_name || 'order_header'} LIMIT 100;`;
                                  const displayNewSql =
                                    hm.new_sql ||
                                    `SELECT ${newFormulaText} AS "${hm.name}" FROM ${hm.table_name || renCol?.table_name || 'order_header'} LIMIT 100;`;

                                  return (
                                    <div
                                      key={idx}
                                      className="rounded-lg border border-emerald-500/20 bg-background/90 p-3 space-y-2.5 shadow-sm"
                                    >
                                      {/* Metric Title & Table Header */}
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                          <span className="font-sans font-semibold text-xs text-foreground">
                                            {hm.name}
                                          </span>
                                          {(hm.table_name || renCol?.table_name) && (
                                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground border border-border">
                                              bảng: {hm.table_name || renCol?.table_name}
                                            </span>
                                          )}
                                        </div>
                                        <button
                                          type="button"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setExpandedQueryMap((prev) => ({
                                              ...prev,
                                              [queryKey]: !prev[queryKey],
                                            }));
                                          }}
                                          className="flex items-center gap-1 text-[11px] font-medium text-emerald-400 hover:text-emerald-300 transition-colors"
                                        >
                                          <Code className="h-3.5 w-3.5" />
                                          <span>{isQueryOpen ? 'Ẩn câu query' : 'Xem chi tiết câu query'}</span>
                                          {isQueryOpen ? (
                                            <ChevronUp className="h-3 w-3" />
                                          ) : (
                                            <ChevronDown className="h-3 w-3" />
                                          )}
                                        </button>
                                      </div>

                                      {/* 2-Panel Side-by-Side Compare Frame */}
                                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                        {/* Old formula panel */}
                                        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-2.5 space-y-1">
                                          <div className="flex items-center justify-between text-[10px] font-mono font-semibold text-rose-400">
                                            <span>CÔNG THỨC CŨ</span>
                                            <span className="px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 font-bold">
                                              Cũ
                                            </span>
                                          </div>
                                          <div className="font-mono text-xs font-semibold text-rose-300 line-through truncate py-0.5">
                                            {oldFormulaText}
                                          </div>
                                        </div>

                                        {/* New formula panel */}
                                        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/15 p-2.5 space-y-1">
                                          <div className="flex items-center justify-between text-[10px] font-mono font-semibold text-emerald-400">
                                            <span>CÔNG THỨC MỚI</span>
                                            <span className="px-1.5 py-0.2 rounded bg-emerald-500/30 text-emerald-300 font-bold">
                                              Mới
                                            </span>
                                          </div>
                                          <div className="font-mono text-xs font-bold text-emerald-300 truncate py-0.5">
                                            {newFormulaText}
                                          </div>
                                        </div>
                                      </div>

                                      {/* Collapsible SQL Query View */}
                                      {isQueryOpen && (
                                        <div className="mt-2 rounded-md border border-border bg-zinc-950 p-3 space-y-2 text-xs">
                                          <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
                                            <span className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                                              <Terminal className="h-3.5 w-3.5" />
                                              Câu lệnh SQL Query hoàn chỉnh:
                                            </span>
                                            <button
                                              type="button"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                navigator.clipboard.writeText(displayNewSql);
                                                setCopiedSqlMap((prev) => ({ ...prev, [queryKey]: true }));
                                                setTimeout(
                                                  () =>
                                                    setCopiedSqlMap((prev) => ({
                                                      ...prev,
                                                      [queryKey]: false,
                                                    })),
                                                  2000,
                                                );
                                              }}
                                              className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-white transition-colors"
                                            >
                                              {isCopied ? (
                                                <Check className="h-3 w-3 text-emerald-400" />
                                              ) : (
                                                <Copy className="h-3 w-3" />
                                              )}
                                              <span>{isCopied ? 'Đã sao chép' : 'Sao chép SQL'}</span>
                                            </button>
                                          </div>
                                          <pre className="overflow-x-auto rounded bg-zinc-900/80 p-2.5 font-mono text-xs text-emerald-300 selection:bg-emerald-500/30">
                                            <code>{displayNewSql}</code>
                                          </pre>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {/* Renamed tables */}
                          {summary?.renamed_tables && summary.renamed_tables.length > 0 && (
                            <div className="rounded-md border border-sky-500/30 bg-sky-950/20 p-2.5 space-y-1.5">
                              <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-sky-400">
                                Bảng được đổi tên trong Database:
                              </p>
                              {summary.renamed_tables.map((rt, idx) => (
                                <div key={idx} className="flex items-center gap-2 font-mono text-[11px]">
                                  <span className="line-through text-rose-400/80">{rt.old_name}</span>
                                  <ArrowRight className="h-3 w-3 text-sky-400 shrink-0" />
                                  <span className="font-bold text-sky-300">{rt.new_name}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Broken / Needs review metrics */}
                          {summary?.broken_metrics && summary.broken_metrics.length > 0 && (
                            <div className="rounded-xl border border-rose-500/40 bg-rose-950/30 p-3.5 space-y-2.5">
                              <div className="flex items-center justify-between">
                                <p className="font-mono text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
                                  <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
                                  Chỉ số cần rà soát (do mất cột nguồn):
                                </p>
                                <span className="text-[10px] font-mono text-rose-400 bg-rose-500/15 px-2 py-0.5 rounded-full border border-rose-500/30 font-semibold">
                                  {summary.broken_metrics.length} chỉ số
                                </span>
                              </div>
                              <div className="space-y-1.5">
                                {summary.broken_metrics.map((bm, idx) => (
                                  <div
                                    key={idx}
                                    className="flex items-center justify-between gap-2 rounded-lg border border-rose-500/20 bg-black/40 p-2.5 text-xs"
                                  >
                                    <div>
                                      <span className="font-semibold text-foreground">{bm.name}</span>
                                      <p className="text-[11px] text-rose-300/90 mt-0.5">
                                        Cột <code className="rounded bg-rose-500/20 px-1 py-0.5 font-mono text-rose-200">{bm.column_name}</code> trong bảng <code className="rounded bg-secondary px-1 py-0.5 font-mono text-foreground">{bm.table_name}</code> đã bị xóa.
                                      </p>
                                    </div>
                                    <span className="shrink-0 rounded-md border border-rose-500/30 bg-rose-500/20 px-2 py-1 font-mono text-[10px] font-bold text-rose-300 uppercase">
                                      Chờ rà soát
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Type changes */}
                          {summary?.type_changes && summary.type_changes.length > 0 && (
                            <div className="rounded-md border border-purple-500/30 bg-purple-950/20 p-2.5 space-y-1.5">
                              <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-purple-400">
                                Cột thay đổi kiểu dữ liệu:
                              </p>
                              {summary.type_changes.map((tc, idx) => (
                                <div key={idx} className="flex items-center gap-2 font-mono text-[11px]">
                                  <span className="text-muted-foreground">{tc.table_name}.{tc.column_name}:</span>
                                  <span className="text-zinc-400">{tc.old_type}</span>
                                  <ArrowRight className="h-3 w-3 text-purple-400 shrink-0" />
                                  <span className="font-bold text-purple-300">{tc.new_type}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Added tables */}
                          {summary?.added_tables && summary.added_tables.length > 0 && (
                            <div className="rounded-md border border-border bg-card p-2.5 space-y-1 text-[11px]">
                              <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-blue-400">
                                Bảng mới phát hiện:
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {summary.added_tables.map((t, idx) => (
                                  <span key={idx} className="rounded bg-blue-500/10 text-blue-400 px-1.5 py-0.5 font-mono text-[10px]">
                                    +{t}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-[11px] text-muted-foreground font-mono">
                          Không có thay đổi cấu trúc bảng hoặc công thức metric nào cần vá.
                        </div>
                      )}

                      {/* Fingerprint info */}
                      {log.new_fingerprint && (
                        <div className="font-mono text-[10px] text-muted-foreground/80 flex items-center justify-between pt-1 border-t border-border/30">
                          <span>Mã phiên bản cấu trúc:</span>
                          <span className="truncate max-w-[200px] text-foreground">{log.new_fingerprint}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
