'use client';

import { AlertTriangle, Check, CheckCircle2, ChevronRight, Loader2, ShieldAlert, Sparkles } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { type SchemaReviewRelationship, updateRelationshipReviewApi } from '@/lib/api';

/** One editable governance draft (business name + description). */
export type Draft = { business_name: string; description: string };
export type DraftMap = Record<string, Draft>;

/** Stable key for a relationship draft, kept distinct from table/column keys. */
export function relationshipKey(rel: SchemaReviewRelationship): string {
  return `r:${rel.relationship_id}`;
}

/** Badge showing whether a metadata row is officially stored or still in review. */
export function ReviewBadge({ status }: { status: 'pending_review' | 'approved' }) {
  const approved = status === 'approved';
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 font-mono text-[10px]',
        approved
          ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
          : 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400',
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', approved ? 'bg-emerald-500' : 'bg-amber-500')} />
      {approved ? 'Đã lưu chính thức' : 'Chờ review'}
    </span>
  );
}

/** Badge showing the independent technical-validity signal of a relationship. */
export function ValidityBadge({ status }: { status: string }) {
  const valid = status === 'valid';
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 font-mono text-[10px]',
        valid
          ? 'border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-400'
          : 'border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400',
      )}
    >
      {valid ? (
        <CheckCircle2 className="h-3 w-3 shrink-0" />
      ) : (
        <ShieldAlert className="h-3 w-3 shrink-0" />
      )}
      {valid ? 'Hợp lệ (kỹ thuật)' : 'Không hợp lệ (kỹ thuật)'}
    </span>
  );
}

/** Show the AI proposal only when it differs from the value the reviewer sees. */
export function AiSuggestion({
  suggestion,
  current,
  onAccept,
  disabled,
}: {
  suggestion?: string | null;
  current: string;
  onAccept: () => void;
  disabled?: boolean;
}) {
  if (!suggestion || suggestion === current) return null;
  return (
    <button
      type="button"
      onClick={onAccept}
      disabled={disabled}
      className="mt-1 inline-flex items-center gap-1.5 text-left font-mono text-[10px] text-muted-foreground transition-colors hover:text-primary disabled:opacity-50"
      title="Dùng đề xuất của AI"
    >
      <Sparkles className="h-3 w-3 shrink-0" />
      <span className="truncate">AI đề xuất: {suggestion}</span>
    </button>
  );
}

interface RowEditorProps {
  businessName: string;
  description: string;
  aiBusinessName?: string | null;
  disabled?: boolean;
  saving?: boolean;
  dirty?: boolean;
  onChange: (patch: { business_name?: string; description?: string }) => void;
  onSave: () => void;
}

