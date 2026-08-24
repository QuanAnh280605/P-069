'use client';

import { Check, GitCommitHorizontal, Plus, Save, Sparkles, Trash2, X } from 'lucide-react';
import { FormEvent, useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  FilterOperator,
  MetricDefinition,
  MetricFilter,
  MetricFunction,
  METRIC_WRITE_PERMISSION_MESSAGE,
  SemanticTable,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { StatusPill } from '@/components/workspace/shared';
import {
  coerceFilterValue,
  createMetricDefinition,
  renderMetricYaml,
  withPendingStatus,
} from '@/lib/metrics';

export interface MetricVersion {
  version: number;
  definition?: MetricDefinition | null;
  change_reason?: string;
  created_at?: string;
}

interface MetricModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (definition: MetricDefinition, changeReason?: string) => Promise<void> | void;
  tables: SemanticTable[];
  initialDefinition?: MetricDefinition | null;
  initialName?: string;
  status?: string;
  onApprove?: () => Promise<void> | void;
  versions?: MetricVersion[];
  canSave?: boolean;
  saveDisabledReason?: string;
  submissionMode?: boolean;
}

const FUNCTIONS: MetricFunction[] = ['SUM', 'COUNT', 'COUNT_DISTINCT', 'AVG', 'MIN', 'MAX'];
const OPERATORS: { label: string; value: FilterOperator }[] = [
  { label: '= (Bằng)', value: 'eq' },
  { label: '≠ (Khác)', value: 'neq' },
  { label: '> (Lớn hơn)', value: 'gt' },
  { label: '≥ (Lớn hơn hoặc bằng)', value: 'gte' },
  { label: '< (Nhỏ hơn)', value: 'lt' },
  { label: '≤ (Nhỏ hơn hoặc bằng)', value: 'lte' },
  { label: 'IN (Trong danh sách)', value: 'in' },
  { label: 'NOT IN (Ngoài danh sách)', value: 'not_in' },
  { label: 'IS NULL (Rỗng)', value: 'is_null' },
  { label: 'IS NOT NULL (Không rỗng)', value: 'is_not_null' },
];

type TabKey = 'definition' | 'history';

