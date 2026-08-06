'use client';

import { useState } from 'react';
import { AlertTriangle, FileText, Loader2, Save, Upload } from 'lucide-react';

import SqlDumpTechnicalPreview from '@/components/SqlDumpTechnicalPreview';
import { useAuth } from '@/context/AuthContext';
import { saveImportedSchema, uploadSqlDumpPreview } from '@/lib/api';
import type { SqlDumpPreview } from '@/lib/api';

const MAX_FILE_BYTES = 20 * 1024 * 1024;
type Dialect = '' | 'postgresql' | 'mysql';

interface Props {
  onSaved?: () => void;
}

export default function SqlDumpPreviewUploader({ onSaved }: Props) {
  const { token } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [dialect, setDialect] = useState<Dialect>('');
  const [preview, setPreview] = useState<SqlDumpPreview | null>(null);
  const [displayName, setDisplayName] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleUpload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !token) return;
    if (file.size > MAX_FILE_BYTES) {
      setError('File exceeds the 20 MiB limit.');
      return;
    }
    setIsUploading(true);
    setError('');
    setPreview(null);
    try {
      setPreview(await uploadSqlDumpPreview(file, dialect, token));
      setDisplayName((current) => current.trim() || file.name.replace(/\.sql$/i, ''));
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Unable to parse SQL dump.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleSave = async () => {
    if (!preview || !displayName.trim() || !token) return;
    setIsSaving(true);
    setError('');
    setMessage('');
    try {
      await saveImportedSchema(displayName.trim(), preview, token);
      setMessage('Đã lưu schema thành công.');
      setPreview(null);
      setFile(null);
      setDisplayName('');
      onSaved?.();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Không thể lưu schema.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section className="glass-card rounded-2xl border border-cyan-500/30 p-6 shadow-xl md:p-8">
      <UploaderHeader />
      <form onSubmit={handleUpload}>
        <DisplayNameField value={displayName} disabled={isUploading || isSaving} onChange={setDisplayName} />
        <div className="grid grid-cols-1 items-end gap-4 md:grid-cols-[1fr_220px_auto]">
          <FilePicker file={file} disabled={isUploading} onChange={(value) => { setFile(value); setPreview(null); }} />
          <DialectPicker value={dialect} disabled={isUploading} onChange={(value) => { setDialect(value); setPreview(null); }} />
          <button type="submit" disabled={!file || !token || isUploading} className="gradient-btn flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50">
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {isUploading ? 'Parsing...' : 'Upload & Preview'}
          </button>
        </div>
      </form>
      {error && <ErrorMessage message={error} />}
      {message && <p className="mt-4 text-xs text-emerald-300">{message}</p>}
      {preview && <SaveSchemaAction disabled={!displayName.trim()} saving={isSaving} onSave={handleSave} />}
      {preview && <SqlDumpTechnicalPreview preview={preview} />}
    </section>
  );
}

function UploaderHeader() {
  return (
    <div className="mb-6 flex items-start gap-3 border-b border-slate-800 pb-4">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/15 text-cyan-300"><Upload className="h-5 w-5" /></div>
      <div>
        <h2 className="text-lg font-bold text-slate-100">Import SQL Dump</h2>
        <p className="mt-1 text-xs text-slate-400">Parse PostgreSQL or MySQL DDL into technical schema metadata. No SQL is executed.</p>
      </div>
    </div>
  );
}

function DisplayNameField({ value, disabled, onChange }: { value: string; disabled: boolean; onChange: (value: string) => void }) {
  return (
    <label className="mb-4 block"><span className="mb-2 block text-xs font-semibold uppercase text-slate-300">Tên gợi nhớ</span><input value={value} disabled={disabled} maxLength={200} onChange={(event) => onChange(event.target.value)} placeholder="Ví dụ: Schema bán hàng tháng 8" className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500 disabled:opacity-60" /></label>
  );
}

function SaveSchemaAction({ disabled, saving, onSave }: { disabled: boolean; saving: boolean; onSave: () => void }) {
  return <div className="mt-5 flex justify-end"><button type="button" onClick={onSave} disabled={disabled || saving} className="gradient-btn flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{saving ? 'Đang lưu...' : 'Lưu schema'}</button></div>;
}

function FilePicker({ file, disabled, onChange }: { file: File | null; disabled: boolean; onChange: (file: File | null) => void }) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase text-slate-300">File .sql</span>
      <span className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5">
        <FileText className="h-4 w-4 shrink-0 text-cyan-300" /><span className="truncate text-xs text-slate-300">{file?.name || 'Choose a schema-only SQL dump'}</span>
        <input type="file" accept=".sql,application/sql,text/plain" className="sr-only" disabled={disabled} onChange={(event) => onChange(event.target.files?.[0] || null)} />
      </span>
    </label>
  );
}

function DialectPicker({ value, disabled, onChange }: { value: Dialect; disabled: boolean; onChange: (value: Dialect) => void }) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase text-slate-300">Dialect override</span>
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value as Dialect)} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-xs text-slate-200">
        <option value="">Auto detect</option><option value="postgresql">PostgreSQL</option><option value="mysql">MySQL</option>
      </select>
    </label>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return <p className="mt-4 flex gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300"><AlertTriangle className="h-4 w-4 shrink-0" />{message}</p>;
}