/** Inline editor for one table, column or relationship row. */
export function RowEditor({
  businessName,
  description,
  aiBusinessName,
  disabled,
  saving,
  dirty,
  onChange,
  onSave,
}: RowEditorProps) {
  return (
    <div className="grid flex-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_auto]">
      <div className="min-w-0">
        <Input
          value={businessName}
          disabled={disabled}
          placeholder="Tên nghiệp vụ"
          aria-label="Tên nghiệp vụ"
          className="h-8 text-xs"
          onChange={(event) => onChange({ business_name: event.target.value })}
        />
        <AiSuggestion
          suggestion={aiBusinessName}
          current={businessName}
          disabled={disabled}
          onAccept={() => onChange({ business_name: aiBusinessName || '' })}
        />
      </div>
      <Input
        value={description}
        disabled={disabled}
        placeholder="Mô tả nghiệp vụ"
        aria-label="Mô tả nghiệp vụ"
        className="h-8 text-xs"
        onChange={(event) => onChange({ description: event.target.value })}
      />
      <Button
        size="sm"
        variant="outline"
        disabled={disabled || saving || !dirty}
        onClick={onSave}
        className="h-8 shrink-0 gap-1.5 text-[11px]"
      >
        {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
        Lưu
      </Button>
    </div>
  );
}

interface RelationshipReviewSectionProps {
  dbId?: number | null;
  relationships: SchemaReviewRelationship[];
  drafts: DraftMap;
  isDirty: (key: string) => boolean;
  patch: (key: string, value: Partial<Draft>) => void;
  savingKey: string | null;
  saveRow: (key: string, save: (draft: Draft) => Promise<unknown>) => void;
  approving: string | null;
  canManageSchema: boolean;
  canApproveSchema: boolean;
  onApproveRelationship: (relationshipId: number) => void;
}

function formatPath(rel: SchemaReviewRelationship): string {
  const pairs = rel.column_pairs.filter((pair) => pair.from_column_name || pair.to_column_name);
  if (pairs.length === 0) return `${rel.from_table_name} → ${rel.to_table_name}`;
  return pairs
    .map(
      (pair) =>
        `${rel.from_table_name}.${pair.from_column_name ?? '?'} → ${rel.to_table_name}.${pair.to_column_name ?? '?'}`,
    )
    .join('; ');
}

/** Bounded relationship review section extracted from {@link SchemaReviewView}. */
export function RelationshipReviewSection({
  dbId,
  relationships,
  drafts,
  isDirty,
  patch,
  savingKey,
  saveRow,
  approving,
  canManageSchema,
  canApproveSchema,
  onApproveRelationship,
}: RelationshipReviewSectionProps) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>(() =>
    Object.fromEntries(
      relationships.map((rel) => [rel.relationship_id, rel.review_status === 'pending_review']),
    ),
  );

  const pendingCount = relationships.filter((rel) => rel.review_status === 'pending_review').length;

  if (relationships.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-secondary p-4 text-xs text-muted-foreground">
        Chưa có quan hệ (relationship) nào được gợi ý.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="font-mono text-[11px] text-muted-foreground">
        {relationships.length} quan hệ · {pendingCount} chờ review
      </p>
      {relationships.map((rel) => {
        const key = relationshipKey(rel);
        const open = expanded[rel.relationship_id] ?? rel.review_status === 'pending_review';
        const valid = rel.validation_status === 'valid';
        const approved = rel.review_status === 'approved';
        const ambiguous = rel.ambiguous_target_groups.length > 0;
        return (
          <section key={key} className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() =>
                  setExpanded((current) => ({ ...current, [rel.relationship_id]: !open }))
                }
                className="flex min-w-0 items-center gap-2 text-left"
                aria-expanded={open}
                aria-label={`Mở rộng quan hệ ${rel.business_name || formatPath(rel)}`}
              >
                <ChevronRight
                  className={cn('h-4 w-4 shrink-0 transition-transform', open && 'rotate-90')}
                />
                <span className="truncate font-mono text-[13px] text-foreground">
                  {rel.business_name || formatPath(rel)}
                </span>
              </button>
              <ReviewBadge status={rel.review_status as 'pending_review' | 'approved'} />
              <ValidityBadge status={rel.validation_status} />
              {ambiguous && (
                <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="h-3 w-3 shrink-0" />
                  Không rõ ràng
                </span>
              )}
              <div className="ml-auto flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 gap-1.5 text-[11px]"
                  disabled={!canApproveSchema || approving !== null || !valid || (approved && valid)}
                  onClick={() => onApproveRelationship(rel.relationship_id)}
                >
                  {approving === String(rel.relationship_id) ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3" />
                  )}
                  Duyệt quan hệ này
                </Button>
              </div>
            </div>

            <div className="mt-3 flex items-start gap-3">
              <RowEditor
                businessName={drafts[key]?.business_name ?? ''}
                description={drafts[key]?.description ?? ''}
                aiBusinessName={rel.ai_business_name}
                disabled={!canManageSchema}
                saving={savingKey === key}
                dirty={isDirty(key)}
                onChange={(value) => patch(key, value)}
                onSave={() =>
                  saveRow(key, (draft) =>
                    updateRelationshipReviewApi(
                      String(dbId),
                      rel.relationship_id,
                      draft.business_name,
                      draft.description,
                    ),
                  )
                }
              />
            </div>

            {open && (
              <div className="mt-4 space-y-3 border-t border-border pt-3">
                <div>
                  <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                    Đường vật lý (FK)
                  </p>
                  <p className="break-words font-mono text-[11px] text-foreground">{formatPath(rel)}</p>
                </div>

                {ambiguous && (
                  <div
                    role="status"
                    aria-live="polite"
                    className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300"
                  >
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <p className="font-medium">
                        Có {rel.ambiguous_target_groups.length} nhóm đường join không rõ ràng cần phân
                        biệt trước khi duyệt:
                      </p>
                      <ul className="mt-1 list-disc space-y-1 pl-4">
                        {rel.ambiguous_target_groups.map((group, index) => (
                          <li key={index} className="font-mono text-[11px]">
                            Bảng đích #{group.target_entity_id}:{' '}
                            {group.candidate_relationship_ids
                              .map((path) => `[${path.join(' → ')}]`)
                              .join(' hoặc ')}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {!valid && (
                  <div
                    role="status"
                    aria-live="polite"
                    className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-700 dark:text-rose-400"
                  >
                    <ShieldAlert className="h-4 w-4 shrink-0" />
                    Quan hệ không hợp lệ về mặt kỹ thuật (validation_status=
                    <span className="font-mono">{rel.validation_status}</span>) nên không thể duyệt.
                  </div>
                )}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
