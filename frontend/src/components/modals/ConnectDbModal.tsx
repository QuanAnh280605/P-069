'use client';

import React, { useState } from 'react';
import { X, Database, Upload, PlusCircle, Loader2, FileText, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { getStoredToken } from '@/lib/jwt';
import { connectLiveTargetDb, uploadSqlDumpPreview, saveImportedSchema, updateLayer, convertRawSchemaToLayer } from '@/lib/api';

interface ConnectDbModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newDbName: string, dbId?: string) => void;
}

export const ConnectDbModal: React.FC<ConnectDbModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<'live' | 'dump'>('live');

  // Live DB Form State
  const [dbName, setDbName] = useState('');
  const [dbType, setDbType] = useState<'auto' | 'postgresql' | 'mysql' | 'sqlite'>('auto');
  const [connUrl, setConnUrl] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [liveDbError, setLiveDbError] = useState('');

  // SQL Dump Form State
  const [file, setFile] = useState<File | null>(null);
  const [dumpDialect, setDumpDialect] = useState<'' | 'postgresql' | 'mysql'>('');
  const [dumpDisplayName, setDumpDisplayName] = useState('');
  const [isDumpProcessing, setIsDumpProcessing] = useState(false);
  const [dumpError, setDumpError] = useState('');

  if (!isOpen) return null;

  const handleConnectLiveDb = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dbName.trim() || !connUrl.trim()) return;

    setIsAnalyzing(true);
    setLiveDbError('');
    const accessToken = token || getStoredToken();

    if (!accessToken) {
      setLiveDbError('Vui lòng đăng nhập để lưu kết nối an toàn trên backend.');
      setIsAnalyzing(false);
      return;
    }

    if (accessToken) {
      try {
        const liveRecord = await connectLiveTargetDb(dbName.trim(), dbType, connUrl.trim(), accessToken);
        const newLayer = convertRawSchemaToLayer(
          liveRecord.id,
          liveRecord.display_name || dbName.trim(),
          liveRecord.dialect || dbType,
          liveRecord.raw_schema,
          undefined,
          liveRecord.updated_at,
          liveRecord.semantic_db_id,
          'live',
        );
        updateLayer(newLayer);
        setIsAnalyzing(false);
        onSuccess(dbName.trim(), newLayer.id);
        onClose();
        return;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Kết nối và trích xuất schema thất bại';
        setLiveDbError(msg);
        setIsAnalyzing(false);
        return;
      }
    }

    /* Offline / Guest Fallback removed: backend is authoritative.
    setTimeout(() => {
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
              { column_name: 'total_amount', data_type: 'NUMERIC', business_name: 'Tổng tiền', sample_value: '500,000' },
              { column_name: 'order_status', data_type: 'VARCHAR(20)', business_name: 'Trạng thái đơn', sample_value: 'COMPLETED' },
              { column_name: 'created_at', data_type: 'TIMESTAMP', business_name: 'Ngày tạo đơn', sample_value: '2026-08-01' },
            ],
          },
          {
            table_name: 'products',
            business_name: 'Sản phẩm',
            description: 'Bảng danh mục sản phẩm kinh doanh',
            columns: [
              { column_name: 'product_id', data_type: 'INTEGER (PK)', business_name: 'Mã sản phẩm', sample_value: 'P-10' },
              { column_name: 'product_name', data_type: 'VARCHAR(100)', business_name: 'Tên sản phẩm', sample_value: 'Laptop Pro 15' },
              { column_name: 'unit_price', data_type: 'NUMERIC', business_name: 'Đơn giá', sample_value: '25,000,000' },
            ],
          },
        ],
        metrics: [
          {
            id: `m_${Date.now()}_1`,
            name: 'Tổng doanh thu bán hàng',
            description: 'Tổng tiền các đơn hàng đã hoàn thành (COMPLETED)',
            sql_template: `SELECT SUM(total_amount) FROM orders WHERE order_status = 'COMPLETED'`,
            source: 'ai',
          },
        ],
      };

      updateLayer(newLayer);
      setIsAnalyzing(false);
      onSuccess(dbName.trim(), newId);
      onClose();
    }, 600);
  };

    */
  };

  const handleUploadDump = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIsDumpProcessing(true);
    setDumpError('');
    const accessToken = token || getStoredToken();

    if (!accessToken) {
      setDumpError('Vui lòng đăng nhập để lưu schema trên backend.');
      setIsDumpProcessing(false);
      return;
    }

    if (accessToken) {
      try {
        const preview = await uploadSqlDumpPreview(file, dumpDialect, accessToken);
        const name = dumpDisplayName.trim() || file.name.replace(/\.sql$/i, '');
        const savedRecord = await saveImportedSchema(name, preview, accessToken);
        const newLayer = convertRawSchemaToLayer(
          savedRecord.id,
          savedRecord.display_name || name,
          savedRecord.dialect || dumpDialect || 'postgresql',
          savedRecord.raw_schema,
          undefined,
          savedRecord.updated_at,
          savedRecord.semantic_db_id,
          'sql_dump',
        );
        updateLayer(newLayer);
        setIsDumpProcessing(false);
        onSuccess(name, newLayer.id);
        onClose();
        return;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Không thể đọc hoặc lưu file SQL dump';
        setDumpError(msg);
        setIsDumpProcessing(false);
        return;
      }
    }

    /* Offline / Guest Fallback removed: backend is authoritative.
    setTimeout(() => {
      const name = dumpDisplayName.trim() || file.name.replace(/\.sql$/i, '');
      const newId = `dump-${Date.now()}`;
      const newLayer: SemanticLayerData = {
        id: newId,
        db_name: name,
        db_type: dumpDialect || 'postgresql',
        status: 'Draft',
        updated_at: new Date().toISOString().replace('T', ' ').slice(0, 16),
        tables: [
          {
            table_name: 'imported_table',
            business_name: 'Bảng nhập từ SQL Dump',
            description: 'Bảng dữ liệu trích xuất từ DDL Schema file',
            columns: [
              { column_name: 'id', data_type: 'INTEGER (PK)', business_name: 'Mã định danh', sample_value: '1' },
              { column_name: 'title', data_type: 'VARCHAR(200)', business_name: 'Tiêu đề', sample_value: 'Sample Title' },
            ],
          },
        ],
        metrics: [],
      };
      updateLayer(newLayer);
      setIsDumpProcessing(false);
      onSuccess(name, newId);
      onClose();
    }, 600);
  };

    */
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 dark:bg-slate-950/75 backdrop-blur-sm animate-in fade-in">
      <div className="glass-card w-full max-w-xl rounded-2xl border border-slate-200 dark:border-indigo-500/30 shadow-2xl overflow-hidden bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/90 dark:bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-600/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center border border-indigo-200 dark:border-indigo-500/30">
              <PlusCircle className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">Thêm Kết Nối Database Mới</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Introspect Schema & Khởi tạo Semantic Layer</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 dark:hover:text-white p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 bg-slate-100/80 dark:bg-slate-950/40 p-1">
          <button
            onClick={() => setActiveTab('live')}
            className={`flex-1 py-2.5 text-xs font-bold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 ${
              activeTab === 'live'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs border border-slate-200/80 dark:border-slate-800'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800/40'
            }`}
          >
            <Database className="w-4 h-4" />
            <span>1. Kết nối Live Database URL</span>
          </button>
          <button
            onClick={() => setActiveTab('dump')}
            className={`flex-1 py-2.5 text-xs font-bold rounded-xl transition-all cursor-pointer flex items-center justify-center gap-2 ${
              activeTab === 'dump'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs border border-slate-200/80 dark:border-slate-800'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800/40'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>2. Import SQL Dump File (.sql)</span>
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6">
          {activeTab === 'live' ? (
            <form onSubmit={handleConnectLiveDb} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                  Tên gợi nhớ Database
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. E-Commerce Production DB"
                  value={dbName}
                  onChange={(e) => setDbName(e.target.value)}
                  className="w-full bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                  Dialect Override
                </label>
                <select
                  value={dbType}
                  onChange={(e) => setDbType(e.target.value as 'auto' | 'postgresql' | 'mysql' | 'sqlite')}
                  className="w-full bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 cursor-pointer"
                >
                  <option value="auto" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">Auto Detect</option>
                  <option value="postgresql" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">PostgreSQL</option>
                  <option value="mysql" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">MySQL</option>
                  <option value="sqlite" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">SQLite</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                  Chuỗi Kết Nối (Connection URL)
                </label>
                <input
                  type="text"
                  required
                  placeholder="postgresql+asyncpg://user:pass@localhost:5432/ecommerce_db"
                  value={connUrl}
                  onChange={(e) => setConnUrl(e.target.value)}
                  className="w-full bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-4 py-2.5 text-xs font-mono text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600"
                />
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1.5 flex items-center gap-1">
                  🔒 Chuỗi URL được mã hóa Fernet an toàn và chỉ dùng SQLAlchemy Inspector đọc metadata.
                </p>
              </div>

              {liveDbError && (
                <div className="p-3 rounded-xl border border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10 text-xs text-red-600 dark:text-red-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{liveDbError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={isAnalyzing}
                  className="gradient-btn px-5 py-2.5 text-xs font-bold text-white rounded-xl shadow-md flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Đang Phân Tích...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Bắt Đầu Kết Nối & Introspect</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleUploadDump} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                  Tên gợi nhớ Schema
                </label>
                <input
                  type="text"
                  placeholder="Ví dụ: Schema bán hàng tháng 8"
                  value={dumpDisplayName}
                  onChange={(e) => setDumpDisplayName(e.target.value)}
                  className="w-full bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-400 dark:placeholder:text-slate-600"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                  Chọn File .SQL Dump
                </label>
                <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-900/80 transition-colors">
                  <FileText className="h-5 w-5 text-cyan-600 dark:text-cyan-400 shrink-0" />
                  <span className="truncate text-xs text-slate-700 dark:text-slate-300">
                    {file?.name || 'Chọn file SQL schema DDL (.sql)...'}
                  </span>
                  <input
                    type="file"
                    accept=".sql,application/sql,text/plain"
                    className="sr-only"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                </label>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                  Dialect Override
                </label>
                <select
                  value={dumpDialect}
                  onChange={(e) => setDumpDialect(e.target.value as '' | 'postgresql' | 'mysql')}
                  className="w-full bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 cursor-pointer"
                >
                  <option value="" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">Auto Detect</option>
                  <option value="postgresql" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">PostgreSQL</option>
                  <option value="mysql" className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">MySQL</option>
                </select>
              </div>

              {dumpError && (
                <div className="p-3 rounded-xl border border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10 text-xs text-red-600 dark:text-red-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{dumpError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={!file || isDumpProcessing}
                  className="gradient-btn px-5 py-2.5 text-xs font-bold text-white rounded-xl shadow-md flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {isDumpProcessing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Đang Xử Lý File...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      <span>Upload & Parse Schema</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
