'use client';

import { Check, Save } from 'lucide-react';
import { FormEvent, useEffect } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  MetricDefinition,
  MetricFunction,
  METRIC_WRITE_PERMISSION_MESSAGE,
  SemanticCatalog,
  SemanticTable,
} from '@/lib/api';
import { FilterEditor } from '@/components/modals/FilterEditor';
import { TabKey } from '@/components/modals/MetricModalShell';
import { createMetricDefinition, renderMetricYaml, withPendingStatus } from '@/lib/metrics';

const FUNCTIONS: MetricFunction[] = ['SUM', 'COUNT', 'COUNT_DISTINCT', 'AVG', 'MIN', 'MAX'];

interface MetricModalFormProps {
  metric: MetricDefinition['metric'];
  setMetric: (patch: Partial<MetricDefinition['metric']>) => void;
  setPreferredPaths: (next: Record<string, number[]>) => void;
  tables: SemanticTable[];
  dbId?: string | null;
  catalog?: SemanticCatalog | null;
  requiresChangeReason: boolean;
  changeReason: string;
  setChangeReason: (value: string) => void;
  error: string;
  canSave?: boolean;
  saveDisabledReason?: string;
  submissionMode?: boolean;
  isMemberRequest?: boolean;
  status: string;
  onApprove?: () => Promise<void> | void;
  onClose: () => void;
  saving: boolean;
  submit: (event: FormEvent) => void;
  staleTargets: string[];
  onStaleChange: (targets: string[]) => void;
}

function useMetricModalReset(
  props: {
    tables: SemanticTable[];
    initialDefinition?: MetricDefinition | null;
    initialName?: string;
    isOpen: boolean;
  },
  setDefinition: (value: MetricDefinition) => void,
  setError: (value: string) => void,
  setChangeReason: (value: string) => void,
  setActiveTab: (value: TabKey) => void,
): void {
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
  }, [props.initialDefinition, props.initialName, props.isOpen, props.tables, setDefinition, setError, setChangeReason, setActiveTab]);
}

function MetricNameField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div>
      <Label htmlFor="metric-name" className="mb-1.5 block text-xs font-medium">
        Tên metric
      </Label>
      <Input id="metric-name" required value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function BaseEntitySelect({
  value,
  onChange,
  tables,
}: {
  value: string;
  onChange: (value: string) => void;
  tables: SemanticTable[];
}) {
  return (
    <div>
      <Label className="mb-1.5 block text-xs font-medium">Base entity</Label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-md border border-border bg-card text-foreground px-2.5 text-xs outline-none focus:ring-1 focus:ring-ring dark:bg-zinc-900 dark:text-zinc-100 [&>option]:bg-white [&>option]:text-zinc-900 dark:[&>option]:bg-zinc-900 dark:[&>option]:text-zinc-100"
      >
        {tables.map((t) => (
          <option
            key={t.table_name}
            value={t.table_name}
            className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100"
          >
            {t.business_name || t.table_name}
          </option>
        ))}
      </select>
    </div>
  );
}

function FunctionSelect({
  value,
  onChange,
}: {
  value: MetricFunction;
  onChange: (value: MetricFunction) => void;
}) {
  return (
    <div>
      <Label className="mb-1.5 block text-xs font-medium">Hàm tổng hợp</Label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as MetricFunction)}
        className="h-9 w-full rounded-md border border-border bg-card text-foreground px-2.5 text-xs font-mono outline-none focus:ring-1 focus:ring-ring dark:bg-zinc-900 dark:text-zinc-100 [&>option]:bg-white [&>option]:text-zinc-900 dark:[&>option]:bg-zinc-900 dark:[&>option]:text-zinc-100"
      >
        {FUNCTIONS.map((f) => (
          <option key={f} value={f} className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100">
            {f}
          </option>
        ))}
      </select>
    </div>
  );
}

function ExpressionField({
  value,
  onChange,
  columns,
}: {
  value: string;
  onChange: (value: string) => void;
  columns: string[];
}) {
  return (
    <div>
      <Label className="mb-1.5 block text-xs font-medium">Biểu thức công thức</Label>
      <Input
        required
        list="metric-columns"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="quantity * unit_price"
        className="font-mono text-xs"
      />
      <datalist id="metric-columns">
        {columns.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
    </div>
  );
}

function ExcludedNotesField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <Label className="mb-1.5 block text-xs font-medium">Ghi chú loại trừ</Label>
      <textarea
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-border bg-transparent p-2 text-xs outline-none focus:ring-1 focus:ring-ring"
        placeholder="Ví dụ: Chưa trừ hoàn tiền, chỉ tính đơn completed"
      />
    </div>
  );
}

function ChangeReasonField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <Label className="mb-1.5 block text-xs font-medium">
        Lý do thay đổi <span className="text-destructive">*</span>
      </Label>
      <textarea
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-border bg-transparent p-2 text-xs outline-none focus:ring-1 focus:ring-ring"
        placeholder="VD: Cập nhật công thức theo policy mới..."
      />
      <p className="mt-1 text-[11px] text-muted-foreground">
        Chỉ số đang publish sẽ giữ nguyên. Bản sửa được lưu thành phiên bản mới chờ phê duyệt.
      </p>
    </div>
  );
}

