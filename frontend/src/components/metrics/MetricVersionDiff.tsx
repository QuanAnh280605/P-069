'use client';

import { useMemo } from 'react';

import type { MetricDefinition } from '@/lib/api';
import { buildMetricVersionDiff, DiffRow, DiffRowStatus } from '@/lib/metric-version-diff';
import { cn } from '@/lib/utils';

interface MetricVersionDiffProps {
  previousDefinition: MetricDefinition | null | undefined;
  currentDefinition: MetricDefinition | null | undefined;
}

const rowStyles: Record<DiffRowStatus, string> = {
  removed: 'bg-red-500/10 text-red-600 dark:text-red-400',
  added: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  unchanged: 'text-muted-foreground',
};

const rowMarkers: Record<DiffRowStatus, string> = {
  removed: '−',
  added: '+',
  unchanged: '',
};

export function MetricVersionDiff({
  previousDefinition,
  currentDefinition,
}: MetricVersionDiffProps) {
  const result = useMemo(
    () => buildMetricVersionDiff(previousDefinition, currentDefinition),
    [previousDefinition, currentDefinition],
  );

  if (!result.available) {
    return (
      <p className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-600 dark:text-amber-400">
        Không thể so sánh: một trong hai phiên bản là bản legacy không có definition.
      </p>
    );
  }

  const formulaLines = collectFormulaLines(previousDefinition, currentDefinition);

  return (
    <div className="overflow-hidden rounded-md border border-border">
      <ul data-testid="metric-version-diff" className="divide-y divide-border font-mono text-xs">
        {result.rows.map((row, index) => (
          <DiffLine key={`${index}-${row.text}`} row={row} isFormula={formulaLines.has(row.text)} />
        ))}
      </ul>
    </div>
  );
}

function DiffLine({ row, isFormula }: { row: DiffRow; isFormula: boolean }) {
  return (
    <li
      data-status={row.status}
      className={cn('flex items-start gap-2 px-3 py-1.5', rowStyles[row.status])}
    >
      <span aria-hidden="true" className="w-3 shrink-0 select-none text-center">
        {rowMarkers[row.status]}
      </span>
      <span className="shrink-0 rounded border border-border bg-background/60 px-1 font-sans text-[10px] uppercase tracking-wide">
        {isFormula ? 'Công thức' : 'Bộ lọc'}
      </span>
      <span className="break-all">{row.text}</span>
    </li>
  );
}

function collectFormulaLines(
  previous: MetricDefinition | null | undefined,
  current: MetricDefinition | null | undefined,
): Set<string> {
  const lines = new Set<string>();
  if (previous?.metric?.formula) {
    lines.add(`${previous.metric.formula.function}(${previous.metric.formula.expression})`);
  }
  if (current?.metric?.formula) {
    lines.add(`${current.metric.formula.function}(${current.metric.formula.expression})`);
  }
  return lines;
}
