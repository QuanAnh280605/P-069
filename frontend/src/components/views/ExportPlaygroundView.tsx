'use client';

import { Check, Copy, Download, FileJson, FileText, Loader2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { exportSemanticLayerApi, MetricRecord } from '@/lib/api';
import { cn } from '@/lib/utils';
import { SectionLabel, type WorkspaceDatabase } from '@/components/workspace/shared';
import { ViewHeader } from '@/components/workspace/ViewHeader';

interface ExportPlaygroundViewProps {
  dbId?: number | null;
  metrics?: MetricRecord[];
  database?: WorkspaceDatabase | null;
}

export function ExportPlaygroundView({ dbId, metrics = [], database }: ExportPlaygroundViewProps) {
  const [format, setFormat] = useState<'json' | 'yaml'>('yaml');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!dbId) return;
    setLoading(true);
    setError('');
    exportSemanticLayerApi(String(dbId), format)
      .then(setContent)
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Không thể export'))
      .finally(() => setLoading(false));
  }, [dbId, format]);

  const copy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const download = () => {
    const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `semantic-layer.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const approvedMetrics = useMemo(
    () => metrics.filter((m) => m.status === 'approved'),
    [metrics],
  );

  const stats = [
    { label: 'Approved metrics', value: approvedMetrics.length || (content ? '✓' : 0) },
    {
      label: 'Source tables',
      value: new Set(approvedMetrics.map((m) => m.definition?.metric?.base_entity).filter(Boolean))
        .size || (content ? 1 : 0),
    },
    {
      label: 'Format',
      value: format.toUpperCase(),
    },
  ];

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background text-foreground">
      <ViewHeader
        eyebrow="Publish"
        title="Export Playground"
        description="Publish the approved semantic layer to a standard spec for BI tools and semantic engines."
        database={database}
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 text-xs"
              onClick={() => void copy()}
              disabled={!content}
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Đã sao chép' : 'Copy'}
            </Button>
            <Button
              size="sm"
              className="gap-1.5 text-xs"
              onClick={download}
              disabled={!content}
            >
              <Download className="h-3.5 w-3.5" />
              Tải file
            </Button>
          </div>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        <div className="mx-auto flex max-w-5xl flex-col gap-4">
          {/* Summary Stat Cards */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {stats.map((s, i) => (
              <div
                key={s.label}
                className="ws-reveal relative overflow-hidden rounded-lg border border-border bg-card p-4 transition-colors hover:border-foreground/25 shadow-2xs"
                style={{ animationDelay: `${i * 70}ms` }}
              >
                <div
                  className="ws-hatch-bg pointer-events-none absolute -right-4 -top-4 h-16 w-16 opacity-40"
                  aria-hidden
                />
                <p className="relative font-display text-4xl leading-none text-card-foreground tabular-nums">
                  {s.value}
                </p>
                <p className="relative mt-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                  {s.label}
                </p>
              </div>
            ))}
          </div>

          {/* Output Code Block */}
          {loading ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <p className="text-xs">Đang tải export...</p>
            </div>
          ) : error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-xs text-destructive">
              {error}
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-border bg-card shadow-xs">
              <div className="flex items-center justify-between border-b border-border bg-secondary/30 px-4 py-2.5">
                <SectionLabel>semantic_layer.{format}</SectionLabel>
                <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
                  {([
                    { key: 'yaml' as const, label: 'YAML', icon: FileText },
                    { key: 'json' as const, label: 'JSON', icon: FileJson },
                  ]).map((f) => {
                    const Icon = f.icon;
                    return (
                      <button
                        key={f.key}
                        type="button"
                        onClick={() => setFormat(f.key)}
                        className={cn(
                          'flex items-center gap-1.5 rounded-md px-3 py-1 text-xs transition-colors cursor-pointer',
                          format === f.key
                            ? 'bg-primary text-primary-foreground'
                            : 'text-muted-foreground hover:text-foreground',
                        )}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        <span>{f.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <pre className="max-h-[52vh] overflow-auto p-4 font-mono text-xs leading-relaxed text-foreground">
                {content || '# Không có dữ liệu để export'}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
