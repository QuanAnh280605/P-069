'use client';

import React, { useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Database,
  History,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { triggerSyncApi, type SchemaSyncStatus } from '@/lib/api';

interface SchemaDriftBannerProps {
  databaseId: string | number;
  databaseName: string;
  syncStatus: SchemaSyncStatus;
  onOpenSyncModal: () => void;
  onSyncComplete?: () => void;
}

export const SchemaDriftBanner: React.FC<SchemaDriftBannerProps> = ({
  databaseId,
  databaseName,
  syncStatus,
  onOpenSyncModal,
  onSyncComplete,
}) => {
  const [dismissed, setDismissed] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStep, setSyncStep] = useState<number>(0);
  const [syncError, setSyncError] = useState<string | null>(null);

  if (dismissed || syncStatus.in_sync) {
    return null;
  }

  const preview = syncStatus.drift_preview;
  const renamedCount = preview?.renamed_columns?.length || 0;
  const addedTableCount = preview?.added_tables?.length || 0;
  const droppedTableCount = preview?.dropped_tables?.length || 0;

  const handleQuickSync = async () => {
    setIsSyncing(true);
    setSyncError(null);
    setSyncStep(1);

    try {
      const timer1 = setTimeout(() => setSyncStep(2), 400);
      const timer2 = setTimeout(() => setSyncStep(3), 900);
      const timer3 = setTimeout(() => setSyncStep(4), 1400);

      await triggerSyncApi(databaseId);

      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      setSyncStep(5); // Complete

      setTimeout(() => {
        setIsSyncing(false);
        setSyncStep(0);
        onSyncComplete?.();
      }, 800);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Đồng bộ thất bại';
      setSyncError(msg);
      setIsSyncing(false);
      setSyncStep(0);
    }
  };

  const steps = [
    { num: 1, text: 'Quét cấu trúc Database...' },
    { num: 2, text: 'Kiểm tra & đối chiếu cột đổi tên...' },
    { num: 3, text: 'Tự động cập nhật công thức chỉ số...' },
    { num: 4, text: 'Lưu lịch sử thay đổi...' },
  ];

  return (
    <aside
      aria-label="Cảnh báo thay đổi cấu trúc bảng"
      className="relative mb-4 overflow-hidden rounded-xl border border-amber-500/30 bg-gradient-to-r from-amber-950/40 via-amber-900/20 to-zinc-950/60 p-4 shadow-lg backdrop-blur-md transition-all duration-300"
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-400 shadow-inner">
            <ShieldAlert className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-amber-200">
                Phát hiện thay đổi cấu trúc Database ({databaseName})
              </h2>
              <span className="rounded-full border border-amber-500/40 bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300">
                Thay đổi cấu trúc
              </span>
            </div>
            <p className="mt-0.5 text-xs text-zinc-300">
              {preview?.renamed_columns && preview.renamed_columns.length > 0 ? (
                <>
                  Phát hiện đổi tên cột tại bảng{' '}
                  <strong className="text-amber-300 font-mono">
                    {preview.renamed_columns[0].table_name}
                  </strong>
                  :{' '}
                  <span className="line-through text-rose-400 font-mono">
                    {preview.renamed_columns[0].old_name}
                  </span>{' '}
                  <ArrowRight className="inline h-3 w-3 text-zinc-400" />{' '}
                  <strong className="text-emerald-400 font-mono">
                    {preview.renamed_columns[0].new_name}
                  </strong>
                  {preview.renamed_columns.length > 1 &&
                    ` (+${preview.renamed_columns.length - 1} cột khác)`}
                </>
              ) : addedTableCount > 0 || droppedTableCount > 0 ? (
                <>
                  Có thay đổi về bảng ({addedTableCount} bảng mới, {droppedTableCount} bảng đã xóa). Bạn có muốn đồng bộ ngay?
                </>
              ) : (
                'Cấu trúc bảng trong Database vừa có sự thay đổi. Bạn có muốn áp dụng Tự Phục Hồi để cập nhật lại chỉ số không?'
              )}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 self-end md:self-auto">
          <Button
            size="sm"
            variant="outline"
            onClick={onOpenSyncModal}
            className="h-8 border-zinc-700/80 bg-zinc-900/60 text-xs text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800 hover:text-white"
          >
            <History className="mr-1.5 h-3.5 w-3.5 text-zinc-400" />
            Chi tiết
          </Button>

          <Button
            size="sm"
            onClick={handleQuickSync}
            disabled={isSyncing}
            className="h-8 border border-amber-500/50 bg-amber-600 font-medium text-xs text-white shadow hover:bg-amber-500 active:scale-95 transition-all"
          >
            {isSyncing ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                Đang tự vá...
              </>
            ) : (
              <>
                <Sparkles className="mr-1.5 h-3.5 w-3.5 text-amber-200" />
                Cập nhật ngay
              </>
            )}
          </Button>

          <button
            onClick={() => setDismissed(true)}
            aria-label="Để sau"
            title="Để sau"
            className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Syncing Real-time Progress View */}
      {isSyncing && (
        <div className="mt-3 rounded-lg border border-amber-500/20 bg-zinc-950/80 p-3">
          <div className="mb-2 flex items-center justify-between text-[11px] font-medium text-amber-300">
            <span className="flex items-center gap-1.5">
              <RefreshCw className="h-3 w-3 animate-spin text-amber-400" />
              Tiến trình đồng bộ & tự vá:
            </span>
            <span>Bước {Math.min(syncStep, 4)} / 4</span>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
            {steps.map((s) => {
              const isDone = syncStep > s.num || syncStep === 5;
              const isCurrent = syncStep === s.num;
              return (
                <div
                  key={s.num}
                  className={`flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] transition-all ${
                    isDone
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                      : isCurrent
                        ? 'border-amber-500/50 bg-amber-500/20 font-semibold text-amber-200 shadow-sm'
                        : 'border-zinc-800 bg-zinc-900/40 text-zinc-500'
                  }`}
                >
                  {isDone ? (
                    <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-400" />
                  ) : isCurrent ? (
                    <Loader2 className="h-3 w-3 shrink-0 animate-spin text-amber-400" />
                  ) : (
                    <span className="flex h-3 w-3 shrink-0 items-center justify-center rounded-full bg-zinc-800 text-[9px]">
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

      {syncError && (
        <div className="mt-2 rounded border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-300">
          ⚠️ {syncError}
        </div>
      )}
    </aside>
  );
};
