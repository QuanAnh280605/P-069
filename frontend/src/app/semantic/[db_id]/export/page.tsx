'use client';

import React, { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { getLayerById, SemanticLayerData } from '@/lib/api';
import {
  ArrowLeft,
  Download,
  Copy,
  Check,
  FileCode,
  FileText,
  Share2,
  Database,
} from 'lucide-react';

import { useAuth } from '@/context/AuthContext';

export default function ExportPage({ params }: { params: Promise<{ db_id: string }> }) {
  const resolvedParams = use(params);
  const { user, isLoading } = useAuth();
  const [layer, setLayer] = useState<SemanticLayerData | null>(null);
  const [exportFormat, setExportFormat] = useState<'json' | 'yaml'>('json');
  const [copied, setCopied] = useState(false);

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
          Vui lòng đăng nhập để xem và xuất Semantic Layer.
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

  // Generate JSON string
  const jsonOutput = JSON.stringify(
    {
      db_name: layer.db_name,
      db_type: layer.db_type,
      generated_at: new Date().toISOString(),
      tables: layer.tables,
      metrics: layer.metrics,
    },
    null,
    2
  );

  // Generate simple YAML representation
  const yamlOutput = `db_name: "${layer.db_name}"
db_type: "${layer.db_type}"
generated_at: "${new Date().toISOString()}"

tables:
${layer.tables
  .map(
    (t) => `  - name: "${t.table_name}"
    business_name: "${t.business_name}"
    description: "${t.description}"
    columns:
${t.columns
  .map(
    (c) => `      - name: "${c.column_name}"
        data_type: "${c.data_type}"
        business_name: "${c.business_name}"`
  )
  .join('\n')}`
  )
  .join('\n\n')}

metrics:
${layer.metrics
  .map(
    (m) => `  - name: "${m.name}"
    source: "${m.source}"
    description: "${m.description}"
    sql_template: |
      ${m.sql_template.replace(/\n/g, '\n      ')}`
  )
  .join('\n\n')}`;

  const currentContent = exportFormat === 'json' ? jsonOutput : yamlOutput;

  const handleCopy = () => {
    navigator.clipboard.writeText(currentContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = (format: 'json' | 'yaml') => {
    const content = format === 'json' ? jsonOutput : yamlOutput;
    const blob = new Blob([content], {
      type: format === 'json' ? 'application/json' : 'text/yaml',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `semantic_layer_${layer.db_name.toLowerCase().replace(/\s+/g, '_')}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 animate-in fade-in">
      {/* Top Header */}
      <div className="glass-card rounded-2xl p-5 border border-indigo-500/20 shadow-xl flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href={`/semantic/${layer.id}/review`}
            className="p-2 rounded-xl bg-slate-900 border border-slate-700/80 text-slate-300 hover:text-white hover:border-indigo-500 transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">
              📤 EXPORT SEMANTIC LAYER: {layer.db_name}
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Xuất cấu hình Semantic Governance ra file định dạng chuẩn JSON / YAML
            </p>
          </div>
        </div>
      </div>

      {/* Format Selection Cards */}
      <div className="space-y-4">
        <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
          CHỌN ĐỊNH DẠNG XUẤT:
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* JSON Card */}
          <div
            onClick={() => setExportFormat('json')}
            className={`glass-card rounded-2xl p-6 border cursor-pointer transition-all ${
              exportFormat === 'json'
                ? 'border-indigo-500 bg-indigo-950/20 shadow-indigo-500/10'
                : 'border-slate-800 hover:border-slate-700/80'
            }`}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
                <FileCode className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">📄 JSON Format</h3>
                <p className="text-xs text-slate-400">Tương thích: REST API, Metabase, custom tools</p>
              </div>
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDownload('json');
              }}
              className="gradient-btn w-full mt-4 py-2.5 text-xs font-bold text-white rounded-xl shadow flex items-center justify-center gap-2"
            >
              <Download className="w-4 h-4" /> ⬇️ Tải về JSON
            </button>
          </div>

          {/* YAML Card */}
          <div
            onClick={() => setExportFormat('yaml')}
            className={`glass-card rounded-2xl p-6 border cursor-pointer transition-all ${
              exportFormat === 'yaml'
                ? 'border-indigo-500 bg-indigo-950/20 shadow-indigo-500/10'
                : 'border-slate-800 hover:border-slate-700/80'
            }`}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-600/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">📋 YAML Format</h3>
                <p className="text-xs text-slate-400">Tương thích: dbt, Looker Studio, Metabase</p>
              </div>
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDownload('yaml');
              }}
              className="gradient-btn w-full mt-4 py-2.5 text-xs font-bold text-white rounded-xl shadow flex items-center justify-center gap-2"
            >
              <Download className="w-4 h-4" /> ⬇️ Tải về YAML
            </button>
          </div>
        </div>
      </div>

      {/* Code Preview Container */}
      <div className="glass-card rounded-2xl p-6 border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            PREVIEW ({exportFormat.toUpperCase()}):
          </h3>

          <button
            onClick={handleCopy}
            className="px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-900 border border-slate-700 rounded-lg hover:text-white hover:border-indigo-500 flex items-center gap-1.5 transition-colors"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" /> Đã sao chép!
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" /> Copy Code
              </>
            )}
          </button>
        </div>

        <pre className="bg-slate-950 p-5 rounded-xl border border-indigo-500/20 font-mono text-xs text-emerald-400 max-h-[500px] overflow-y-auto whitespace-pre-wrap leading-relaxed">
          {currentContent}
        </pre>
      </div>
    </div>
  );
}
