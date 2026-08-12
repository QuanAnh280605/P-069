'use client';

import React, { useState } from 'react';
import { BusinessMetric, MetricSuggestion } from '@/lib/api';
import { SqlCodeViewer } from '@/components/studio/SqlCodeViewer';
import {
  BarChart3,
  Sparkles,
  Trash2,
  Edit2,
  ShieldCheck,
  Search,
  Plus,
} from 'lucide-react';

interface MetricsCatalogViewProps {
  metrics: BusinessMetric[];
  theme: 'light' | 'dark';
  onDeleteMetric: (id: string) => void;
  onEditMetric: (metric: BusinessMetric) => void;
  onOpenStudio: () => void;
}

export const MetricsCatalogView: React.FC<MetricsCatalogViewProps> = ({
  metrics,
  theme,
  onDeleteMetric,
  onEditMetric,
  onOpenStudio,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  const filtered = metrics.filter(
    (m) =>
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-4 animate-in fade-in">
      {/* Header Bar */}
      <div
        className={`p-4 rounded-2xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
          theme === 'light'
            ? 'bg-white border-slate-200 shadow-2xs'
            : 'bg-slate-900/60 border-slate-800 shadow-lg'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-tight">Business Metrics Catalog</h2>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30">
                {metrics.length} Chỉ Số
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Thư viện chỉ số kinh doanh chuẩn hóa, công thức SQL read-only đã kiểm định
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 w-full md:w-auto">
          <div className="relative w-full md:w-60">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm kiếm chỉ số KPI..."
              className={`w-full pl-8 pr-3 py-1.5 text-xs rounded-xl border focus:outline-none focus:ring-2 focus:ring-indigo-200 ${
                theme === 'light'
                  ? 'bg-slate-50 border-slate-200 text-slate-800'
                  : 'bg-slate-950 border-slate-800 text-slate-200'
              }`}
            />
          </div>

          <button
            onClick={onOpenStudio}
            className="px-3.5 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-all cursor-pointer flex items-center gap-1.5 shrink-0 shadow-xs"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>✨ Sinh thêm với AI</span>
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      {filtered.length === 0 ? (
        <div
          className={`p-12 text-center rounded-2xl border space-y-3 ${
            theme === 'light'
              ? 'bg-white border-slate-200 shadow-2xs'
              : 'bg-slate-900/60 border-slate-800'
          }`}
        >
          <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-500 flex items-center justify-center mx-auto">
            <BarChart3 className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold">Chưa có chỉ số nào trong Library</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Hãy bấm vào nút bên dưới để mở AI Metric Studio và sinh các chỉ số kinh doanh thông minh từ schema.
          </p>
          <button
            onClick={onOpenStudio}
            className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl inline-flex items-center gap-2 shadow-sm cursor-pointer"
          >
            <Sparkles className="w-4 h-4" />
            <span>Mở AI Metric Studio ngay</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((metric) => (
            <div
              key={metric.id}
              className={`p-4 rounded-2xl border transition-all space-y-3 ${
                theme === 'light'
                  ? 'bg-white hover:border-indigo-300 border-slate-200 shadow-2xs'
                  : 'bg-slate-900/60 hover:border-indigo-500/60 border-slate-800 shadow-lg'
              }`}
            >
              {/* Card Header */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white truncate">
                      {metric.name}
                    </h3>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 inline-flex items-center gap-1 shrink-0">
                      <ShieldCheck className="w-3 h-3 text-emerald-500" /> Read-Only
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 line-clamp-2">
                    {metric.description}
                  </p>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => onEditMetric(metric)}
                    className={`p-1.5 rounded-lg transition-colors cursor-pointer border ${
                      theme === 'light'
                        ? 'text-slate-600 hover:text-indigo-700 hover:bg-indigo-50 border-slate-200 shadow-2xs'
                        : 'text-slate-400 hover:text-indigo-300 hover:bg-indigo-950/60 border-slate-800'
                    }`}
                    title="Chỉnh sửa chỉ số"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => onDeleteMetric(metric.id)}
                    className={`p-1.5 rounded-lg transition-colors cursor-pointer border ${
                      theme === 'light'
                        ? 'text-slate-500 hover:text-red-700 hover:bg-red-50 border-slate-200 shadow-2xs'
                        : 'text-slate-400 hover:text-red-400 hover:bg-red-950/40 border-slate-800'
                    }`}
                    title="Xóa chỉ số"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* SQL Viewer */}
              <div>
                <SqlCodeViewer sql={metric.sql_template} title="SQL Definition" theme={theme} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
