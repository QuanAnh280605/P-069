'use client';

import React, { useState } from 'react';
import { SemanticLayerData } from '@/lib/api';
import {
  Layers,
  Database,
  Key,
  Link2,
  Table as TableIcon,
  Sparkles,
  Search,
  Filter,
} from 'lucide-react';

interface DataModelViewProps {
  layer: SemanticLayerData;
  theme: 'light' | 'dark';
  onOpenStudioForTable: (tableName: string) => void;
}

export const DataModelView: React.FC<DataModelViewProps> = ({
  layer,
  theme,
  onOpenStudioForTable,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTable, setSelectedTable] = useState<string>(
    layer.tables[0]?.table_name || ''
  );

  const isDark = theme === 'dark';

  const filteredTables = layer.tables.filter(
    (t) =>
      t.table_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.business_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeTableObj =
    layer.tables.find((t) => t.table_name === selectedTable) || layer.tables[0];

  return (
    <div className="space-y-4 animate-in fade-in">
      {/* Header Info */}
      <div
        className={`p-4 rounded-2xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
          isDark
            ? 'bg-slate-900/80 border-slate-800 shadow-md text-white'
            : 'bg-white border-slate-200 shadow-2xs text-slate-900'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-600 dark:text-sky-400 flex items-center justify-center">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-tight">Data Modeling & Schema Governance</h2>
            <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Cấu trúc lược đồ quan hệ, tên nghiệp vụ tiếng Việt, Dimensions & Measures
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <div className="relative w-full md:w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm kiếm bảng hoặc cột..."
              className={`w-full pl-8 pr-3 py-1.5 text-xs rounded-xl border focus:outline-none focus:ring-2 focus:ring-indigo-500/30 font-medium ${
                isDark
                  ? 'bg-slate-950 border-slate-800 text-slate-100 placeholder-slate-500'
                  : 'bg-slate-50 border-slate-200 text-slate-900 placeholder-slate-400'
              }`}
            />
          </div>
        </div>
      </div>

      {/* Main 2-Column Explorer: Left Table List + Right Column Table Details */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Left: Table Navigator (4 cols) */}
        <div
          className={`lg:col-span-4 rounded-2xl border p-4 space-y-2.5 ${
            isDark
              ? 'bg-[#0E1526] border-slate-800 shadow-md'
              : 'bg-white border-slate-200 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider px-1">
            <span>Danh sách Bảng ({filteredTables.length})</span>
            <Filter className="w-3 h-3 text-slate-400" />
          </div>

          <div className="space-y-1.5">
            {filteredTables.map((tbl) => {
              const isSelected = tbl.table_name === selectedTable;
              return (
                <div
                  key={tbl.table_name}
                  onClick={() => setSelectedTable(tbl.table_name)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-2 ${
                    isSelected
                      ? isDark
                        ? 'bg-indigo-950/80 border-indigo-500/80 shadow-xs'
                        : 'bg-indigo-50 border-indigo-300 shadow-xs'
                      : isDark
                      ? 'bg-slate-900/60 hover:bg-slate-800/80 border-slate-800 text-slate-300'
                      : 'bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-800'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <TableIcon
                        className={`w-3.5 h-3.5 shrink-0 ${
                          isSelected ? 'text-indigo-600 dark:text-indigo-400' : 'text-sky-500'
                        }`}
                      />
                      <span
                        className={`text-xs font-mono font-bold truncate ${
                          isSelected
                            ? isDark
                              ? 'text-white'
                              : 'text-indigo-950'
                            : isDark
                            ? 'text-slate-200'
                            : 'text-slate-900'
                        }`}
                      >
                        {tbl.table_name}
                      </span>
                    </div>
                    <div
                      className={`text-[11px] truncate mt-0.5 font-medium ${
                        isSelected
                          ? isDark
                            ? 'text-indigo-300'
                            : 'text-indigo-700'
                          : isDark
                          ? 'text-slate-400'
                          : 'text-slate-600'
                      }`}
                    >
                      {tbl.business_name}
                    </div>
                  </div>

                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 border ${
                      isSelected
                        ? isDark
                          ? 'bg-indigo-500/30 text-indigo-200 border-indigo-500/40'
                          : 'bg-indigo-100 text-indigo-800 border-indigo-200'
                        : isDark
                        ? 'bg-slate-800 text-slate-400 border-slate-700'
                        : 'bg-slate-200 text-slate-700 border-slate-300'
                    }`}
                  >
                    {tbl.columns.length} cols
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Selected Table Details (8 cols) */}
        {activeTableObj && (
          <div
            className={`lg:col-span-8 rounded-2xl border p-5 space-y-4 ${
              isDark
                ? 'bg-[#0E1526] border-slate-800 shadow-md'
                : 'bg-white border-slate-200 shadow-2xs'
            }`}
          >
            {/* Table Header Bar */}
            <div
              className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b ${
                isDark ? 'border-slate-800' : 'border-slate-200'
              }`}
            >
              <div>
                <div className="flex items-center gap-2">
                  <h3
                    className={`text-base font-bold font-mono ${
                      isDark ? 'text-indigo-400' : 'text-indigo-700'
                    }`}
                  >
                    {activeTableObj.table_name}
                  </h3>
                  <span
                    className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${
                      isDark
                        ? 'bg-indigo-950/80 text-indigo-300 border-indigo-800'
                        : 'bg-indigo-100 text-indigo-900 border-indigo-200'
                    }`}
                  >
                    {activeTableObj.business_name}
                  </span>
                </div>
                <p className={`text-xs mt-1 font-medium ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {activeTableObj.description || 'Bảng chứa thông tin lược đồ cơ sở dữ liệu'}
                </p>
              </div>

              <button
                onClick={() => onOpenStudioForTable(activeTableObj.table_name)}
                className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 rounded-xl transition-all cursor-pointer flex items-center gap-1.5 shrink-0 shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5 text-white" />
                <span>Sinh Metric cho bảng này</span>
              </button>
            </div>

            {/* Column Schema Table */}
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr
                    className={`border-b text-[11px] font-bold uppercase tracking-wider ${
                      isDark
                        ? 'border-slate-800 text-slate-300 bg-slate-900/90'
                        : 'border-slate-200 text-slate-800 bg-slate-100'
                    }`}
                  >
                    <th className="py-3 px-3.5">Cột (Column)</th>
                    <th className="py-3 px-3.5">Kiểu dữ liệu</th>
                    <th className="py-3 px-3.5">Tên nghiệp vụ (VN)</th>
                    <th className="py-3 px-3.5">Phân loại</th>
                    <th className="py-3 px-3.5">Mẫu dữ liệu</th>
                  </tr>
                </thead>
                <tbody className={`divide-y ${isDark ? 'divide-slate-800' : 'divide-slate-200'}`}>
                  {activeTableObj.columns.map((col) => {
                    const isPK = col.data_type.toUpperCase().includes('PK');
                    const isFK = col.data_type.toUpperCase().includes('FK');
                    const isMeasure =
                      col.data_type.toUpperCase().includes('INT') ||
                      col.data_type.toUpperCase().includes('NUMERIC') ||
                      col.data_type.toUpperCase().includes('DECIMAL') ||
                      col.data_type.toUpperCase().includes('FLOAT');

                    return (
                      <tr
                        key={col.column_name}
                        className={
                          isDark
                            ? 'hover:bg-slate-800/40 transition-colors'
                            : 'hover:bg-indigo-50/40 transition-colors'
                        }
                      >
                        <td className="py-2.5 px-3.5 font-mono font-bold flex items-center gap-1.5">
                          {isPK && <Key className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
                          {isFK && <Link2 className="w-3.5 h-3.5 text-indigo-500 shrink-0" />}
                          <span className={isDark ? 'text-slate-100' : 'text-slate-900'}>
                            {col.column_name}
                          </span>
                        </td>
                        <td
                          className={`py-2.5 px-3.5 font-mono text-[11px] font-semibold ${
                            isDark ? 'text-slate-300' : 'text-slate-700'
                          }`}
                        >
                          {col.data_type}
                        </td>
                        <td
                          className={`py-2.5 px-3.5 font-bold ${
                            isDark ? 'text-slate-200' : 'text-slate-900'
                          }`}
                        >
                          {col.business_name}
                        </td>
                        <td className="py-2.5 px-3.5">
                          {isMeasure ? (
                            <span
                              className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border inline-block ${
                                isDark
                                  ? 'bg-blue-950/80 text-blue-300 border-blue-800'
                                  : 'bg-blue-100 text-blue-900 border-blue-300'
                              }`}
                            >
                              Measure
                            </span>
                          ) : (
                            <span
                              className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border inline-block ${
                                isDark
                                  ? 'bg-purple-950/80 text-purple-300 border-purple-800'
                                  : 'bg-purple-100 text-purple-900 border-purple-300'
                              }`}
                            >
                              Dimension
                            </span>
                          )}
                        </td>
                        <td
                          className={`py-2.5 px-3.5 font-mono text-[11px] font-medium ${
                            isDark ? 'text-slate-400' : 'text-slate-600'
                          }`}
                        >
                          {col.sample_value || '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
