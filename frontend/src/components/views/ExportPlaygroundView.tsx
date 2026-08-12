'use client';

import { Copy, Download, Loader2, Share2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { exportSemanticLayerApi } from '@/lib/api';

interface ExportPlaygroundViewProps {
  dbId?: number | null;
}

export function ExportPlaygroundView({ dbId }: ExportPlaygroundViewProps) {
  const [format, setFormat] = useState<'json' | 'yaml'>('yaml');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!dbId) return;
    setLoading(true);
    setError('');
    exportSemanticLayerApi(String(dbId), format).then(setContent).catch((caught) => setError(caught instanceof Error ? caught.message : 'Không thể export')).finally(() => setLoading(false));
  }, [dbId, format]);

  const copy = async () => { await navigator.clipboard.writeText(content); setCopied(true); window.setTimeout(() => setCopied(false), 1500); };
  const download = () => {
    const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = `semantic-layer.${format === 'yaml' ? 'yaml' : 'json'}`; anchor.click(); URL.revokeObjectURL(url);
  };

  return <div className='space-y-4'><header className='flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900'><div><h2 className='flex items-center gap-2 text-sm font-bold'><Share2 className='h-5 w-5 text-purple-500' />Semantic Layer Export</h2><p className='mt-1 text-xs text-slate-500'>Nội dung do backend tạo; chỉ metric đã approved được export.</p></div><div className='flex gap-2'><select value={format} onChange={(event) => setFormat(event.target.value as 'json' | 'yaml')} className='form-input'><option value='yaml'>YAML</option><option value='json'>JSON</option></select><button onClick={() => void copy()} disabled={!content} className='rounded-xl border px-3 py-2 text-xs'><Copy className='mr-1 inline h-4 w-4' />{copied ? 'Đã sao chép' : 'Copy'}</button><button onClick={download} disabled={!content} className='rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white'><Download className='mr-1 inline h-4 w-4' />Tải file</button></div></header>{loading ? <p className='p-10 text-center text-sm'><Loader2 className='mr-2 inline h-5 w-5 animate-spin' />Đang tải export...</p> : error ? <p className='rounded-xl bg-red-50 p-4 text-sm text-red-700'>{error}</p> : <pre className='overflow-auto whitespace-pre rounded-2xl border border-slate-800 bg-slate-950 p-4 text-xs leading-5 text-emerald-300'>{content}</pre>}</div>;
}
