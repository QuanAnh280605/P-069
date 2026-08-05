'use client';

import { useEffect, useState } from 'react';
import { Eye, FolderKanban, Loader2, Server, Trash2, X } from 'lucide-react';

import SqlDumpTechnicalPreview from '@/components/SqlDumpTechnicalPreview';
import {
  deleteImportedSchema,
  getImportedSchema,
  listImportedSchemas,
} from '@/lib/api';
import type { ImportedSchemaRecord, ImportedSchemaSummary } from '@/lib/api';

interface Props {
  token: string;
  refreshKey: number;
}

export default function ImportedSchemaList({ token, refreshKey }: Props) {
  const [items, setItems] = useState<ImportedSchemaSummary[]>([]);
  const [selected, setSelected] = useState<ImportedSchemaRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    listImportedSchemas(token)
      .then((data) => active && setItems(data))
      .catch((reason) => active && setError(errorMessage(reason)))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [token, refreshKey]);

  const openRecord = async (id: number) => {
    try { setSelected(await getImportedSchema(id, token)); }
    catch (reason) { setError(errorMessage(reason)); }
  };

  const removeRecord = async (id: number) => {
    try {
      await deleteImportedSchema(id, token);
      setItems((current) => current.filter((item) => item.id !== id));
      setSelected((current) => current?.id === id ? null : current);
    } catch (reason) { setError(errorMessage(reason)); }
  };

  return (
    <section className="glass-card rounded-2xl border border-indigo-500/20 p-6 shadow-xl md:p-8">
      <ListHeader count={items.length} />
      {error && <p className="mb-4 text-xs text-red-300">{error}</p>}
      {loading ? <LoadingState /> : <SchemaTable items={items} onOpen={openRecord} onDelete={removeRecord} />}
      {selected && <SavedSchemaPreview record={selected} onClose={() => setSelected(null)} />}
    </section>
  );
}

function SavedSchemaPreview({ record, onClose }: { record: ImportedSchemaRecord; onClose: () => void }) {
  return (
    <div className="mt-6 border-t border-slate-800 pt-2">
      <div className="flex justify-end"><button onClick={onClose} className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-3.5 w-3.5" /> Close preview</button></div>
      <SqlDumpTechnicalPreview preview={{ dialect: record.dialect, raw_schema: record.raw_schema, diagnostics: [] }} />
    </div>
  );
}

function ListHeader({ count }: { count: number }) {
  return (
    <header className="mb-5 flex items-center justify-between border-b border-slate-800 pb-4">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-purple-500/30 bg-purple-600/20 text-purple-300"><FolderKanban className="h-5 w-5" /></span>
        <div><h3 className="font-bold uppercase text-slate-100">Danh sách schema đã lưu</h3><p className="text-xs text-slate-400">Các technical schema được import từ file SQL</p></div>
      </div>
      <span className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs text-slate-400">{count} schemas</span>
    </header>
  );
}

function SchemaTable({ items, onOpen, onDelete }: { items: ImportedSchemaSummary[]; onOpen: (id: number) => void; onDelete: (id: number) => void }) {
  if (!items.length) return <p className="py-6 text-center text-sm text-slate-500">Chưa có schema nào được lưu.</p>;
  return (
    <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead><tr className="border-b border-slate-800 text-xs uppercase text-slate-400"><th className="px-4 py-3">Tên gợi nhớ</th><th className="px-4 py-3">Dialect</th><th className="px-4 py-3">Số bảng</th><th className="px-4 py-3">Cập nhật</th><th className="px-4 py-3 text-right">Thao tác</th></tr></thead>
      <tbody className="divide-y divide-slate-800/60">{items.map((item) => <SchemaRow key={item.id} item={item} onOpen={onOpen} onDelete={onDelete} />)}</tbody>
    </table></div>
  );
}

function SchemaRow({ item, onOpen, onDelete }: { item: ImportedSchemaSummary; onOpen: (id: number) => void; onDelete: (id: number) => void }) {
  return (
    <tr className="hover:bg-slate-900/40">
      <td className="px-4 py-3.5 font-semibold text-slate-200"><span className="flex items-center gap-2"><Server className="h-4 w-4 text-indigo-400" />{item.display_name}</span></td>
      <td className="px-4 py-3.5"><span className="rounded border border-slate-700 bg-slate-800/80 px-2 py-0.5 font-mono text-xs uppercase text-slate-300">{item.dialect}</span></td>
      <td className="px-4 py-3.5 text-slate-400">{item.table_count}</td><td className="px-4 py-3.5 font-mono text-xs text-slate-400">{formatDate(item.updated_at)}</td>
      <td className="px-4 py-3.5"><span className="flex justify-end gap-2"><button onClick={() => onOpen(item.id)} className="gradient-btn flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-white"><Eye className="h-3.5 w-3.5" /> Mở preview</button><button onClick={() => onDelete(item.id)} className="rounded-lg p-1.5 text-slate-500 hover:bg-red-500/10 hover:text-red-400" title="Xóa schema"><Trash2 className="h-4 w-4" /></button></span></td>
    </tr>
  );
}

function LoadingState() {
  return <p className="flex items-center justify-center gap-2 py-6 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Đang tải...</p>;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString('vi-VN');
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : 'Không thể tải danh sách schema.';
}
