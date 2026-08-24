'use client';

import { AlertCircle, Check, CheckCircle2, ChevronRight, Loader2, Sparkles } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  approveSchemaReviewApi,
  getSchemaReviewApi,
  updateColumnReviewApi,
  updateTableReviewApi,
  type SchemaReview,
  type SchemaReviewColumn,
  type SchemaReviewTable,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { SectionLabel, type WorkspaceDatabase } from '@/components/workspace/shared';
import { ViewHeader } from '@/components/workspace/ViewHeader';

interface SchemaReviewViewProps {
  dbId?: number | null;
  database?: WorkspaceDatabase | null;
  canManageSchema?: boolean;
  canApproveSchema?: boolean;
  onNotify?: (message: string) => void;
  onReviewChanged?: () => void;
}

/** Badge showing whether a metadata row is officially stored or still in review. */
function ReviewBadge({ status }: { status: 'pending_review' | 'approved' }) {
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

/** Show the AI proposal only when it differs from the value the reviewer sees. */
function AiSuggestion({
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

/** Inline editor for one table or column row. */
function RowEditor({
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

type Draft = { business_name: string; description: string };
type DraftMap = Record<string, Draft>;

function tableKey(table: SchemaReviewTable): string {
  return `t:${table.table_name}`;
}

function columnKey(table: SchemaReviewTable, column: SchemaReviewColumn): string {
  return `c:${table.table_name}:${column.column_name}`;
}

function buildDrafts(review: SchemaReview): DraftMap {
  const drafts: DraftMap = {};
  for (const table of review.tables) {
    drafts[tableKey(table)] = {
      business_name: table.business_name || '',
      description: table.description || '',
    };
    for (const column of table.columns) {
      drafts[columnKey(table, column)] = {
        business_name: column.business_name || '',
        description: column.description || '',
      };
    }
  }
  return drafts;
}

export function SchemaReviewView({
  dbId,
  database,
  canManageSchema = false,
  canApproveSchema = false,
  onNotify,
  onReviewChanged,
}: SchemaReviewViewProps) {
  const [review, setReview] = useState<SchemaReview | null>(null);
  const [drafts, setDrafts] = useState<DraftMap>({});
  const [baseline, setBaseline] = useState<DraftMap>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!dbId) return;
    setLoading(true);
    setError('');
    try {
      const data = await getSchemaReviewApi(String(dbId));
      setReview(data);
      const next = buildDrafts(data);
      setDrafts(next);
      setBaseline(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể tải hàng đợi review');
    } finally {
      setLoading(false);
    }
  }, [dbId]);

  useEffect(() => {
    void load();
  }, [load]);

  const isDirty = (key: string) =>
    drafts[key] !== undefined &&
    (drafts[key].business_name !== baseline[key]?.business_name ||
      drafts[key].description !== baseline[key]?.description);

  const patch = (key: string, value: Partial<Draft>) =>
    setDrafts((current) => ({ ...current, [key]: { ...current[key], ...value } }));

  const saveRow = async (key: string, save: (draft: Draft) => Promise<unknown>) => {
    const draft = drafts[key];
    if (!dbId || !draft) return;
    setSavingKey(key);
    setError('');
    try {
      await save(draft);
      setBaseline((current) => ({ ...current, [key]: { ...draft } }));
      onNotify?.('Đã lưu bản chỉnh sửa, chờ phê duyệt');
      await load();
      onReviewChanged?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể lưu chỉnh sửa');
    } finally {
      setSavingKey(null);
    }
  };

  const approve = async (tableNames?: string[]) => {
    if (!dbId) return;
    setApproving(tableNames?.[0] ?? '*');
    setError('');
    try {
      const result = await approveSchemaReviewApi(String(dbId), tableNames);
      onNotify?.(
        `Đã duyệt ${result.approved_tables} bảng và ${result.approved_columns} cột vào Metadata Store`,
      );
      await load();
      onReviewChanged?.();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể phê duyệt schema');
    } finally {
      setApproving(null);
    }
  };

  const pendingTotal = (review?.pending_tables || 0) + (review?.pending_columns || 0);
  const dirtyCount = useMemo(
    () => Object.keys(drafts).filter((key) => isDirty(key)).length,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [drafts, baseline],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-background">
      <ViewHeader
        eyebrow="Flow 1 · HITL Review"
        title="Schema Review"
        description="Tên nghiệp vụ do AI đề xuất chỉ được lưu chính thức vào Metadata Store sau khi BA/DA chỉnh sửa và phê duyệt."
        database={database}
        actions={
          <Button
            size="sm"
            disabled={!canApproveSchema || pendingTotal === 0 || approving !== null}
            onClick={() => approve()}
            className="gap-2 text-xs"
          >
            {approving === '*' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            Duyệt toàn bộ ({pendingTotal})
          </Button>
        }
      />

      <div className="flex flex-col gap-4 p-4 sm:p-6">
        {!canManageSchema && (
          <p className="rounded-lg border border-border bg-secondary p-3 text-xs text-muted-foreground">
            Bạn chỉ có quyền xem hàng đợi review. Liên hệ Data Lead để chỉnh sửa hoặc phê duyệt.
          </p>
        )}
        {error && (
          <p className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </p>
        )}
        {dirtyCount > 0 && (
          <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
            {dirtyCount} chỉnh sửa chưa được lưu. Nhấn Lưu trên từng dòng trước khi phê duyệt.
          </p>
        )}

        <div className="flex items-center gap-4">
          <SectionLabel>
            {review?.tables.length || 0} bảng · {review?.pending_tables || 0} bảng chờ ·{' '}
            {review?.pending_columns || 0} cột chờ
          </SectionLabel>
          {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
        </div>

        {review?.tables.length === 0 && !loading && (
          <p className="rounded-lg border border-border bg-secondary p-4 text-xs text-muted-foreground">
            Chưa có metadata nào. Hãy chạy Generate ở AI Studio để tạo Semantic Layer trước.
          </p>
        )}

        {review?.tables.map((table) => {
          const key = tableKey(table);
          const open = expanded[table.table_name] ?? table.review_status === 'pending_review';
          const pendingColumns = table.columns.filter((c) => c.review_status === 'pending_review').length;
          return (
            <section
              key={table.table_name}
              className="rounded-xl border border-border bg-card p-4 shadow-sm"
            >
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setExpanded((current) => ({ ...current, [table.table_name]: !open }))
                  }
                  className="flex min-w-0 items-center gap-2 text-left"
                  aria-expanded={open}
                >
                  <ChevronRight
                    className={cn('h-4 w-4 shrink-0 transition-transform', open && 'rotate-90')}
                  />
                  <span className="truncate font-mono text-[13px] text-foreground">
                    {table.table_name}
                  </span>
                </button>
                <ReviewBadge status={table.review_status} />
                {pendingColumns > 0 && (
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {pendingColumns}/{table.columns.length} cột chờ
                  </span>
                )}
                {table.reviewed_at && (
                  <span className="font-mono text-[10px] text-muted-foreground">
                    Duyệt lúc {new Date(table.reviewed_at).toLocaleString()}
                  </span>
                )}
                <div className="ml-auto flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 gap-1.5 text-[11px]"
                    disabled={
                      !canApproveSchema ||
                      approving !== null ||
                      (table.review_status === 'approved' && pendingColumns === 0)
                    }
                    onClick={() => approve([table.table_name])}
                  >
                    {approving === table.table_name ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-3 w-3" />
                    )}
                    Duyệt bảng này
                  </Button>
                </div>
              </div>

              <div className="mt-3 flex items-start gap-3">
                <RowEditor
                  businessName={drafts[key]?.business_name ?? ''}
                  description={drafts[key]?.description ?? ''}
                  aiBusinessName={table.ai_business_name}
                  disabled={!canManageSchema}
                  saving={savingKey === key}
                  dirty={isDirty(key)}
                  onChange={(value) => patch(key, value)}
                  onSave={() =>
                    saveRow(key, (draft) =>
                      updateTableReviewApi(
                        String(dbId),
                        table.table_name,
                        draft.business_name,
                        draft.description,
                      ),
                    )
                  }
                />
              </div>

              {open && (
                <div className="mt-4 space-y-3 border-t border-border pt-3">
                  {table.columns.map((column) => {
                    const colKey = columnKey(table, column);
                    return (
                      <div key={column.column_name} className="flex flex-col gap-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate font-mono text-[11px] text-muted-foreground">
                            {column.column_name}
                            <span className="ml-1.5 opacity-60">{column.data_type}</span>
                          </span>
                          {column.is_primary_key && (
                            <span className="rounded bg-secondary px-1.5 font-mono text-[9px] text-secondary-foreground">
                              PK
                            </span>
                          )}
                          <ReviewBadge status={column.review_status} />
                        </div>
                        <RowEditor
                          businessName={drafts[colKey]?.business_name ?? ''}
                          description={drafts[colKey]?.description ?? ''}
                          aiBusinessName={column.ai_business_name}
                          disabled={!canManageSchema}
                          saving={savingKey === colKey}
                          dirty={isDirty(colKey)}
                          onChange={(value) => patch(colKey, value)}
                          onSave={() =>
                            saveRow(colKey, (draft) =>
                              updateColumnReviewApi(
                                String(dbId),
                                table.table_name,
                                column.column_name,
                                draft.business_name,
                                draft.description,
                              ),
                            )
                          }
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
