'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertTriangle, ArrowLeft, CheckCircle2, Clock, Database, KeyRound, Loader2 } from 'lucide-react';

import { useAuth } from '@/context/AuthContext';
import { approveSqlDumpPreview, getSqlDumpPreview, SqlDumpPreview } from '@/lib/api';

export default function SqlDumpPreviewReviewPage() {
  const params = useParams<{ draft_id: string }>();
  const { token } = useAuth();
  const [draft, setDraft] = useState<SqlDumpPreview | null>(null);
  const [error, setError] = useState('');
  const [isApproving, setIsApproving] = useState(false);

  useEffect(() => {
    if (!token || !params.draft_id) return;
    getSqlDumpPreview(params.draft_id, token)
      .then(setDraft)
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : 'Không thể tải bản nháp.'));
  }, [params.draft_id, token]);

  const handleApprove = async () => {
    if (!token || !draft) return;
    setIsApproving(true);
    setError('');
    try {
      setDraft(await approveSqlDumpPreview(draft.draft_id, token));
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : 'Không thể phê duyệt preview.');
    } finally {
      setIsApproving(false);
    }
  };

  if (error && !draft) return <PreviewError message={error} />;
  if (!draft) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center text-slate-300 gap-3">
        <Loader2 className="w-5 h-5 animate-spin text-cyan-300" /> Đang tải SQL dump preview...
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in">
      <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-cyan-300">
        <ArrowLeft className="w-4 h-4" /> Quay lại dashboard
      </Link>

      <header className="glass-card rounded-2xl p-6 border border-cyan-500/30">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Database className="w-5 h-5 text-cyan-300" />
              <span className="text-xs font-bold uppercase text-cyan-300">{draft.dialect} SQL dump</span>
              <span className="text-[10px] uppercase px-2 py-1 rounded-full bg-amber-500/15 text-amber-300">
                RAM only
              </span>
            </div>
            <h1 className="text-2xl font-extrabold text-white">Review technical schema preview</h1>
            <p className="text-xs text-slate-400 mt-2 flex items-center gap-2">
              <Clock className="w-3.5 h-3.5" /> Hết hạn: {new Date(draft.expires_at).toLocaleString('vi-VN')}
            </p>
          </div>
          <button
            onClick={handleApprove}
            disabled={isApproving || draft.status === 'approved_preview'}
            className="gradient-btn px-5 py-3 rounded-xl text-sm font-bold text-white disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {isApproving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            {draft.status === 'approved_preview' ? 'Đã phê duyệt preview' : 'Phê duyệt preview'}
          </button>
        </div>
        <p className="mt-4 text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-xl p-3">
          Preview không gọi Save Node và không tạo bản ghi semantic database/table/column.
        </p>
      </header>

      {error && (
        <p className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-xl p-3">{error}</p>
      )}

      {draft.diagnostics.length > 0 && (
        <section className="space-y-2">
          {draft.diagnostics.map((diagnostic, index) => (
            <div key={`${diagnostic.code}-${index}`} className="flex gap-2 text-xs p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-200">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>
                <strong>{diagnostic.code}</strong>: {diagnostic.message}
                {diagnostic.line && ` (dòng ${diagnostic.line}${diagnostic.column ? `, cột ${diagnostic.column}` : ''})`}
              </span>
            </div>
          ))}
        </section>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {draft.raw_schema.tables.map((table) => (
          <article key={`${table.schema_name.normalized_name}.${table.table_name.normalized_name}`} className="glass-card rounded-2xl border border-slate-800 overflow-hidden">
            <div className="px-5 py-4 bg-slate-900/70 border-b border-slate-800">
              <h2 className="font-mono font-bold text-slate-100">
                {table.schema_name.raw_name}.{table.table_name.raw_name}
              </h2>
              <p className="text-[11px] text-slate-500 mt-1">{table.columns.length} columns • {table.foreign_keys.length} foreign keys</p>
            </div>
            <div className="divide-y divide-slate-800/70">
              {table.columns.map((column) => (
                <div key={column.column_name.normalized_name} className="px-5 py-3 flex items-center justify-between gap-3 text-xs">
                  <span className="font-mono text-slate-200 flex items-center gap-2">
                    {column.primary_key && <KeyRound className="w-3.5 h-3.5 text-amber-300" />}
                    {column.column_name.raw_name}
                  </span>
                  <span className="font-mono text-cyan-300 text-right">
                    {column.raw_data_type}{column.nullable ? ' NULL' : ' NOT NULL'}
                  </span>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function PreviewError({ message }: { message: string }) {
  return (
    <div className="max-w-xl mx-auto mt-20 glass-card rounded-2xl p-6 border border-red-500/30 text-center">
      <AlertTriangle className="w-8 h-8 text-red-300 mx-auto mb-3" />
      <h1 className="font-bold text-white">Không thể mở preview</h1>
      <p className="text-sm text-slate-400 mt-2">{message}</p>
      <Link href="/" className="inline-block mt-5 text-cyan-300 text-sm">Quay lại dashboard</Link>
    </div>
  );
}
