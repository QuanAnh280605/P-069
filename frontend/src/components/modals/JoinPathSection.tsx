'use client';

import { useEffect, useMemo, useState } from 'react';

import {
  getMetricJoinPathOptionsApi,
  MetricJoinPathOptions,
  SemanticCatalog,
} from '@/lib/api';
import { JoinPathSelector } from '@/components/modals/JoinPathSelector';

interface JoinPathSectionProps {
  dbId?: string | null;
  catalog?: SemanticCatalog | null;
  baseEntity: string;
  baseEntityId?: number | null;
  value: Record<string, number[]>;
  onChange: (next: Record<string, number[]>) => void;
  onStaleChange?: (targets: string[]) => void;
}

function resolveBaseEntityId(
  catalog: SemanticCatalog | null | undefined,
  baseEntity: string,
  baseEntityId?: number | null,
): number | null {
  if (baseEntityId) return baseEntityId;
  const table = catalog?.tables.find((t) => t.table_name === baseEntity);
  return table ? table.table_id : null;
}

function computeStaleTargets(
  options: MetricJoinPathOptions,
  preferred: Record<string, number[]>,
): string[] {
  if (!options || Object.keys(options).length === 0) return [];
  const stale: string[] = [];
  for (const target of Object.keys(preferred)) {
    const candidates = options[target];
    const selected = preferred[target];
    if (!candidates || candidates.length === 0) {
      stale.push(target);
      continue;
    }
    const valid = candidates.some(
      (c) =>
        Array.isArray(selected) &&
        c.relationship_ids.length === selected.length &&
        c.relationship_ids.every((id, i) => id === selected[i]),
    );
    if (!valid) stale.push(target);
  }
  return stale;
}

function useJoinOptions(dbId: string | null | undefined, baseEntityId: number | null) {
  const [options, setOptions] = useState<MetricJoinPathOptions>({});
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!dbId || baseEntityId == null) return;
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (!cancelled) setLoading(true);
    });
    getMetricJoinPathOptionsApi(dbId, baseEntityId)
      .then((opts) => {
        if (!cancelled) setOptions(opts);
      })
      .catch(() => {
        if (!cancelled) setOptions({});
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dbId, baseEntityId]);
  return { options, loading };
}

function useTargetLabels(catalog: SemanticCatalog | null | undefined): Record<string, string> {
  return useMemo(() => {
    const labels: Record<string, string> = {};
    if (catalog) {
      for (const table of catalog.tables) {
        labels[String(table.table_id)] = table.business_name || table.table_name;
      }
    }
    return labels;
  }, [catalog]);
}

function StalePathsAlert({ onClear }: { onClear: () => void }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive"
    >
      <p>
        Một số ngữ cảnh quan hệ đã lưu không còn hợp lệ (quan hệ có thể đã bị xoá hoặc thay đổi).
        Vui lòng chọn lại trước khi lưu.
      </p>
      <button
        type="button"
        onClick={onClear}
        className="mt-1.5 rounded border border-destructive/40 px-2 py-0.5 font-medium hover:bg-destructive/20"
      >
        Xoá lựa chọn không hợp lệ
      </button>
    </div>
  );
}

export function JoinPathSection({
  dbId,
  catalog,
  baseEntity,
  baseEntityId,
  value,
  onChange,
  onStaleChange,
}: JoinPathSectionProps) {
  const resolvedId = resolveBaseEntityId(catalog, baseEntity, baseEntityId);
  const { options, loading } = useJoinOptions(dbId, resolvedId);
  const effectiveOptions = useMemo(
    () => (dbId && resolvedId != null ? options : {}),
    [dbId, resolvedId, options],
  );
  const staleTargets = useMemo(
    () => computeStaleTargets(effectiveOptions, value),
    [effectiveOptions, value],
  );
  const targetLabels = useTargetLabels(catalog);
  useEffect(() => {
    onStaleChange?.(staleTargets);
  }, [staleTargets, onStaleChange]);
  if (!dbId) return null;
  return (
    <div className="space-y-2">
      {loading && <p className="text-[11px] text-muted-foreground">Đang tải ngữ cảnh quan hệ…</p>}
      {staleTargets.length > 0 && (
        <StalePathsAlert
          onClear={() => {
            const next = { ...value };
            for (const target of staleTargets) delete next[target];
            onChange(next);
          }}
        />
      )}
      <JoinPathSelector
        options={effectiveOptions}
        value={value}
        onChange={onChange}
        targetLabels={targetLabels}
        staleTargets={staleTargets}
      />
    </div>
  );
}
