'use client';

import { useMemo } from 'react';

import { cn } from '@/lib/utils';
import { JoinPathOption, MetricJoinPathOptions } from '@/lib/api';

interface JoinPathSelectorProps {
  /** Safe governed join-path options keyed by target entity id. */
  options: MetricJoinPathOptions;
  /** Currently selected preferred path per target entity id. */
  value: Record<string, number[]>;
  onChange: (next: Record<string, number[]>) => void;
  /** Friendly target table names keyed by target entity id. */
  targetLabels?: Record<string, string>;
  /** Targets whose stored selection no longer matches any current option. */
  staleTargets?: string[];
}

function candidateMatches(candidate: JoinPathOption, selected: number[] | undefined): boolean {
  if (!selected || candidate.relationship_ids.length !== selected.length) return false;
  return candidate.relationship_ids.every((id, i) => id === selected[i]);
}

/**
 * Renders the governed "Ngữ cảnh quan hệ" selection for a metric's base entity.
 *
 * Only targets reachable through more than one safe governed path are shown,
 * because a single safe path is deterministic and needs no human choice. Each
 * candidate is presented by its reviewed business labels/descriptions rather
 * than raw relationship ids; the chosen ordered relationship-id sequence is
 * persisted via {@link JoinPathSelectorProps.onChange}.
 */
export function JoinPathSelector({
  options,
  value,
  onChange,
  targetLabels,
  staleTargets,
}: JoinPathSelectorProps) {
  const ambiguousTargets = useMemo(
    () => Object.keys(options).filter((target) => (options[target]?.length ?? 0) > 1),
    [options],
  );

  if (ambiguousTargets.length === 0) return null;

  const staleSet = new Set(staleTargets ?? []);

  const select = (target: string, relationshipIds: number[]) => {
    onChange({ ...value, [target]: relationshipIds });
  };

  return (
    <div className="space-y-4" data-testid="join-path-selector">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-foreground">
          Ngữ cảnh quan hệ
        </span>
        <span className="text-[10px] text-muted-foreground">
          Chọn đường dẫn join được duyệt cho các bảng có nhiều hơn 1 quan hệ an toàn
        </span>
      </div>

      {ambiguousTargets.map((target) => {
        const candidates = options[target];
        const selected = value[target];
        const isStale = staleSet.has(target) && !candidates.some((c) => candidateMatches(c, selected));
        const targetLabel = targetLabels?.[target] || `bảng (entity ${target})`;

        return (
          <fieldset key={target} className="space-y-2 rounded-lg border border-border bg-card/40 p-3">
            <legend className="px-1 text-xs font-medium text-foreground">{targetLabel}</legend>
            {isStale && (
              <p
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-[11px] text-destructive"
              >
                Lựa chọn đã lưu không còn hợp lệ (quan hệ có thể đã thay đổi). Vui lòng chọn lại đường
                dẫn bên dưới.
              </p>
            )}
            <div className="space-y-1.5">
              {candidates.map((candidate, index) => {
                const checked = candidateMatches(candidate, selected);
                const pathLabel = candidate.labels.join(' → ') || `Đường dẫn ${index + 1}`;
                const description = candidate.descriptions
                  .filter((d): d is string => Boolean(d))
                  .join(' · ');
                return (
                  <label
                    key={index}
                    className={cn(
                      'flex cursor-pointer items-start gap-2 rounded-md border p-2 text-xs transition-colors',
                      checked
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/60 hover:bg-accent/40',
                    )}
                  >
                    <input
                      type="radio"
                      name={`join-path-${target}`}
                      checked={checked}
                      onChange={() => select(target, candidate.relationship_ids)}
                      className="mt-0.5 h-3.5 w-3.5 accent-primary"
                    />
                    <span className="flex-1">
                      <span className="block font-medium text-foreground">{pathLabel}</span>
                      {description && (
                        <span className="mt-0.5 block text-[11px] text-muted-foreground">
                          {description}
                        </span>
                      )}
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        );
      })}
    </div>
  );
}
