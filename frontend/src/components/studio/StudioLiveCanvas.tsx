'use client';

import React from 'react';
import { MetricSuggestion } from '@/lib/api';
import { SqlCodeViewer } from './SqlCodeViewer';
import {
  ShieldCheck,
  PlusCircle,
  Edit3,
  Sparkles,
  Database,
  Calculator,
  Layers,
  ArrowRight,
} from 'lucide-react';

interface StudioLiveCanvasProps {
  metric: MetricSuggestion | null;
  allSuggestions: MetricSuggestion[];
  selectedIndex: number;
  onSelectSuggestion: (index: number) => void;
  onAddMetric: (metric: MetricSuggestion, index: number) => void;
  onEditMetric: (metric: MetricSuggestion, index: number) => void;
  onRefineWithAI: (metric: MetricSuggestion) => void;
  isAdding?: boolean;
  theme?: 'light' | 'dark';
}

export const StudioLiveCanvas: React.FC<StudioLiveCanvasProps> = ({
  metric,
  allSuggestions,
  selectedIndex,
  onSelectSuggestion,
  onAddMetric,
  onEditMetric,
  onRefineWithAI,
  isAdding = false,
  theme = 'light',
}) => {
  const isDark = theme === 'dark';

  if (!metric) {
    return (
      <div
        className={`h-full flex flex-col items-center justify-center p-8 text-center rounded-2xl border transition-colors min-h-[420px] ${
          isDark
            ? 'bg-[#0E1526] border-slate-800 text-slate-300 shadow-md'
            : 'bg-white border-slate-200/80 text-slate-700 shadow-xs'
        }`}
      >
        <div
          className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 border ${
            isDark
              ? 'bg-indigo-950/60 border-indigo-800 text-indigo-400'
              : 'bg-amber-50 border-amber-200/60 text-amber-600 shadow-xs'
          }`}
        >
          <Sparkles className="w-7 h-7" />
        </div>
        <h3 className={`text-base font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-800'}`}>
          Live Metric Canvas & Inspector
        </h3>
        <p className="text-xs text-slate-400 max-w-sm mt-1.5 leading-relaxed">
          Gõ yêu cầu vào khung chat bên trái hoặc chọn gợi ý có sẵn để AI phân tích lược đồ DB và hiển thị công thức chỉ số tại đây.
        </p>
        <div
          className={`mt-6 p-4 rounded-xl border text-left max-w-sm w-full space-y-2 ${
            isDark
              ? 'bg-[#131B2E] border-slate-800'
              : 'bg-slate-50 border-slate-200/70'
          }`}
        >
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-indigo-500" /> Tính năng Canvas
          </div>
          <ul className={`text-xs space-y-1.5 pl-1 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
            <li className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Kiểm định an toàn Read-Only qua AST
            </li>
            <li className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" /> Tự động thụt đầu dòng SQL chuẩn hóa
            </li>
            <li className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Lưu 1-click vào Semantic Layer Library
            </li>
          </ul>
        </div>
      </div>
    );
  }

  // Extract table names mentioned in SQL
  const extractTablesFromSql = (sql: string): string[] => {
    const fromMatches = sql.match(/FROM\s+([a-zA-Z0-9_]+)/gi) || [];
    const joinMatches = sql.match(/JOIN\s+([a-zA-Z0-9_]+)/gi) || [];
    const tables = new Set<string>();
    [...fromMatches, ...joinMatches].forEach((m) => {
      const parts = m.trim().split(/\s+/);
      if (parts[1]) tables.add(parts[1].toLowerCase());
    });
    return Array.from(tables);
  };

  const detectedTables = extractTablesFromSql(metric.sql_template);

  return (
    <div
      className={`h-full flex flex-col rounded-2xl border overflow-hidden transition-colors ${
        isDark
          ? 'bg-[#0E1526] border-slate-800 text-slate-200 shadow-md'
          : 'bg-white border-slate-200 text-slate-800 shadow-xs'
      }`}
    >
      {/* Top Suggestion Switcher Tabs */}
      {allSuggestions.length > 1 && (
        <div
          className={`flex items-center gap-2 p-2.5 border-b overflow-x-auto ${
            isDark ? 'bg-[#131B2E] border-slate-800' : 'bg-slate-50 border-slate-200'
          }`}
        >
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider pl-1 shrink-0">
            Đề xuất ({allSuggestions.length}):
          </span>
          <div className="flex items-center gap-1.5">
            {allSuggestions.map((s, idx) => (
              <button
                key={idx}
                onClick={() => onSelectSuggestion(idx)}
                className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer whitespace-nowrap border ${
                  idx === selectedIndex
                    ? isDark
                      ? 'bg-slate-800 text-indigo-300 border-indigo-500/60 font-bold shadow-xs'
                      : 'bg-white text-indigo-700 shadow-xs border-slate-300 font-bold'
                    : isDark
                    ? 'text-slate-400 hover:text-white bg-slate-900 border-slate-800'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 border-transparent'
                }`}
              >
                Chỉ số #{idx + 1}: {s.name.slice(0, 24)}
                {s.name.length > 24 ? '...' : ''}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main Canvas Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {/* Metric Header Card */}
        <div
          className={`p-4 rounded-xl border space-y-2.5 ${
            isDark
              ? 'bg-[#162036] border-slate-750'
              : 'bg-gradient-to-br from-slate-50 to-indigo-50/40 border-slate-200/80'
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                isDark
                  ? 'bg-indigo-950/80 text-indigo-300 border-indigo-800'
                  : 'bg-indigo-100/70 text-indigo-700 border-indigo-200/60'
              }`}
            >
              <Sparkles className="w-3 h-3 text-indigo-500" /> AI Đề Xuất
            </span>
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${
                isDark
                  ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800'
                  : 'bg-emerald-50 text-emerald-700 border-emerald-200'
              }`}
            >
              <ShieldCheck className="w-3 h-3 text-emerald-500" /> 🟢 AST Validated (Read-Only SELECT)
            </span>
          </div>

          <div>
            <h2 className={`text-base font-bold tracking-tight leading-snug ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {metric.name}
            </h2>
            <p className={`text-xs mt-1 leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
              {metric.description}
            </p>
          </div>
        </div>

        {/* Business Logic & Calculation Explanation Card */}
        <div
          className={`p-3.5 rounded-xl border space-y-1.5 ${
            isDark
              ? 'bg-amber-950/30 border-amber-800/40 text-amber-200'
              : 'bg-amber-50/40 border-amber-200/60 text-slate-700'
          }`}
        >
          <div
            className={`flex items-center gap-1.5 text-xs font-bold ${
              isDark ? 'text-amber-300' : 'text-amber-800'
            }`}
          >
            <Calculator className="w-3.5 h-3.5 text-amber-500" /> Diễn giải công thức nghiệp vụ
          </div>
          <p className="text-xs leading-relaxed">
            Chỉ số này tự động tổng hợp dữ liệu từ các giao dịch thoả mãn điều kiện kinh doanh, đảm bảo tính toán an toàn và không làm thay đổi dữ liệu bảng gốc.
          </p>
        </div>

        {/* SQL Code Block */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs font-semibold px-0.5">
            <span className={isDark ? 'text-slate-200' : 'text-slate-700'}>Câu lệnh SQL Template</span>
            <span className="text-[11px] text-slate-400 font-normal">Dialect: PostgreSQL / ANSI SQL</span>
          </div>
          <SqlCodeViewer sql={metric.sql_template} title="SQL Template Template" theme={theme} />
        </div>

        {/* Schema Dependencies */}
        {detectedTables.length > 0 && (
          <div className="flex items-center gap-2 pt-1 flex-wrap">
            <span className="text-xs text-slate-400 flex items-center gap-1">
              <Database className="w-3.5 h-3.5 text-slate-400" /> Bảng tham chiếu:
            </span>
            {detectedTables.map((tbl) => (
              <span
                key={tbl}
                className={`px-2 py-0.5 text-xs font-mono font-medium rounded-md border ${
                  isDark
                    ? 'bg-slate-900 border-slate-800 text-slate-300'
                    : 'bg-slate-100 border-slate-200 text-slate-700'
                }`}
              >
                {tbl}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Action Footer Bar */}
      <div
        className={`p-4 border-t flex flex-wrap items-center justify-between gap-3 ${
          isDark ? 'bg-[#131B2E] border-slate-800' : 'bg-slate-50 border-slate-200'
        }`}
      >
        <div className="flex items-center gap-2">
          <button
            onClick={() => onRefineWithAI(metric)}
            className={`px-3 py-2 text-xs font-semibold rounded-xl border transition-all cursor-pointer inline-flex items-center gap-1.5 shadow-2xs ${
              isDark
                ? 'bg-slate-900 hover:bg-slate-800 text-slate-200 border-slate-700'
                : 'bg-white hover:bg-slate-100 text-slate-700 border-slate-200'
            }`}
            title="Nhờ AI tinh chỉnh chỉ số này qua khung chat"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" /> Nhờ AI tinh chỉnh
          </button>
          <button
            onClick={() => onEditMetric(metric, selectedIndex)}
            className={`px-3 py-2 text-xs font-semibold rounded-xl border transition-all cursor-pointer inline-flex items-center gap-1.5 shadow-2xs ${
              isDark
                ? 'bg-slate-900 hover:bg-slate-800 text-slate-200 border-slate-700'
                : 'bg-white hover:bg-slate-100 text-slate-700 border-slate-200'
            }`}
            title="Chỉnh sửa thủ công tên, mô tả hoặc SQL"
          >
            <Edit3 className="w-3.5 h-3.5 text-slate-400" /> Chỉnh sửa
          </button>
        </div>

        <button
          onClick={() => onAddMetric(metric, selectedIndex)}
          disabled={isAdding}
          className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 rounded-xl transition-all cursor-pointer inline-flex items-center gap-2 shadow-sm disabled:opacity-50"
        >
          {isAdding ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              <span>Đang lưu...</span>
            </>
          ) : (
            <>
              <PlusCircle className="w-4 h-4" />
              <span>Lưu vào Semantic Layer</span>
              <ArrowRight className="w-3.5 h-3.5 opacity-80" />
            </>
          )}
        </button>
      </div>
    </div>
  );
};
