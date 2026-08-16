'use client';

import { BarChart3, CheckCircle2, Clock3, Edit2, History, Search, ShieldAlert, Sparkles, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';

import { getMetricHistoryApi, MetricHistory as MetricHistoryData, MetricRecord } from '@/lib/api';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { metricName, renderMetricYaml, statusLabel } from '@/lib/metrics';

interface MetricsCatalogViewProps {
  dbId?: number | null;
  metrics: MetricRecord[];
  onDeleteMetric: (id: number) => Promise<void> | void;
  onEditMetric: (metric: MetricRecord) => void;
  onOpenStudio: () => void;
  onApproveAll: () => Promise<void>;
  onApproveMetric?: (id: number) => Promise<void> | void;
}

export function MetricsCatalogView(props: MetricsCatalogViewProps) {
  const [search, setSearch] = useState('');
  const [approving, setApproving] = useState(false);
  const [history, setHistory] = useState<MetricHistoryData | null>(null);
  const [filterTab, setFilterTab] = useState<'all' | 'pending' | 'approved'>('all');

  const filtered = useMemo(
    () => props.metrics.filter((item) => metricName(item).toLowerCase().includes(search.toLowerCase())),
    [props.metrics, search]
  );

  const pendingMetrics = useMemo(
    () => filtered.filter((item) => item.status === 'pending_approval' || item.status === 'needs_review'),
    [filtered]
  );

  const approvedMetrics = useMemo(
    () => filtered.filter((item) => item.status === 'approved'),
    [filtered]
  );

  const totalPending = props.metrics.filter(
    (item) => item.status === 'pending_approval' || item.status === 'needs_review'
  ).length;
  const totalApproved = props.metrics.filter((item) => item.status === 'approved').length;

  const approveAll = async () => {
    setApproving(true);
    try {
      await props.onApproveAll();
    } finally {
      setApproving(false);
    }
  };

  const showHistory = async (metricId: number) => {
    if (props.dbId) setHistory(await getMetricHistoryApi(String(props.dbId), metricId));
  };

  return (
    <div className='space-y-5'>
      {/* Header Bar */}
      <header className='flex flex-col justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4.5 shadow-xs md:flex-row md:items-center dark:border-slate-800 dark:bg-slate-900'>
        <div>
          <h2 className='flex items-center gap-2 text-base font-bold text-slate-800 dark:text-slate-100'>
            <BarChart3 className='h-5 w-5 text-indigo-500' /> Business Metrics Catalog
          </h2>
          <p className='mt-1 text-xs text-slate-500 flex items-center gap-2'>
            <span>Tổng cộng: <strong>{props.metrics.length}</strong> metric</span>
            <span>·</span>
            <span className='text-emerald-600 dark:text-emerald-400 font-semibold'>
              ✅ {totalApproved} đã duyệt
            </span>
            <span>·</span>
            <span className='text-amber-600 dark:text-amber-400 font-semibold'>
              ⏳ {totalPending} chờ duyệt
            </span>
          </p>
        </div>

        <div className='flex flex-wrap items-center gap-2'>
          <label className='relative'>
            <Search className='absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400' />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder='Tìm kiếm metric...'
              className='form-input pl-8 text-xs'
            />
          </label>

          <button
            type='button'
            onClick={() => void approveAll()}
            disabled={!totalPending || approving}
            className='inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-700 px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:from-emerald-500 hover:to-emerald-600 disabled:opacity-40 transition-all cursor-pointer'
          >
            <CheckCircle2 className='h-4 w-4' />
            {approving ? 'Đang duyệt...' : `Duyệt tất cả (${totalPending})`}
          </button>

          <button
            type='button'
            onClick={props.onOpenStudio}
            className='inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-indigo-500 transition-all cursor-pointer'
          >
            <Sparkles className='h-4 w-4' />
            Sinh với AI
          </button>
        </div>
      </header>

      {/* Filter Tabs */}
      <div className='flex items-center gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800 w-fit'>
        <button
          type='button'
          onClick={() => setFilterTab('all')}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
            filterTab === 'all'
              ? 'bg-white text-slate-900 shadow-xs dark:bg-slate-900 dark:text-white'
              : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
          }`}
        >
          Tất cả ({filtered.length})
        </button>
        <button
          type='button'
          onClick={() => setFilterTab('pending')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
            filterTab === 'pending'
              ? 'bg-white text-amber-700 shadow-xs dark:bg-slate-900 dark:text-amber-400'
              : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
          }`}
        >
          <Clock3 className='h-3.5 w-3.5 text-amber-500' />
          Chờ phê duyệt ({pendingMetrics.length})
        </button>
        <button
          type='button'
          onClick={() => setFilterTab('approved')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
            filterTab === 'approved'
              ? 'bg-white text-emerald-700 shadow-xs dark:bg-slate-900 dark:text-emerald-400'
              : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
          }`}
        >
          <CheckCircle2 className='h-3.5 w-3.5 text-emerald-500' />
          Đã phê duyệt ({approvedMetrics.length})
        </button>
      </div>

      {!filtered.length ? (
        <Empty onOpenStudio={props.onOpenStudio} />
      ) : (
        <div className='space-y-6'>
          {/* PHẦN 1: METRICS ĐANG CHỜ PHÊ DUYỆT */}
          {(filterTab === 'all' || filterTab === 'pending') && (
            <section className='space-y-3'>
              <div className='flex items-center justify-between border-b border-amber-200/80 pb-2 dark:border-amber-900/50'>
                <div className='flex items-center gap-2'>
                  <div className='flex h-7 w-7 items-center justify-center rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'>
                    <Clock3 className='h-4 w-4' />
                  </div>
                  <div>
                    <h3 className='text-sm font-bold text-slate-800 dark:text-slate-100'>
                      1. Metrics Đang Chờ Phê Duyệt
                    </h3>
                    <p className='text-[11px] text-slate-500'>
                      Các chỉ số do AI đề xuất hoặc vừa chỉnh sửa, cần HITL review và phê duyệt
                    </p>
                  </div>
                </div>
                <span className='rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-800 dark:bg-amber-950 dark:text-amber-300'>
                  {pendingMetrics.length} chỉ số
                </span>
              </div>

              {pendingMetrics.length === 0 ? (
                <div className='rounded-xl border border-dashed border-slate-200 p-6 text-center text-xs text-slate-400 dark:border-slate-800'>
                  ✨ Không có metric nào đang chờ duyệt.
                </div>
              ) : (
                <div className='grid gap-4 md:grid-cols-2'>
                  {pendingMetrics.map((metric) => (
                    <MetricCard
                      key={metric.metric_id}
                      metric={metric}
                      onEdit={props.onEditMetric}
                      onDelete={props.onDeleteMetric}
                      onHistory={showHistory}
                      onApprove={props.onApproveMetric}
                    />
                  ))}
                </div>
              )}
            </section>
          )}

          {/* PHẦN 2: METRICS ĐÃ PHÊ DUYỆT */}
          {(filterTab === 'all' || filterTab === 'approved') && (
            <section className='space-y-3'>
              <div className='flex items-center justify-between border-b border-emerald-200/80 pb-2 dark:border-emerald-900/50'>
                <div className='flex items-center gap-2'>
                  <div className='flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'>
                    <CheckCircle2 className='h-4 w-4' />
                  </div>
                  <div>
                    <h3 className='text-sm font-bold text-slate-800 dark:text-slate-100'>
                      2. Metrics Đã Phê Duyệt (Official Metrics)
                    </h3>
                    <p className='text-[11px] text-slate-500'>
                      Các chỉ số chuẩn hóa đã sẵn sàng để truy vấn trong Metric Explorer và Export
                    </p>
                  </div>
                </div>
                <span className='rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'>
                  {approvedMetrics.length} chỉ số
                </span>
              </div>

              {approvedMetrics.length === 0 ? (
                <div className='rounded-xl border border-dashed border-slate-200 p-6 text-center text-xs text-slate-400 dark:border-slate-800'>
                  Chưa có metric nào được phê duyệt. Hãy duyệt các metric ở phần trên.
                </div>
              ) : (
                <div className='grid gap-4 md:grid-cols-2'>
                  {approvedMetrics.map((metric) => (
                    <MetricCard
                      key={metric.metric_id}
                      metric={metric}
                      onEdit={props.onEditMetric}
                      onDelete={props.onDeleteMetric}
                      onHistory={showHistory}
                      onApprove={props.onApproveMetric}
                    />
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      )}

      {history && <HistoryDialog history={history} onClose={() => setHistory(null)} />}
    </div>
  );
}

function MetricCard({
  metric,
  onEdit,
  onDelete,
  onHistory,
  onApprove,
}: {
  metric: MetricRecord;
  onEdit: (item: MetricRecord) => void;
  onDelete: (id: number) => Promise<void> | void;
  onHistory: (id: number) => Promise<void>;
  onApprove?: (id: number) => Promise<void> | void;
}) {
  const definition = metric.definition;
  const isPending = metric.status === 'pending_approval';

  return (
    <article className='flex flex-col justify-between space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900'>
      <div className='space-y-2'>
        <div className='flex justify-between items-start gap-2'>
          <div>
            <h3 className='font-bold text-sm text-slate-800 dark:text-slate-100'>{metricName(metric)}</h3>
            <p className='mt-0.5 text-[11px] text-slate-500'>
              v{metric.version} · Nguồn: <span className='capitalize font-medium'>{metric.source}</span>
            </p>
          </div>
          <StatusBadge status={metric.status} />
        </div>

        {definition ? (
          <>
            <p className='font-mono text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/40 p-2 rounded-lg'>
              {definition.metric.formula.function}({definition.metric.formula.expression}) · Bảng: {definition.metric.base_entity}
            </p>
            {definition.metric.excluded_notes && (
              <p className='text-xs text-slate-500'>Lưu ý: {definition.metric.excluded_notes}</p>
            )}
            <details className='text-xs'>
              <summary className='cursor-pointer font-semibold text-slate-500 hover:text-indigo-600'>
                Xem YAML definition
              </summary>
              <div className='mt-2'>
                <YamlCodeViewer yaml={renderMetricYaml(definition)} />
              </div>
            </details>
          </>
        ) : (
          <div className='rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300'>
            <ShieldAlert className='mr-1 inline h-4 w-4' />
            Metric legacy chưa có canonical definition. Hãy chuẩn hóa trước khi duyệt hoặc query.
          </div>
        )}
      </div>

      <div className='flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 dark:border-slate-800'>
        <div className='flex gap-1.5'>
          <button
            onClick={() => void onHistory(metric.metric_id)}
            title='Xem lịch sử phiên bản'
            className='rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300'
          >
            <History className='h-3.5 w-3.5' />
          </button>
          <button
            onClick={() => onEdit(metric)}
            className='rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300'
          >
            <Edit2 className='mr-1 inline h-3.5 w-3.5' />
            {definition ? 'Chỉnh sửa' : 'Chuẩn hóa'}
          </button>
          <button
            onClick={() => {
              if (window.confirm(`Xóa metric ${metricName(metric)}?`)) void onDelete(metric.metric_id);
            }}
            className='rounded-lg border border-red-200 p-2 text-red-500 hover:bg-red-50 dark:border-red-900/50'
            title='Xóa metric'
          >
            <Trash2 className='h-3.5 w-3.5' />
          </button>
        </div>

        {isPending && onApprove && (
          <button
            type='button'
            onClick={() => void onApprove(metric.metric_id)}
            className='flex items-center gap-1 rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white shadow transition-all hover:bg-emerald-700 active:scale-95'
            title='Phê duyệt chỉ số này'
          >
            <CheckCircle2 className='h-3.5 w-3.5' />
            Duyệt chỉ số này
          </button>
        )}
      </div>
    </article>
  );
}

function StatusBadge({ status }: { status: MetricRecord['status'] }) {
  const color =
    status === 'approved'
      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
      : status === 'needs_review'
      ? 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300'
      : 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300';
  return (
    <span className={`h-fit rounded-full px-2.5 py-1 text-[10px] font-bold ${color}`}>
      <Clock3 className='mr-1 inline h-3 w-3' />
      {statusLabel(status)}
    </span>
  );
}

function Empty({ onOpenStudio }: { onOpenStudio: () => void }) {
  return (
    <div className='rounded-2xl border border-dashed border-slate-300 p-12 text-center'>
      <p className='text-sm font-bold'>Chưa có Metric Definition</p>
      <button onClick={onOpenStudio} className='mt-3 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white'>
        Mở AI Studio
      </button>
    </div>
  );
}

function HistoryDialog({ history, onClose }: { history: MetricHistoryData; onClose: () => void }) {
  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4'>
      <div className='max-h-[80vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-5 dark:bg-slate-900'>
        <div className='flex justify-between'>
          <h3 className='font-bold'>Lịch sử · {history.metric_name}</h3>
          <button onClick={onClose} className='text-xs text-slate-400 hover:text-slate-600'>
            Đóng
          </button>
        </div>
        <div className='mt-4 space-y-3'>
          {history.versions.map((version) => (
            <div key={version.version} className='rounded-xl border p-3 dark:border-slate-800'>
              <p className='mb-2 text-xs font-bold'>
                Version {version.version} · {new Date(version.created_at).toLocaleString()}
              </p>
              {version.definition ? (
                <YamlCodeViewer yaml={renderMetricYaml(version.definition)} />
              ) : (
                <p className='text-xs text-amber-600'>Phiên bản legacy không có definition.</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

