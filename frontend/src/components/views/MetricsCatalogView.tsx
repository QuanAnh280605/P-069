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
  const filtered = useMemo(
    () => props.metrics.filter((item) => metricName(item).toLowerCase().includes(search.toLowerCase())),
    [props.metrics, search]
  );
  const pending = props.metrics.filter((item) => item.status === 'pending_approval').length;

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
    <div className='space-y-4'>
      <header className='flex flex-col justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 md:flex-row md:items-center dark:border-slate-800 dark:bg-slate-900'>
        <div>
          <h2 className='flex items-center gap-2 text-sm font-bold'>
            <BarChart3 className='h-5 w-5 text-emerald-500' /> Business Metrics Catalog
          </h2>
          <p className='mt-1 text-xs text-slate-500'>
            {props.metrics.length} metric · <strong className='text-amber-600 dark:text-amber-400'>{pending} đang chờ phê duyệt</strong>
          </p>
        </div>
        <div className='flex flex-wrap gap-2'>
          <label className='relative'>
            <Search className='absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400' />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder='Tìm metric...'
              className='form-input pl-8'
            />
          </label>
          <button
            onClick={() => void approveAll()}
            disabled={!pending || approving}
            className='rounded-xl bg-emerald-600 px-3.5 py-2 text-xs font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50'
          >
            <CheckCircle2 className='mr-1 inline h-4 w-4' />
            {approving ? 'Đang duyệt...' : `Duyệt tất cả (${pending})`}
          </button>
          <button
            onClick={props.onOpenStudio}
            className='rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white shadow hover:bg-indigo-700'
          >
            <Sparkles className='mr-1 inline h-4 w-4' />
            Sinh với AI
          </button>
        </div>
      </header>

      {filtered.length ? (
        <div className='grid gap-4 md:grid-cols-2'>
          {filtered.map((metric) => (
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
      ) : (
        <Empty onOpenStudio={props.onOpenStudio} />
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