export function MetricModal(props: MetricModalProps) {
  const [definition, setDefinition] = useState<MetricDefinition>(createMetricDefinition());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<TabKey>('definition');
  const [changeReason, setChangeReason] = useState('');

  useEffect(() => {
    const base = props.tables[0]?.table_name || '';
    const next = props.initialDefinition || createMetricDefinition(base);
    setDefinition({
      metric: {
        ...next.metric,
        name: next.metric.name || props.initialName || '',
      },
    });
    setError('');
    setChangeReason('');
    setActiveTab('definition');
  }, [props.initialDefinition, props.initialName, props.isOpen, props.tables]);

  const columns = useMemo(
    () =>
      props.tables.find((table) => table.table_name === definition.metric.base_entity)?.columns ||
      [],
    [definition.metric.base_entity, props.tables],
  );

  const setMetric = (patch: Partial<MetricDefinition['metric']>) => {
    setDefinition((current) => ({ metric: { ...current.metric, ...patch } }));
  };

  // Editing a published metric never overwrites it: the backend stores a
  // copy-on-write draft and demands a reason for the audit trail.
  const requiresChangeReason =
    !props.submissionMode && (props.status || definition.metric.status) === 'approved';

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (props.canSave === false) {
      setError(props.saveDisabledReason || METRIC_WRITE_PERMISSION_MESSAGE);
      return;
    }
    const message = validateDefinition(definition);
    if (message) return setError(message);
    if (requiresChangeReason && !changeReason.trim()) {
      return setError('Chỉ số đã publish: vui lòng nhập lý do thay đổi để lưu vào lịch sử phiên bản.');
    }
    setSaving(true);
    setError('');
    try {
      await props.onSave(withPendingStatus(definition), changeReason);
      props.onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể lưu metric');
    } finally {
      setSaving(false);
    }
  };

  const status = props.submissionMode
    ? 'unverified'
    : props.status || definition.metric.status || 'pending_approval';
  const versions = props.versions || [];

  return (
    <Dialog open={props.isOpen} onOpenChange={(open) => !open && props.onClose()}>
      <DialogContent className="flex max-h-[88vh] flex-col overflow-hidden bg-background sm:max-w-3xl">
        <DialogHeader>
          <div className="flex flex-wrap items-center gap-3">
            <DialogTitle className="font-display text-2xl">
              {props.submissionMode ? 'Gửi Business Metric' : 'Định nghĩa Business Metric'}
            </DialogTitle>
            <StatusPill status={status} />
          </div>
          {definition.metric.name && (
            <p className="font-mono text-[11px] text-muted-foreground">
              {definition.metric.name} · {definition.metric.base_entity}
            </p>
          )}
        </DialogHeader>

        {/* Tab Controls */}
        <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1 self-start">
          {[
            { key: 'definition' as TabKey, label: 'Definition' },
            {
              key: 'history' as TabKey,
              label: `Version history (${versions.length})`,
            },
          ].map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'rounded-md px-3 py-1.5 text-xs transition-colors cursor-pointer',
                activeTab === tab.key
                  ? 'bg-primary text-primary-foreground font-semibold'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {activeTab === 'definition' ? (
            <form onSubmit={submit} className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-3.5">
                <div>
                  <Label htmlFor="metric-name" className="mb-1.5 block text-xs font-medium">
                    Tên metric
                  </Label>
                  <Input
                    id="metric-name"
                    required
                    value={definition.metric.name}
                    onChange={(e) => setMetric({ name: e.target.value })}
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="mb-1.5 block text-xs font-medium">Base entity</Label>
                    <select
                      value={definition.metric.base_entity}
                      onChange={(e) => setMetric({ base_entity: e.target.value, filters: [] })}
                      className="h-9 w-full rounded-md border border-border bg-transparent px-2.5 text-xs outline-none focus:ring-1 focus:ring-ring"
                    >
                      {props.tables.map((t) => (
                        <option key={t.table_name} value={t.table_name}>
                          {t.business_name || t.table_name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <Label className="mb-1.5 block text-xs font-medium">Hàm tổng hợp</Label>
                    <select
                      value={definition.metric.formula.function}
                      onChange={(e) =>
                        setMetric({
                          formula: {
                            ...definition.metric.formula,
                            function: e.target.value as MetricFunction,
                          },
                        })
                      }
                      className="h-9 w-full rounded-md border border-border bg-transparent px-2.5 text-xs font-mono outline-none focus:ring-1 focus:ring-ring"
                    >
                      {FUNCTIONS.map((f) => (
                        <option key={f} value={f}>
                          {f}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <Label className="mb-1.5 block text-xs font-medium">Biểu thức công thức</Label>
                  <Input
                    required
                    list="metric-columns"
                    value={definition.metric.formula.expression}
                    onChange={(e) =>
                      setMetric({
                        formula: {
                          ...definition.metric.formula,
                          expression: e.target.value,
                        },
                      })
                    }
                    placeholder="quantity * unit_price"
                    className="font-mono text-xs"
                  />
                  <datalist id="metric-columns">
                    {columns.map((c) => (
                      <option key={c.column_name} value={c.column_name} />
                    ))}
                  </datalist>
                </div>

                <div>
                  <Label className="mb-1.5 block text-xs font-medium">Ghi chú loại trừ</Label>
                  <textarea
                    rows={2}
                    value={definition.metric.excluded_notes || ''}
                    onChange={(e) => setMetric({ excluded_notes: e.target.value })}
                    className="w-full rounded-md border border-border bg-transparent p-2 text-xs outline-none focus:ring-1 focus:ring-ring"
                    placeholder="Ví dụ: Chưa trừ hoàn tiền, chỉ tính đơn completed"
                  />
                </div>

                <FilterEditor
                  filters={definition.metric.filters}
                  columns={columns.map((c) => c.column_name)}
                  onChange={(filters) => setMetric({ filters })}
                />

                {requiresChangeReason && (
                  <div>
                    <Label className="mb-1.5 block text-xs font-medium">
                      Lý do thay đổi <span className="text-destructive">*</span>
                    </Label>
                    <textarea
                      rows={2}
                      value={changeReason}
                      onChange={(e) => setChangeReason(e.target.value)}
                      className="w-full rounded-md border border-border bg-transparent p-2 text-xs outline-none focus:ring-1 focus:ring-ring"
                      placeholder="VD: Cập nhật công thức theo policy mới..."
                    />
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      Chỉ số đang publish sẽ giữ nguyên. Bản sửa được lưu thành phiên bản mới chờ
                      phê duyệt.
                    </p>
                  </div>
                )}

                {error && (
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive">
                    {error}
                  </div>
                )}
                {props.canSave === false && !error && (
                  <div
                    role="alert"
                    className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300"
                  >
                    {props.saveDisabledReason || METRIC_WRITE_PERMISSION_MESSAGE}
                  </div>
                )}
                {props.submissionMode && !error && (
                  <div
                    role="status"
                    className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300"
                  >
                    Metric sẽ có trạng thái Chưa được xác minh sau khi gửi.
                  </div>
                )}
              </div>

              {/* YAML Spec Preview Column */}
              <div className="flex flex-col space-y-2">
                <span className="font-mono text-[11px] text-muted-foreground">
                  Preview chỉ đọc (YAML spec):
                </span>
                <div className="flex-1 overflow-hidden rounded-lg border border-border bg-card">
                  <pre className="max-h-[380px] overflow-auto p-3 font-mono text-xs leading-relaxed text-foreground">
                    {renderMetricYaml(withPendingStatus(definition))}
                  </pre>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="flex items-center justify-between gap-2 border-t border-border pt-4 lg:col-span-2">
                <div>
                  {!props.submissionMode && status !== 'approved' && props.onApprove && (
                    <Button
                      type="button"
                      variant="secondary"
                      className="gap-1.5 text-xs"
                      onClick={() => void props.onApprove?.()}
                    >
                      <Check className="h-4 w-4" />
                      Phê duyệt metric
                    </Button>
                  )}
                  {status === 'approved' && (
                    <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-emerald-500">
                      <Check className="h-3.5 w-3.5" />
                      Đã có trong Semantic Layer
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <Button type="button" variant="ghost" onClick={props.onClose}>
                    Hủy
                  </Button>
                  <Button
                    type="submit"
                    disabled={saving || props.canSave === false}
                    title={
                      props.canSave === false
                        ? props.saveDisabledReason || METRIC_WRITE_PERMISSION_MESSAGE
                        : undefined
                    }
                    className="gap-1.5 text-xs"
                  >
                    <Save className="h-3.5 w-3.5" />
                    {saving
                      ? props.submissionMode
                        ? 'Đang gửi...'
                        : 'Đang lưu...'
                      : props.submissionMode
                        ? 'Gửi metric'
                        : 'Lưu metric'}
                  </Button>
                </div>
              </div>
            </form>
          ) : (
            <div className="p-4">
              {versions.length === 0 ? (
                <p className="text-xs text-muted-foreground italic text-center py-6">
                  Chưa có lịch sử phiên bản.
                </p>
              ) : (
                <ol className="relative space-y-4 border-l border-border pl-6">
                  {versions.map((v, i) => (
                    <li key={v.version} className="relative">
                      <span className="absolute -left-[27px] flex h-4 w-4 items-center justify-center rounded-full border border-border bg-background">
                        <GitCommitHorizontal className="h-3 w-3 text-muted-foreground" />
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-foreground">
                          Version {v.version}
                        </span>
                        {i === 0 && (
                          <span className="rounded-full bg-secondary px-2 py-0.5 font-mono text-[10px] text-secondary-foreground">
                            current
                          </span>
                        )}
                      </div>
                      {v.change_reason && (
                        <p className="mt-0.5 text-sm text-foreground">{v.change_reason}</p>
                      )}
                      {v.created_at && (
                        <p className="font-mono text-[11px] text-muted-foreground">
                          {new Date(v.created_at).toLocaleString()}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FilterEditor({
  filters,
  columns,
  onChange,
}: {
  filters: MetricFilter[];
  columns: string[];
  onChange: (filters: MetricFilter[]) => void;
}) {
  const update = (index: number, patch: Partial<MetricFilter>) =>
    onChange(
      filters.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs font-medium">Bộ lọc cố định</Label>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() =>
            onChange([...filters, { field: columns[0] || '', operator: 'eq', value: '' }])
          }
          className="h-6 gap-1 text-[11px] text-primary"
        >
          <Plus className="h-3 w-3" />
          Thêm
        </Button>
      </div>
      {filters.map((filter, index) => (
        <div key={index} className="flex items-center gap-1.5 text-xs">
          <select
            value={filter.field}
            onChange={(e) => update(index, { field: e.target.value })}
            className="h-8 flex-1 rounded border border-border bg-background px-2 text-xs outline-none"
          >
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            value={filter.operator}
            onChange={(e) =>
              update(index, {
                operator: e.target.value as FilterOperator,
                value: null,
              })
            }
            className="h-8 w-24 rounded border border-border bg-background px-1 text-xs outline-none"
          >
            {OPERATORS.map((op) => (
              <option key={op.value} value={op.value}>
                {op.label}
              </option>
            ))}
          </select>
          <Input
            disabled={filter.operator.startsWith('is_')}
            value={displayValue(filter.value)}
            onChange={(e) =>
              update(index, {
                value: coerceFilterValue(filter.operator, e.target.value),
              })
            }
            className="h-8 flex-1 px-2 text-xs"
          />
          <button
            type="button"
            onClick={() => onChange(filters.filter((_, i) => i !== index))}
            className="rounded p-1 text-muted-foreground hover:text-destructive cursor-pointer"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}

function displayValue(value: unknown): string {
  return Array.isArray(value) ? value.join(', ') : value == null ? '' : String(value);
}

function validateDefinition(definition: MetricDefinition): string {
  const metric = definition.metric;
  if (!metric.name.trim() || !metric.base_entity || !metric.formula.expression.trim()) {
    return 'Tên, base entity và biểu thức là bắt buộc.';
  }
  if (metric.formula.expression === '*' && metric.formula.function !== 'COUNT') {
    return 'Chỉ COUNT được phép dùng biểu thức *.';
  }
  if (metric.filters.some((item) => !item.field)) {
    return 'Mỗi bộ lọc phải chọn một cột.';
  }
  return '';
}
