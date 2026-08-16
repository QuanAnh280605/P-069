'use client';

import React, { useState } from 'react';
import { Copy, Check, Code2 } from 'lucide-react';

interface SqlCodeViewerProps {
  sql: string;
  title?: string;
  theme?: 'light' | 'dark';
}

function formatSql(rawSql: string): string[] {
  if (!rawSql) return [];
  const trimmed = rawSql.trim();
  if (trimmed.includes('\n')) {
    return trimmed.split('\n');
  }
  const formatted = trimmed
    .replace(/\s+(FROM)\s+/gi, '\nFROM ')
    .replace(/\s+(WHERE)\s+/gi, '\nWHERE\n  ')
    .replace(/\s+(GROUP BY)\s+/gi, '\nGROUP BY\n  ')
    .replace(/\s+(ORDER BY)\s+/gi, '\nORDER BY\n  ')
    .replace(/\s+(HAVING)\s+/gi, '\nHAVING\n  ')
    .replace(/\s+(LIMIT)\s+/gi, '\nLIMIT ')
    .replace(/\s+((?:LEFT\s+|RIGHT\s+|INNER\s+|OUTER\s+|CROSS\s+)?JOIN)\s+/gi, '\n$1 ');
  return formatted.split('\n');
}

export const SqlCodeViewer: React.FC<SqlCodeViewerProps> = ({
  sql,
  title = 'SQL Template (Read-only)',
  theme = 'light',
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const lines = formatSql(sql);

  // Syntax highlight for SQL keywords
  const highlightSyntax = (line: string) => {
    const keywords = [
      'SELECT',
      'FROM',
      'WHERE',
      'GROUP BY',
      'ORDER BY',
      'HAVING',
      'LIMIT',
      'JOIN',
      'LEFT JOIN',
      'RIGHT JOIN',
      'INNER JOIN',
      'OUTER JOIN',
      'ON',
      'AND',
      'OR',
      'NOT',
      'IN',
      'AS',
      'SUM',
      'COUNT',
      'AVG',
      'MIN',
      'MAX',
      'DISTINCT',
      'CASE',
      'WHEN',
      'THEN',
      'ELSE',
      'END',
      'OVER',
      'PARTITION BY',
      'COALESCE',
      'CAST',
      'EXTRACT',
      'DATE_TRUNC',
      'BETWEEN',
      'LIKE',
      'IS NULL',
      'IS NOT NULL',
    ];

    const pattern = new RegExp(`\\b(${keywords.join('|')})\\b`, 'gi');
    const parts = line.split(/('(?:[^'\\]|\\.)*')/g);

    return parts.map((part, pIdx) => {
      if (part.startsWith("'") && part.endsWith("'")) {
        return (
          <span
            key={pIdx}
            className={theme === 'dark' ? 'text-emerald-400 font-medium' : 'text-emerald-700 font-medium'}
          >
            {part}
          </span>
        );
      }

      const subParts = part.split(pattern);
      return subParts.map((sub, sIdx) => {
        if (keywords.includes(sub.toUpperCase())) {
          return (
            <span
              key={`${pIdx}-${sIdx}`}
              className={theme === 'dark' ? 'text-indigo-400 font-bold' : 'text-indigo-700 font-bold'}
            >
              {sub.toUpperCase()}
            </span>
          );
        }
        return <span key={`${pIdx}-${sIdx}`}>{sub}</span>;
      });
    });
  };

  const isDark = theme === 'dark';

  return (
    <div
      className={`rounded-xl border overflow-hidden transition-colors ${
        isDark
          ? 'border-slate-800 bg-[#090D16] shadow-sm'
          : 'border-slate-200 bg-slate-50/90 shadow-2xs'
      }`}
    >
      {/* Top Header */}
      <div
        className={`flex items-center justify-between px-3.5 py-2 border-b ${
          isDark
            ? 'border-slate-800 bg-slate-900/80 text-slate-300'
            : 'border-slate-200/80 bg-slate-100/70 text-slate-700'
        }`}
      >
        <div className="flex items-center gap-2">
          <Code2 className={`w-3.5 h-3.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
          <span className="text-xs font-semibold">{title}</span>
        </div>
        <button
          onClick={handleCopy}
          className={`inline-flex items-center gap-1 text-[11px] font-medium rounded-md px-2 py-1 transition-all cursor-pointer border ${
            isDark
              ? 'text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border-slate-700'
              : 'text-slate-600 hover:text-slate-900 bg-white hover:bg-slate-100 border-slate-200 shadow-2xs'
          }`}
          title="Sao chép câu lệnh SQL"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-500" />
              <span className="text-emerald-500 font-semibold">Đã chép</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3 text-slate-400" />
              <span>Copy SQL</span>
            </>
          )}
        </button>
      </div>

      {/* Code Display */}
      <div
        className={`p-3 font-mono text-xs overflow-x-auto max-h-56 leading-relaxed select-text ${
          isDark ? 'text-slate-200' : 'text-slate-800'
        }`}
      >
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, idx) => (
              <tr
                key={idx}
                className={isDark ? 'hover:bg-slate-800/40 transition-colors' : 'hover:bg-indigo-50/40 transition-colors'}
              >
                <td
                  className={`pr-3 text-right select-none text-[11px] w-6 align-top font-mono ${
                    isDark ? 'text-slate-600' : 'text-slate-400'
                  }`}
                >
                  {idx + 1}
                </td>
                <td className="pl-2 whitespace-pre">{highlightSyntax(line)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
