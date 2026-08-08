'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { Header } from '@/components/layout/Header';
import ImportedSchemaList from '@/components/ImportedSchemaList';
import LiveDbList from '@/components/LiveDbList';
import SqlDumpPreviewUploader from '@/components/SqlDumpPreviewUploader';
import {
  getLocalLayers,
  updateLayer,
  deleteLayer,
  connectLiveTargetDb,
  SemanticLayerData,
} from '@/lib/api';
import {
  Database,
  PlusCircle,
  Zap,
  CheckCircle2,
  Loader2,
  Clock,
  ExternalLink,
  Trash2,
  FolderKanban,
  Server,
  KeyRound,
  Sparkles,
} from 'lucide-react';

export default function DashboardPage() {
  const router = useRouter();
  const { user, token, isLoading } = useAuth();
  const [layers, setLayers] = useState<SemanticLayerData[]>([]);
  const [savedSchemaRevision, setSavedSchemaRevision] = useState(0);
  const [mounted, setMounted] = useState(false);

  // Form State
  const [dbName, setDbName] = useState('');
  const [dbType, setDbType] = useState<'auto' | 'postgresql' | 'mysql' | 'sqlite'>('auto');
  const [connUrl, setConnUrl] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState<number>(0); // 0: Idle, 1: Introspect, 2: Enrich, 3: Metrics, 4: Done
  const [liveDbRevision, setLiveDbRevision] = useState(0);
  const [liveDbError, setLiveDbError] = useState('');

  useEffect(() => {
    setMounted(true);
    setLayers(getLocalLayers());
  }, []);

  const handleStartAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dbName.trim() || !connUrl.trim()) return;

    setIsAnalyzing(true);
    setAnalysisStep(1);
    setLiveDbError('');

    if (token) {
      try {
        await connectLiveTargetDb(dbName.trim(), dbType, connUrl.trim(), token);
        setAnalysisStep(4);
        setLiveDbRevision((rev) => rev + 1);
        setDbName('');
        setConnUrl('');
        setIsAnalyzing(false);
        return;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Kết nối và trích xuất schema thất bại';
        setLiveDbError(msg);
        setIsAnalyzing(false);
        return;
      }
    }

    // Simulate 3-step progress feedback for local/offline demo
    setTimeout(() => {
      setAnalysisStep(2);
      setTimeout(() => {
        setAnalysisStep(3);
        setTimeout(() => {
          setAnalysisStep(4);
          // Create new local demo layer
          const newId = `db-${Date.now()}`;
          const newLayer: SemanticLayerData = {
            id: newId,
            db_name: dbName.trim(),
            db_type: dbType,
            conn_url: connUrl.trim(),
            status: 'Draft',
            updated_at: new Date().toISOString().replace('T', ' ').slice(0, 16),
            tables: [
              {
                table_name: 'orders',
                business_name: 'Đơn hàng',
                description: 'Bảng chứa lịch sử giao dịch bán hàng',
                columns: [
                  { column_name: 'order_id', data_type: 'INTEGER (PK)', business_name: 'Mã đơn hàng', sample_value: '1001' },
                  { column_name: 'customer_id', data_type: 'INTEGER (FK)', business_name: 'Mã khách hàng', sample_value: 'C-01' },
                  { column_name: 'amount', data_type: 'NUMERIC', business_name: 'Tổng tiền đơn hàng', sample_value: '250,000' },
                  { column_name: 'created_at', data_type: 'TIMESTAMP', business_name: 'Thời gian đặt hàng', sample_value: '2026-08-01' },
                ],
              },
              {
                table_name: 'products',
                business_name: 'Sản phẩm',
                description: 'Bảng danh mục sản phẩm và giá',
                columns: [
                  { column_name: 'product_id', data_type: 'INTEGER (PK)', business_name: 'Mã sản phẩm', sample_value: 'P-99' },
                  { column_name: 'price', data_type: 'NUMERIC', business_name: 'Đơn giá', sample_value: '120,000' },
                ],
              },
            ],
            metrics: [
              {
                id: `m_${Date.now()}`,
                name: 'Tổng doanh thu',
                description: 'Tổng tiền các đơn hàng',
                sql_template: 'SELECT SUM(amount) FROM orders',
                source: 'ai',
              },
            ],
          };
          updateLayer(newLayer);
          setLayers(getLocalLayers());
          setIsAnalyzing(false);
          setAnalysisStep(0);
          setDbName('');
          setConnUrl('');
          router.push(`/semantic/${newId}/review`);
        }, 1000);
      }, 1000);
    }, 1000);
  };

  const handleDelete = (id: string) => {
    if (confirm('Bạn có chắc chắn muốn xóa Semantic Layer này?')) {
      deleteLayer(id);
      setLayers(getLocalLayers());
    }
  };

  if (!mounted || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0B0F19]">
        <div className="flex items-center gap-3 text-indigo-400">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span className="text-sm font-semibold">Đang tải dữ liệu...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col bg-[#0B0F19]">
        <Header />
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-8">
          <div className="space-y-12 py-6 animate-in fade-in">
            {/* Hero Guest Banner */}
            <div className="glass-card rounded-3xl p-8 md:p-12 border border-indigo-500/20 shadow-2xl relative overflow-hidden text-center max-w-4xl mx-auto">
              <div className="absolute top-0 right-1/2 translate-x-1/2 w-96 h-96 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />

              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-bold mb-6">
                <Sparkles className="w-4 h-4" /> AI SEMANTIC LAYER AGENT PLATFORM
              </div>

              <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight text-white leading-tight">
                Chuẩn hóa Semantic Layer & Business Metrics bằng <span className="gradient-text">AI Agent</span>
              </h1>

              <p className="text-sm md:text-base text-slate-300 mt-4 max-w-2xl mx-auto leading-relaxed">
                Tự động Introspect DB Schema, đề xuất tên nghiệp vụ, định nghĩa Business Metrics thống nhất và xuất cấu hình JSON / YAML cho dbt, Metabase và Looker Studio.
              </p>

              {/* Auth Required Notice & CTA */}
              <div className="mt-8 pt-8 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/login"
                  className="gradient-btn w-full sm:w-auto px-8 py-3 text-sm font-bold text-white rounded-xl shadow-xl flex items-center justify-center gap-2 group"
                >
                  <KeyRound className="w-4 h-4" /> Đăng nhập ngay (JWT / Google)
                </Link>

                <Link
                  href="/register"
                  className="w-full sm:w-auto px-8 py-3 text-sm font-bold text-slate-200 bg-slate-900 border border-slate-700 hover:border-indigo-500/80 rounded-xl flex items-center justify-center gap-2 transition-all"
                >
                  <PlusCircle className="w-4 h-4 text-cyan-400" /> Tạo tài khoản mới
                </Link>
              </div>
            </div>

            {/* Feature Highlights Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
              <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-3">
                <div className="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                  <Server className="w-5 h-5" />
                </div>
                <h3 className="text-base font-bold text-white">Schema Introspection</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Đọc metadata schema PostgreSQL, MySQL, SQLite qua SQLAlchemy Inspector mà không thực thi bất kỳ truy vấn SELECT data nào.
                </p>
              </div>

              <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-3">
                <div className="w-10 h-10 rounded-xl bg-purple-600/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
                  <Sparkles className="w-5 h-5" />
                </div>
                <h3 className="text-base font-bold text-white">LLM Business Enrich</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  AI tự động chuyển đổi tên bảng/cột kỹ thuật sang tên nghiệp vụ tiếng Việt dễ hiểu và đề xuất Business Metrics chuẩn hóa.
                </p>
              </div>

              <div className="glass-card rounded-2xl p-6 border border-slate-800 space-y-3">
                <div className="w-10 h-10 rounded-xl bg-cyan-600/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30">
                  <FolderKanban className="w-5 h-5" />
                </div>
                <h3 className="text-base font-bold text-white">HITL Review & Export</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Quy trình duyệt Human-In-The-Loop cho phép chỉnh sửa 1-click trước khi xuất cấu hình chính thức ra file JSON hoặc YAML.
                </p>
              </div>
            </div>
          </div>
        </main>
        <footer className="py-6 border-t border-slate-800/60 text-center text-xs text-slate-500">
          © 2026 AI Semantic Layer Agent. All rights reserved. Managed with JWT & Google Auth.
        </footer>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#0B0F19]">
      <Header />
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-8">
        <div className="space-y-8 animate-in fade-in">
          {/* Welcome Banner */}
          <div className="glass-card rounded-2xl p-6 md:p-8 border border-indigo-500/20 shadow-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6 relative overflow-hidden">
            <div className="absolute -right-10 -bottom-10 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold mb-3">
                <Sparkles className="w-3.5 h-3.5" /> AI Governance Engine v1.0
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                Quản lý Kết nối Database & Semantic Layers
              </h1>
              <p className="text-sm text-slate-400 mt-1 max-w-2xl">
                Tự động phân tích Metadata Schema, enrich tên nghiệp vụ bằng LLM và định nghĩa Business Metrics chuẩn hóa với quy trình duyệt Human-In-The-Loop.
              </p>
            </div>
          </div>

          <SqlDumpPreviewUploader onSaved={() => setSavedSchemaRevision((value) => value + 1)} />

          {token && <ImportedSchemaList token={token} refreshKey={savedSchemaRevision} />}

          {/* Live DB List */}
          {token && <LiveDbList token={token} refreshKey={liveDbRevision} />}

          {/* Section 1: Connect New Database Form */}
          <div className="glass-card rounded-2xl p-6 md:p-8 border border-indigo-500/20 shadow-xl">
            <div className="flex items-center gap-3 pb-4 mb-6 border-b border-slate-800">
              <div className="w-9 h-9 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                <PlusCircle className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">
                  ➕ KẾT NỐI DATABASE MỚI
                </h2>
                <p className="text-xs text-slate-400">
                  Nhập thông tin kết nối để AI tự động Introspect & Enrich Schema
                </p>
              </div>
            </div>

            <form onSubmit={handleStartAnalysis} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-2">
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                    Tên gợi nhớ DB
                  </label>
                  <input
                    type="text"
                    required
                    disabled={isAnalyzing}
                    placeholder="e.g. E-Commerce Production Database"
                    value={dbName}
                    onChange={(e) => setDbName(e.target.value)}
                    className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-500 disabled:opacity-50"
                  />
                </div>

                <div className="md:col-span-1">
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                    DIALECT OVERRIDE
                  </label>
                  <select
                    disabled={isAnalyzing}
                    value={dbType}
                    onChange={(e) => setDbType(e.target.value as 'auto' | 'postgresql' | 'mysql' | 'sqlite')}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer disabled:opacity-50"
                  >
                    <option value="auto">Auto detect</option>
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="sqlite">SQLite</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Chuỗi Kết Nối (Connection URL)
                </label>
                <input
                  type="text"
                  required
                  disabled={isAnalyzing}
                  placeholder="postgresql+asyncpg://user:pass@localhost:5432/ecommerce_db"
                  value={connUrl}
                  onChange={(e) => setConnUrl(e.target.value)}
                  className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-100 font-mono focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-600 disabled:opacity-50"
                />
                <p className="text-[11px] text-slate-400 mt-1.5 flex items-center gap-1">
                  🔒 Chuỗi kết nối được mã hóa an toàn bằng Fernet Symmetric Encryption và chỉ dùng SQLAlchemy Inspector để trích xuất metadata.
                </p>
                {liveDbError && (
                  <p className="text-xs text-red-400 mt-2 font-medium bg-red-950/40 p-2.5 rounded-lg border border-red-800">
                    ❌ {liveDbError}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-end pt-2">
                <button
                  type="submit"
                  disabled={isAnalyzing}
                  className="gradient-btn px-6 py-2.5 text-xs font-bold text-white rounded-xl shadow-lg flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Đang Phân Tích...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      <span>⚡ Bắt đầu Phân tích Schema (Auto Introspect & Enrich)</span>
                    </>
                  )}
                </button>
              </div>
            </form>

            {/* Analysis Progress Steps */}
            {isAnalyzing && (
              <div className="mt-8 pt-6 border-t border-slate-800/80">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div
                    className={`p-4 rounded-xl border flex items-center gap-3 transition-all ${
                      analysisStep >= 1
                        ? 'bg-indigo-950/40 border-indigo-500/50 text-indigo-300'
                        : 'bg-slate-900/40 border-slate-800 text-slate-400'
                    }`}
                  >
                    {analysisStep > 1 ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : (
                      <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
                    )}
                    <div>
                      <div className="text-xs font-bold">1. Introspect Schema</div>
                      <div className="text-[11px] text-slate-400">Đọc bảng & kiểu dữ liệu</div>
                    </div>
                  </div>

                  <div
                    className={`p-4 rounded-xl border flex items-center gap-3 transition-all ${
                      analysisStep >= 2
                        ? 'bg-indigo-950/40 border-indigo-500/50 text-indigo-300'
                        : 'bg-slate-900/40 border-slate-800 text-slate-400'
                    }`}
                  >
                    {analysisStep > 2 ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : analysisStep === 2 ? (
                      <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border border-slate-700" />
                    )}
                    <div>
                      <div className="text-xs font-bold">2. LLM Business Enrich</div>
                      <div className="text-[11px] text-slate-400">Sinh tên nghiệp vụ VN</div>
                    </div>
                  </div>

                  <div
                    className={`p-4 rounded-xl border flex items-center gap-3 transition-all ${
                      analysisStep >= 3
                        ? 'bg-indigo-950/40 border-indigo-500/50 text-indigo-300'
                        : 'bg-slate-900/40 border-slate-800 text-slate-400'
                    }`}
                  >
                    {analysisStep === 4 ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : analysisStep === 3 ? (
                      <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border border-slate-700" />
                    )}
                    <div>
                      <div className="text-xs font-bold">3. Metric Suggestions</div>
                      <div className="text-[11px] text-slate-400">Đề xuất chỉ số kinh doanh</div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Section 2: Semantic Layers List */}
          <div className="glass-card rounded-2xl p-6 md:p-8 border border-indigo-500/20 shadow-xl">
            <div className="flex items-center justify-between pb-4 mb-6 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-purple-600/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
                  <FolderKanban className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">
                    📂 DANH SÁCH SEMANTIC LAYERS
                  </h2>
                  <p className="text-xs text-slate-400">
                    Các Layer đang được quản trị, tinh chỉnh HITL và sẵn sàng Export
                  </p>
                </div>
              </div>
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                {layers.length} Databases
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-xs font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-4">Database Name</th>
                    <th className="py-3 px-4">Loại DB</th>
                    <th className="py-3 px-4">Trạng Thái</th>
                    <th className="py-3 px-4">Quy Mô</th>
                    <th className="py-3 px-4">Cập Nhật</th>
                    <th className="py-3 px-4 text-right">Thao Tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {layers.map((layer) => (
                    <tr key={layer.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3.5 px-4 font-semibold text-slate-200">
                        <div className="flex items-center gap-2">
                          <Database className="w-4 h-4 text-indigo-400" />
                          <span>{layer.db_name}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                          {layer.db_type}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        {layer.status === 'Saved' ? (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full">
                            <CheckCircle2 className="w-3 h-3" /> Saved
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 rounded-full">
                            <Clock className="w-3 h-3" /> Draft
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-300">
                        <span>{layer.tables.length} bảng</span> • <span>{layer.metrics.length} metrics</span>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-400 font-mono">
                        {layer.updated_at}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            href={`/semantic/${layer.id}/review`}
                            className="gradient-btn px-3 py-1.5 text-xs font-semibold text-white rounded-lg flex items-center gap-1.5 shadow"
                          >
                            <ExternalLink className="w-3.5 h-3.5" /> [ Mở Review ]
                          </Link>
                          <button
                            onClick={() => handleDelete(layer.id)}
                            className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                            title="Xóa Layer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
      <footer className="py-6 border-t border-slate-800/60 text-center text-xs text-slate-500">
        © 2026 AI Semantic Layer Agent. All rights reserved. Managed with JWT & Google Auth.
      </footer>
    </div>
  );
}