function ModalAlerts({
  error,
  canSave,
  saveDisabledReason,
  submissionMode,
}: {
  error: string;
  canSave?: boolean;
  saveDisabledReason?: string;
  submissionMode?: boolean;
}) {
  if (!error && !(canSave === false) && !submissionMode) return null;
  return (
    <div className="space-y-2">
      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-xs text-destructive">
          {error}
        </div>
      )}
      {canSave === false && !error && (
        <div
          role="alert"
          className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300"
        >
          {saveDisabledReason || METRIC_WRITE_PERMISSION_MESSAGE}
        </div>
      )}
      {submissionMode && !error && (
        <div
          role="status"
          className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300"
        >
          Metric sẽ có trạng thái Chưa được xác minh sau khi gửi.
        </div>
      )}
    </div>
  );
}

function YamlPreview({ definition }: { definition: MetricDefinition }) {
  return (
    <div className="flex flex-col space-y-2">
      <span className="font-mono text-[11px] text-muted-foreground">Preview chỉ đọc (YAML spec):</span>
      <div className="flex-1 overflow-hidden rounded-lg border border-border bg-card">
        <pre className="max-h-[380px] overflow-auto p-3 font-mono text-xs leading-relaxed text-foreground">
          {renderMetricYaml(withPendingStatus(definition))}
        </pre>
      </div>
    </div>
  );
}

function ModalFooter({
  saving,
  submissionMode,
  isMemberRequest,
  canSave,
  saveDisabledReason,
  status,
  onApprove,
  onClose,
}: {
  saving: boolean;
  submissionMode?: boolean;
  isMemberRequest?: boolean;
  canSave?: boolean;
  saveDisabledReason?: string;
  status: string;
  onApprove?: () => Promise<void> | void;
  onClose: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 border-t border-border pt-4 lg:col-span-2">
      <div>
        {!submissionMode && status !== 'approved' && onApprove && (
          <Button
            type="button"
            variant="secondary"
            className="gap-1.5 text-xs"
            onClick={() => void onApprove()}
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
        <Button type="button" variant="ghost" onClick={onClose}>
          Hủy
        </Button>
        <Button
          type="submit"
          disabled={saving || canSave === false}
          title={canSave === false ? saveDisabledReason || METRIC_WRITE_PERMISSION_MESSAGE : undefined}
          className="gap-1.5 text-xs"
        >
          <Save className="h-3.5 w-3.5" />
          {saving
            ? isMemberRequest
              ? 'Đang duyệt & tạo...'
              : submissionMode
                ? 'Đang gửi...'
                : 'Đang lưu...'
            : isMemberRequest
              ? 'Duyệt & tạo metric'
              : submissionMode
                ? 'Gửi metric'
                : 'Lưu metric'}
        </Button>
      </div>
    </div>
  );
}

function MetricFormLeftColumn(props: MetricModalFormProps) {
  const { metric, setMetric, tables, requiresChangeReason, changeReason, setChangeReason, error, canSave, saveDisabledReason, submissionMode } = props;
  const columns = tables.find((t) => t.table_name === metric.base_entity)?.columns || [];
  const columnNames = columns.map((c) => c.column_name);
  return (
    <div className="space-y-3.5">
      <MetricNameField value={metric.name} onChange={(v) => setMetric({ name: v })} />
      <div className="grid grid-cols-2 gap-2">
        <BaseEntitySelect
          value={metric.base_entity}
          onChange={(v) => setMetric({ base_entity: v, filters: [] })}
          tables={tables}
        />
        <FunctionSelect
          value={metric.formula.function}
          onChange={(v) => setMetric({ formula: { ...metric.formula, function: v } })}
        />
      </div>
      {!props.isMemberRequest && (
        <ExpressionField
          value={metric.formula.expression}
          onChange={(v) => setMetric({ formula: { ...metric.formula, expression: v } })}
          columns={columnNames}
        />
      )}
      <ExcludedNotesField
        value={metric.excluded_notes || ''}
        onChange={(v) => setMetric({ excluded_notes: v })}
      />
      <FilterEditor filters={metric.filters} columns={columnNames} onChange={(filters) => setMetric({ filters })} />
      {requiresChangeReason && <ChangeReasonField value={changeReason} onChange={setChangeReason} />}
      <ModalAlerts
        error={error}
        canSave={canSave}
        saveDisabledReason={saveDisabledReason}
        submissionMode={submissionMode}
      />
    </div>
  );
}

function MetricDefinitionForm(props: MetricModalFormProps) {
  return (
    <form onSubmit={props.submit} className="grid gap-5 lg:grid-cols-2">
      <MetricFormLeftColumn {...props} />
      <YamlPreview definition={{ metric: props.metric }} />
      <ModalFooter
        saving={props.saving}
        submissionMode={props.submissionMode}
        isMemberRequest={props.isMemberRequest}
        canSave={props.canSave}
        saveDisabledReason={props.saveDisabledReason}
        status={props.status}
        onApprove={props.onApprove}
        onClose={props.onClose}
      />
    </form>
  );
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

export type { MetricModalFormProps };
export { useMetricModalReset, validateDefinition, MetricDefinitionForm };
