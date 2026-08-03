'use client';

import React, { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { getLayerById, updateLayer, SemanticLayerData, BusinessMetric, SemanticTable } from '@/lib/api';
import { MetricModal } from '@/components/modals/MetricModal';
import {
  ArrowLeft,
  Save,
  Share2,
  Table as TableIcon,
  Sparkles,
  Edit2,
  Trash2,
  PlusCircle,
  CheckCircle2,
  Clock,
  Database,
  Code,
  FileSpreadsheet,
  Layers,
} from 'lucide-react';

import { useAuth } from '@/context/AuthContext';

export default function ReviewPage({ params }: { params: Promise<{ db_id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [layer, setLayer] = useState<SemanticLayerData | null>(null);
  const [activeTab, setActiveTab] = useState<'tables' | 'metrics'>('tables');

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingMetric, setEditingMetric] = useState<BusinessMetric | null>(null);

  useEffect(() => {
    const data = getLayerById(resolvedParams.db_id);
    if (data) {
      setLayer(data);
    }
  }, [resolvedParams.db_id]);

  if (!user && !isLoading) {
    return (
      <div className="glass-card rounded-2xl p-10 text-center max-w-lg mx-auto my-12 border border-indigo-500/20 shadow-2xl">
        <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center mx-auto mb-4 border border-indigo-500/30">
          <Database className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Yêu cầu Đăng nhập</h2>
        <p className="text-xs text-slate-400 mb-6">
          Vui lòng đăng nhập để xem và quản lý Semantic Layer Builder & HITL Review.
        </p>
        <Link href="/login" className="gradient-btn px-6 py-2.5 text-xs font-bold text-white rounded-xl inline-block shadow-lg">
          Đăng nhập ngay (JWT / Google)
        </Link>
      </div>
    );
  }

  if (!layer) {
    return (
      <div className="text-center py-20 text-slate-400">
        <Database className="w-12 h-12 mx-auto text-slate-600 mb-3" />
        <p>Không tìm thấy thông tin Semantic Layer</p>
        <Link href="/" className="text-indigo-400 font-semibold underline text-sm mt-2 inline-block">
          ← Quay lại Dashboard
        </Link>
      </div>
    );
  }

  const handleSaveOfficial = () => {
    if (!layer) return;
    const updated: SemanticLayerData = {
      ...layer,
      status: 'Saved',
      updated_at: new Date().toISOString().replace('T', ' ').slice(0, 16),
    };
    updateLayer(updated);
    setLayer(updated);
    alert('✅ Đã lưu chính thức Semantic Layer thành công!');
  };

  const handleTableBusinessNameChange = (tIdx: number, val: string) => {
    const updatedTables = [...layer.tables];
    updatedTables[tIdx].business_name = val;
    const updatedLayer = { ...layer, tables: updatedTables, status: 'Draft' as const };
    setLayer(updatedLayer);
    updateLayer(updatedLayer);
  };

  const handleTableDescriptionChange = (tIdx: number, val: string) => {
    const updatedTables = [...layer.tables];
    updatedTables[tIdx].description = val;
    const updatedLayer = { ...layer, tables: updatedTables, status: 'Draft' as const };
    setLayer(updatedLayer);
    updateLayer(updatedLayer);
  };

  const handleColumnBusinessNameChange = (tIdx: number, cIdx: number, val: string) => {
    const updatedTables = [...layer.tables];
    updatedTables[tIdx].columns[cIdx].business_name = val;
    const updatedLayer = { ...layer, tables: updatedTables, status: 'Draft' as const };
    setLayer(updatedLayer);
    updateLayer(updatedLayer);
  };

  const handleSaveMetric = (metric: BusinessMetric) => {
    const updatedMetrics = [...layer.metrics];
    const existingIndex = updatedMetrics.findIndex((m) => m.id === metric.id);
    if (existingIndex !== -1) {
      updatedMetrics[existingIndex] = metric;
    } else {
      updatedMetrics.push(metric);
    }
    const updatedLayer = { ...layer, metrics: updatedMetrics, status: 'Draft' as const };
    setLayer(updatedLayer);
    updateLayer(updatedLayer);
  };

  const handleDeleteMetric = (mId: string) => {
    const updatedMetrics = layer.metrics.filter((m) => m.id !== mId);
    const updatedLayer = { ...layer, metrics: updatedMetrics, status: 'Draft' as const };
    setLayer(updatedLayer);
    updateLayer(updatedLayer);
  };

  return (
    <div className="space-y-6 animate-in fade-in">
      {/* Top Review Header */}
      <div className="glass-card rounded-2xl p-5 border border-indigo-500/20 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="p-2 rounded-xl bg-slate-900 border border-slate-700/80 text-slate-300 hover:text-white hover:border-indigo-500 transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white tracking-tight">
                ⚙️ REVIEW SEMANTIC LAYER: {layer.db_name}
              </h1>
              {layer.status === 'Saved' ? (
                <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold px-2.5 py-0.5 rounded-full inline-flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Saved
                </span>
              ) : (
                <span className="bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs font-bold px-2.5 py-0.5 rounded-full inline-flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Draft
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              HITL Workflow — Kiểm tra & duyệt tên nghiệp vụ, mô tả cột và chỉ số thống kê
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto justify-end">
          <Link
            href={`/semantic/${layer.id}/export`}
            className="px-4 py-2 text-xs font-semibold text-slate-200 bg-slate-900/90 border border-slate-700/80 rounded-xl hover:border-indigo-500 flex items-center gap-1.5 transition-colors"
          >
            <Share2 className="w-3.5 h-3.5 text-cyan-400" /> 📤 Export
          </Link>

          <button
            onClick={handleSaveOfficial}
            className="gradient-btn px-5 py-2 text-xs font-semibold text-white rounded-xl shadow-lg flex items-center gap-1.5"
          >
            <Save className="w-3.5 h-3.5" /> 💾 Lưu Chính Thức
          </button>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-3 border-b border-slate-800 pb-1">
        <button
          onClick={() => setActiveTab('tables')}
          className={`px-5 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
            activeTab === 'tables'
              ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-lg'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <TableIcon className="w-4 h-4" /> [ TAB A: BẢNG & CỘT (TABLES & COLUMNS) ]
        </button>

        <button
          onClick={() => setActiveTab('metrics')}
          className={`px-5 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
            activeTab === 'metrics'
              ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-lg'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <Sparkles className="w-4 h-4 text-cyan-400" /> [ TAB B: BUSINESS METRICS LIBRARY ({layer.metrics.length}) ]
        </button>
      </div>

      {/* TAB A: TABLES & COLUMNS */}
      {activeTab === 'tables' && (
        <div className="space-y-6">
          {layer.tables.map((tbl, tIdx) => (
            <div
              key={tbl.table_name}
              className="glass-card rounded-2xl p-6 border border-slate-800 hover:border-slate-700/80 shadow-lg transition-all"
            >
              {/* Table Metadata Header */}
              <div className="mb-5 pb-4 border-b border-slate-800 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-slate-400 uppercase bg-slate-900 px-2 py-1 rounded border border-slate-800">
                    📂 Bảng: {tbl.table_name}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 uppercase mb-1">
                      Tên nghiệp vụ:
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={tbl.business_name}
                        onChange={(e) => handleTableBusinessNameChange(tIdx, e.target.value)}
                        className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-3 py-1.5 text-sm text-indigo-300 font-semibold focus:outline-none focus:border-indigo-500"
                      />
                      <Edit2 className="w-3.5 h-3.5 text-slate-500 absolute right-3 top-2.5 pointer-events-none" />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-400 uppercase mb-1">
                      Mô tả:
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={tbl.description}
                        onChange={(e) => handleTableDescriptionChange(tIdx, e.target.value)}
                        className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-indigo-500"
                      />
                      <Edit2 className="w-3.5 h-3.5 text-slate-500 absolute right-3 top-2.5 pointer-events-none" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Columns Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 font-bold uppercase bg-slate-900/60">
                      <th className="py-2.5 px-3">Tên Cột DB</th>
                      <th className="py-2.5 px-3">Kiểu Dữ Liệu</th>
                      <th className="py-2.5 px-3">Tên Nghiệp Vụ (AI)</th>
                      <th className="py-2.5 px-3">Mẫu DL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {tbl.columns.map((col, cIdx) => (
                      <tr key={col.column_name} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-3 font-mono font-semibold text-slate-200">
                          {col.column_name}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="font-mono text-[11px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            {col.data_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          <input
                            type="text"
                            value={col.business_name}
                            onChange={(e) =>
                              handleColumnBusinessNameChange(tIdx, cIdx, e.target.value)
                            }
                            className="bg-slate-900/90 border border-slate-700/70 rounded-lg px-2.5 py-1 text-xs text-slate-100 w-full focus:outline-none focus:border-indigo-500"
                          />
                        </td>
                        <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px]">
                          {col.sample_value || 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB B: BUSINESS METRICS LIBRARY */}
      {activeTab === 'metrics' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-300 uppercase tracking-wide">
              Danh sách Chỉ số thống kê (Business Metrics)
            </h2>
            <button
              onClick={() => {
                setEditingMetric(null);
                setIsModalOpen(true);
              }}
              className="gradient-btn px-4 py-2 text-xs font-semibold text-white rounded-xl shadow flex items-center gap-1.5"
            >
              <PlusCircle className="w-4 h-4" /> ➕ Thêm Metric thủ công
            </button>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {layer.metrics.map((metric, idx) => (
              <div
                key={metric.id}
                className="glass-card rounded-2xl p-5 border border-slate-800 hover:border-slate-700/80 shadow-md space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {metric.source === 'ai' ? (
                      <span className="bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider flex items-center gap-1">
                        <Sparkles className="w-3 h-3 text-purple-400" /> [AI]
                      </span>
                    ) : (
                      <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" /> [Manual]
                      </span>
                    )}
                    <h3 className="text-sm font-bold text-slate-100">
                      {idx + 1}. {metric.name}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setEditingMetric(metric);
                        setIsModalOpen(true);
                      }}
                      className="px-2.5 py-1 text-xs font-semibold text-slate-300 bg-slate-900 border border-slate-700/80 rounded-lg hover:text-white hover:border-indigo-500 flex items-center gap-1 transition-colors"
                    >
                      <Edit2 className="w-3 h-3 text-indigo-400" /> ✏️ Sửa
                    </button>

                    <button
                      onClick={() => handleDeleteMetric(metric.id)}
                      className="px-2.5 py-1 text-xs font-semibold text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg hover:bg-red-500/20 flex items-center gap-1 transition-colors"
                    >
                      <Trash2 className="w-3 h-3" /> ❌ Xóa
                    </button>
                  </div>
                </div>

                <p className="text-xs text-slate-400">
                  <span className="font-semibold text-slate-300">Mô tả:</span> {metric.description}
                </p>

                <div>
                  <span className="text-[11px] font-semibold text-slate-400 block mb-1">
                    SQL Template:
                  </span>
                  <pre className="bg-slate-950 p-3.5 rounded-xl border border-indigo-500/20 font-mono text-xs text-emerald-400 overflow-x-auto whitespace-pre-wrap">
                    {metric.sql_template}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Metric Modal */}
      <MetricModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveMetric}
        initialMetric={editingMetric}
      />
    </div>
  );
}
