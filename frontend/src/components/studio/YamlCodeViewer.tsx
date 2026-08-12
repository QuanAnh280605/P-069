'use client';

import { Check, Copy } from 'lucide-react';
import { useState } from 'react';

interface YamlCodeViewerProps {
  yaml: string;
  title?: string;
}

export function YamlCodeViewer({ yaml, title = 'Metric definition (YAML)' }: YamlCodeViewerProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(yaml);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className='overflow-hidden rounded-xl border border-slate-700 bg-slate-950'>
      <div className='flex items-center justify-between border-b border-slate-800 px-3 py-2'>
        <span className='text-[11px] font-semibold text-slate-300'>{title}</span>
        <button type='button' onClick={copy} className='flex items-center gap-1 text-[11px] text-slate-400 hover:text-white'>
          {copied ? <Check className='h-3.5 w-3.5 text-emerald-400' /> : <Copy className='h-3.5 w-3.5' />}
          {copied ? 'Đã sao chép' : 'Sao chép'}
        </button>
      </div>
      <pre className='max-h-80 overflow-auto whitespace-pre-wrap p-3 font-mono text-xs leading-5 text-emerald-300'>{yaml}</pre>
    </div>
  );
}
