'use client';

import React, { useState } from 'react';
import { SemanticLayerData } from '@/lib/api';
import { Share2, Download, Copy, Check, FileCode, Layers } from 'lucide-react';

interface ExportPlaygroundViewProps {
  layer: SemanticLayerData;
  theme: 'light' | 'dark';
}

export const ExportPlaygroundView: React.FC<ExportPlaygroundViewProps> = ({ layer, theme }) => {
  const [format, setFormat] = useState<'cube' | 'dbt' | 'json'>('cube');
  const [copied, setCopied] = useState(false);

  // Generate Cube.js JS Schema format
  const generateCubeSchema = (): string => {
    return `// Cube.js Universal Semantic Layer Data Models
// Generated for Database: ${layer.db_name} (${layer.db_type})

${layer.tables
  .map(
    (t) => `cube('${t.table_name.charAt(0).toUpperCase() + t.table_name.slice(1)}', {
  sql: \`SELECT * FROM public.${t.table_name}\`,
  title: '${t.business_name}',
  description: '${t.description}',

  dimensions: {
${t.columns
  .filter((c) => !c.data_type.toUpperCase().includes('NUMERIC') && !c.data_type.toUpperCase().includes('INT'))
  .map(
    (c) => `    ${c.column_name}: {
      sql: \`${c.column_name}\`,
      type: 'string',
      title: '${c.business_name}'
    }`
  )
  .join(',\n')}
  },

  measures: {
    count: {
      type: 'count',
      title: 'Số lượng bản ghi'
    }
  }
});`
  )
  .join('\n\n')}

// Business Metrics Defined:
${layer.metrics
  .map(
    (m) => `// Metric: ${m.name}
// Description: ${m.description}
// SQL: ${m.sql_template}`
  )
  .join('\n\n')}`;
  };

  // Generate dbt Semantic Layer YAML format
  const generateDbtYaml = (): string => {
    return `version: 2

semantic_models:
${layer.tables
  .map(
    (t) => `  - name: ${t.table_name}
    description: "${t.business_name} - ${t.description}"
    model: ref('${t.table_name}')
    defaults:
      agg_time_dimension: created_at

    entities:
      - name: ${t.table_name}_id
        type: primary

    measures:
${layer.metrics
  .map(
    (m) => `      - name: ${m.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}
        description: "${m.description}"
        expr: "${m.sql_template.replace(/\n/g, ' ')}"
        agg: sum`
  )
  .join('\n')}`
  )
  .join('\n')}
`;
  };

  // Generate JSON format
  const generateJson = (): string => {
    return JSON.stringify(
      {
        db_name: layer.db_name,
        db_type: layer.db_type,
        status: layer.status,
        generated_at: new Date().toISOString(),
        tables: layer.tables,
        metrics: layer.metrics,
      },
      null,
      2
    );
  };

  const getActiveCode = () => {
    switch (format) {
      case 'cube':
        return generateCubeSchema();
      case 'dbt':
        return generateDbtYaml();
      case 'json':
        return generateJson();
    }
  };

  const activeCode = getActiveCode();

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(activeCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  const handleDownload = () => {
    const ext = format === 'cube' ? 'js' : format === 'dbt' ? 'yml' : 'json';
    const blob = new Blob([activeCode], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `semantic_layer_${layer.db_name}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 animate-in fade-in">
      {/* Top Header */}
      <div
        className={`p-4 rounded-2xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
          theme === 'light'
            ? 'bg-white border-slate-200 shadow-2xs'
            : 'bg-slate-900/60 border-slate-800 shadow-lg'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-purple-50 dark:bg-purple-950/60 border border-purple-200 dark:border-purple-800 text-purple-600 dark:text-purple-400 flex items-center justify-center">
            <Share2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-tight">Semantic Layer Export & Integrations</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Xuất mô hình dữ liệu sang Cube.js Schema, dbt Semantic Layer YAML hoặc JSON chuẩn hóa
            </p>
          </div>
        </div>

        {/* Format Selector Pills */}
        <div className="flex items-center gap-2">
          <div className="flex items-center p-1 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <button
              onClick={() => setFormat('cube')}
              className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                format === 'cube'
                  ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs font-bold'
                  : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              Cube.js Schema
            </button>
            <button
              onClick={() => setFormat('dbt')}
              className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                format === 'dbt'
                  ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs font-bold'
                  : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              dbt YAML
            </button>
            <button
              onClick={() => setFormat('json')}
              className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                format === 'json'
                  ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs font-bold'
                  : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              JSON Schema
            </button>
          </div>

          <button
            onClick={handleCopy}
            className="px-3.5 py-1.5 text-xs font-bold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 transition-all cursor-pointer inline-flex items-center gap-1.5 shadow-2xs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Đã sao chép' : 'Copy'}</span>
          </button>

          <button
            onClick={handleDownload}
            className="px-3.5 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-all cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Tải file</span>
          </button>
        </div>
      </div>

      {/* Code Editor Container */}
      <div
        className={`rounded-2xl border p-4 font-mono text-xs overflow-x-auto leading-relaxed shadow-sm ${
          theme === 'light'
            ? 'bg-white border-slate-200 text-slate-800'
            : 'bg-slate-950 border-slate-800 text-slate-200'
        }`}
      >
        <pre className="whitespace-pre overflow-x-auto select-text">{activeCode}</pre>
      </div>
    </div>
  );
};
