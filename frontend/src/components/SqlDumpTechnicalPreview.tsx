'use client';

import { AlertTriangle, KeyRound } from 'lucide-react';

import type { SqlDumpPreview, SqlDumpTable } from '@/lib/api';

interface Props {
  preview: SqlDumpPreview;
}

export default function SqlDumpTechnicalPreview({ preview }: Props) {
  const visibleDiagnostics = preview.diagnostics.filter(
    (item) => item.code !== 'UNSUPPORTED_STATEMENT',
  );

  return (
    <section className="mt-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-100">Technical schema preview</h3>
        <span className="text-xs font-bold uppercase text-cyan-300">{preview.dialect}</span>
      </div>
      {visibleDiagnostics.map((item, index) => (
        <div key={`${item.code}-${index}`} className="flex gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span><strong>{item.code}:</strong> {item.message}</span>
        </div>
      ))}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {preview.raw_schema.tables.map((table) => <TableCard key={tableKey(table)} table={table} />)}
      </div>
    </section>
  );
}

function tableKey(table: SqlDumpTable): string {
  return `${table.schema_name.normalized_name}.${table.table_name.normalized_name}`;
}

function TableCard({ table }: { table: SqlDumpTable }) {
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-700 bg-slate-900/70">
      <header className="border-b border-slate-700 px-5 py-4">
        <h4 className="font-mono font-bold text-slate-100">{table.schema_name.raw_name}.{table.table_name.raw_name}</h4>
        <p className="mt-1 text-xs text-slate-500">{table.columns.length} columns - {table.foreign_keys.length} foreign keys</p>
      </header>
      <div className="divide-y divide-slate-800">
        {table.columns.map((column) => (
          <div key={column.column_name.normalized_name} className="flex items-center justify-between gap-4 px-5 py-3 text-xs">
            <span className="flex items-center gap-2 font-mono text-slate-200">
              {column.primary_key && <KeyRound className="h-4 w-4 text-yellow-300" />}
              {column.column_name.raw_name}
            </span>
            <span className="font-mono text-cyan-300">{column.data_type} {column.nullable ? 'NULL' : 'NOT NULL'}</span>
          </div>
        ))}
      </div>
    </article>
  );
}
