'use client';

import React, { useState } from 'react';
import { Table2, Code2, ChevronDown, ChevronUp, ShieldCheck, Database } from 'lucide-react';
import { ChatSemanticQueryResult } from '@/lib/api';
import { SqlCodeViewer } from '@/components/studio/SqlCodeViewer';
import { cn } from '@/lib/utils';

interface ChatQueryResultCardProps {
  result: ChatSemanticQueryResult;
  theme?: 'light' | 'dark';
}

function formatCellValue(val: unknown): string {
  if (val === null || val === undefined || val === '') return '—';
  if (typeof val === 'number') return val.toLocaleString();
  if (typeof val === 'boolean') return val ? 'Có' : 'Không';
  const str = String(val).trim();
  if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
    const parts = str.split('T')[0].split('-');
    if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }
  return str;
}

export const ChatQueryResultCard: React.FC<ChatQueryResultCardProps> = ({
  result,
  theme = 'light',
}) => {
  const [showSql, setShowSql] = useState(false);
  const { columns = [], rows = [], row_count = 0, explanation, sql, spec } = result;
  const limit = spec?.limit ?? 100;

  return (
    <div className="w-full space-y-3 rounded-xl border border-border bg-card/60 p-3.5 shadow-2xs">
      {/* Explanation Header */}
      {explanation && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 px-3.5 py-2.5 text-xs leading-relaxed text-foreground">
          <div className="flex items-center gap-1.5 font-semibold text-primary mb-1">
            <Database className="h-3.5 w-3.5" />
            <span>Giải thích số liệu (Semantic Explanation):</span>
          </div>
          <p className="text-muted-foreground">{explanation}</p>
        </div>
      )}

      {/* Result Table */}
      {rows.length > 0 ? (
        <div className="overflow-hidden rounded-lg border border-border bg-card shadow-2xs">
          <div className="max-h-72 overflow-x-auto overflow-y-auto">
            <table className="w-full border-collapse text-xs">
              <thead className="sticky top-0 z-10">
                <tr className="border-b border-border bg-secondary/80 backdrop-blur-xs">
                  {columns.map((col, idx) => (
                    <th
                      key={col}
                      className={cn(
                        'px-3.5 py-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground',
                        idx === 0 ? 'text-left' : 'text-right',
                      )}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rIdx) => (
                  <tr
                    key={rIdx}
                    className="border-b border-border/60 last:border-0 hover:bg-accent/40 transition-colors"
                  >
                    {columns.map((_, cIdx) => {
                      const val = row[cIdx];
                      const isNum = typeof val === 'number' || (!isNaN(Number(val)) && val !== '' && val !== null);
                      return (
                        <td
                          key={cIdx}
                          className={cn(
                            'px-3.5 py-2 tabular-nums',
                            cIdx === 0 ? 'text-left font-medium text-foreground' : 'text-right',
                            isNum && cIdx > 0 ? 'font-mono text-foreground' : 'text-muted-foreground',
                          )}
                        >
                          {formatCellValue(val)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Table Footer */}
          <div className="flex items-center justify-between border-t border-border bg-secondary/30 px-3.5 py-2 text-[11px] text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Table2 className="h-3.5 w-3.5 text-primary" />
              <span>
                Hiển thị <strong>{rows.length}</strong> {rows.length === 1 ? 'dòng' : 'dòng'} kết quả
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] bg-secondary px-2 py-0.5 rounded border border-border">
                LIMIT {limit} applied
              </span>
              <div className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="h-3.5 w-3.5" />
                <span>Read-only</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
          <Table2 className="mx-auto h-6 w-6 text-muted-foreground/60 mb-2" />
          <p className="font-medium text-foreground">Không có dữ liệu phù hợp</p>
          <p className="mt-1 text-[11px]">Truy vấn đã thực thi thành công nhưng trả về 0 dòng kết quả.</p>
        </div>
      )}

      {/* SQL Disclosure for Data Lead only */}
      {sql && (
        <div className="pt-1">
          <button
            type="button"
            onClick={() => setShowSql(!showSql)}
            className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 font-medium cursor-pointer transition-colors"
          >
            <Code2 className="h-3.5 w-3.5" />
            <span>{showSql ? 'Ẩn SQL đã biên dịch' : 'Xem SQL đã biên dịch'}</span>
            {showSql ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
          {showSql && (
            <div className="mt-2 animate-in fade-in-50 duration-200">
              <SqlCodeViewer sql={sql} title="Compiled SQL (Read-only Guardrails)" theme={theme} />
            </div>
          )}
        </div>
      )}
    </div>
  );
};
