'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, FileText, Loader2, Upload } from 'lucide-react';

import { useAuth } from '@/context/AuthContext';
import { uploadSqlDumpPreview } from '@/lib/api';

const MAX_FILE_BYTES = 20 * 1024 * 1024;

export default function SqlDumpPreviewUploader() {
  const router = useRouter();
  const { token } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [dialect, setDialect] = useState<'' | 'postgresql' | 'mysql'>('');
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !token) return;
    if (file.size > MAX_FILE_BYTES) {
      setError('File vượt quá giới hạn preview 20 MiB.');
      return;
    }
    setIsUploading(true);
    setError('');
    try {
      const draft = await uploadSqlDumpPreview(file, dialect, token);
      router.push(`/semantic/drafts/${draft.draft_id}/review`);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Không thể tải lên SQL dump.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section className="glass-card rounded-2xl p-6 md:p-8 border border-cyan-500/30 shadow-xl">
      <div className="flex items-start gap-3 pb-4 mb-6 border-b border-slate-800">
        <div className="w-10 h-10 rounded-xl bg-cyan-500/15 text-cyan-300 flex items-center justify-center">
          <Upload className="w-5 h-5" />
        </div>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-bold text-slate-100">Import SQL Dump</h2>
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
              Experimental preview
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Tải lên bản dump chỉ chứa schema, không có dữ liệu. Bản nháp chỉ nằm trong RAM và sẽ mất khi backend khởi động lại.
          </p>
        </div>
      </div>

      <form onSubmit={handleUpload} className="grid grid-cols-1 md:grid-cols-[1fr_220px_auto] gap-4 items-end">
        <label className="block">
          <span className="block text-xs font-semibold text-slate-300 uppercase mb-2">File .sql</span>
          <span className="flex items-center gap-3 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 cursor-pointer">
            <FileText className="w-4 h-4 text-cyan-300 shrink-0" />
            <span className="text-xs text-slate-300 truncate">{file?.name || 'Chọn PostgreSQL/MySQL dump'}</span>
            <input
              type="file"
              accept=".sql,application/sql,text/plain"
              className="sr-only"
              disabled={isUploading}
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
          </span>
        </label>

        <label className="block">
          <span className="block text-xs font-semibold text-slate-300 uppercase mb-2">Dialect override</span>
          <select
            value={dialect}
            disabled={isUploading}
            onChange={(event) => setDialect(event.target.value as typeof dialect)}
            className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-200"
          >
            <option value="">Tự nhận diện</option>
            <option value="postgresql">PostgreSQL</option>
            <option value="mysql">MySQL</option>
          </select>
        </label>

        <button
          type="submit"
          disabled={!file || !token || isUploading}
          className="gradient-btn px-5 py-2.5 rounded-xl text-sm font-bold text-white disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          {isUploading ? 'Đang parse...' : 'Upload & Preview'}
        </button>
      </form>

      {error && (
        <p className="mt-4 text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-xl p-3 flex gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
        </p>
      )}
    </section>
  );
}
