'use client';

import { Plus, Save, Sparkles, Trash2, X } from 'lucide-react';
import { FormEvent, useEffect, useMemo, useState } from 'react';

import {
  FilterOperator,
  MetricDefinition,
  MetricFilter,
  MetricFunction,
  SemanticTable,
} from '@/lib/api';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { coerceFilterValue, createMetricDefinition, renderMetricYaml, withPendingStatus } from '@/lib/metrics';

interface MetricModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (definition: MetricDefinition) => Promise<void> | void;
  tables: SemanticTable[];
  initialDefinition?: MetricDefinition | null;
  initialName?: string;
}

const FUNCTIONS: MetricFunction[] = ['SUM', 'COUNT', 'COUNT_DISTINCT', 'AVG', 'MIN', 'MAX'];
const OPERATORS: FilterOperator[] = ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in', 'is_null', 'is_not_null'];

export function MetricModal(props: MetricModalProps) {
  const [definition, setDefinition] = useState<MetricDefinition>(createMetricDefinition());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const base = props.tables[0]?.table_name || '';
    const next = props.initialDefinition || createMetricDefinition(base);
    setDefinition({ metric: { ...next.metric, name: next.metric.name || props.initialName || '' } });
    setError('');
  }, [props.initialDefinition, props.initialName, props.isOpen, props.tables]);

  const columns = useMemo(
    () => props.tables.find((table) => table.table_name === definition.metric.base_entity)?.columns || [],
    [definition.metric.base_entity, props.tables],
  );

  if (!props.isOpen) return null;

  const setMetric = (patch: Partial<MetricDefinition['metric']>) => {
    setDefinition((current) => ({ metric: { ...current.metric, ...patch } }));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const message = validateDefinition(definition);
    if (message) return setError(message);
    setSaving(true);
    setError('');
    try {
      await props.onSave(withPendingStatus(definition));
      props.onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể lưu metric');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm'>
      <div className='max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-indigo-500/30 bg-white shadow-2xl dark:bg-slate-900'>
        <header className='sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4 dark:border-slate-800 dark:bg-slate-900'>
          <h3 className='flex items-center gap-2 font-bold'><Sparkles className='h-4 w-4 text-indigo-500' /> Định nghĩa Business Metric</h3>
          <button type='button' onClick={props.onClose}><X className='h-5 w-5' /></button>
        </header>
        <form onSubmit={submit} className='grid gap-6 p-6 lg:grid-cols-2'>
          <div className='space-y-4'>
            <Field label='Tên metric'>
              <input required value={definition.metric.name} onChange={(event) => setMetric({ name: event.target.value })} className='form-input' />
            </Field>
            <div className='grid grid-cols-2 gap-3'>
              <Field label='Base entity'>
                <select value={definition.metric.base_entity} onChange={(event) => setMetric({ base_entity: event.target.value, filters: [] })} className='form-input'>
                  {props.tables.map((table) => <option key={table.table_name} value={table.table_name}>{table.business_name} ({table.table_name})</option>)}
                </select>
              </Field>
              <Field label='Hàm tổng hợp'>
                <select value={definition.metric.formula.function} onChange={(event) => setMetric({ formula: { ...definition.metric.formula, function: event.target.value as MetricFunction } })} className='form-input'>
                  {FUNCTIONS.map((item) => <option key={item}>{item}</option>)}
                </select>
              </Field>
            </div>
            <Field label='Biểu thức công thức'>
              <input required list='metric-columns' value={definition.metric.formula.expression} onChange={(event) => setMetric({ formula: { ...definition.metric.formula, expression: event.target.value } })} placeholder='quantity * unit_price' className='form-input font-mono' />
              <datalist id='metric-columns'>{columns.map((column) => <option key={column.column_name} value={column.column_name} />)}</datalist>
            </Field>
            <Field label='Độ tin cậy'>
              <select value={definition.metric.confidence || ''} onChange={(event) => setMetric({ confidence: (event.target.value || null) as MetricDefinition['metric']['confidence'] })} className='form-input'>
                <option value=''>Không xác định</option><option value='high'>Cao</option><option value='medium'>Trung bình</option><option value='low'>Thấp</option>
              </select>
            </Field>
            <Field label='Ghi chú loại trừ'>
              <textarea rows={3} value={definition.metric.excluded_notes} onChange={(event) => setMetric({ excluded_notes: event.target.value })} className='form-input' placeholder='Ví dụ: Chưa trừ hoàn tiền, chưa trừ giảm giá' />
            </Field>
            <FilterEditor filters={definition.metric.filters} columns={columns.map((item) => item.column_name)} onChange={(filters) => setMetric({ filters })} />
            {error && <p className='rounded-lg bg-red-50 p-3 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300'>{error}</p>}
          </div>
          <div className='space-y-3'>
            <p className='text-xs text-slate-500'>Preview chỉ đọc; dữ liệu được lưu vào database dưới dạng JSON.</p>
            <YamlCodeViewer yaml={renderMetricYaml(withPendingStatus(definition))} />
          </div>
          <footer className='flex justify-end gap-2 border-t border-slate-200 pt-4 lg:col-span-2 dark:border-slate-800'>
            <button type='button' onClick={props.onClose} className='rounded-xl px-4 py-2 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800'>Hủy</button>
            <button disabled={saving} className='gradient-btn flex items-center gap-2 rounded-xl px-5 py-2 text-xs font-bold text-white disabled:opacity-60'><Save className='h-4 w-4' />{saving ? 'Đang lưu...' : 'Lưu metric'}</button>
          </footer>
        </form>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className='block space-y-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300'><span>{label}</span>{children}</label>;
}

function FilterEditor({ filters, columns, onChange }: { filters: MetricFilter[]; columns: string[]; onChange: (filters: MetricFilter[]) => void }) {
  const update = (index: number, patch: Partial<MetricFilter>) => onChange(filters.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  return <div className='space-y-2'><div className='flex items-center justify-between'><span className='text-xs font-semibold'>Bộ lọc cố định</span><button type='button' onClick={() => onChange([...filters, { field: columns[0] || '', operator: 'eq', value: '' }])} className='flex items-center gap-1 text-xs text-indigo-600'><Plus className='h-3.5 w-3.5' />Thêm</button></div>{filters.map((filter, index) => <div key={index} className='grid grid-cols-[1fr_110px_1fr_auto] gap-2'><select value={filter.field} onChange={(event) => update(index, { field: event.target.value })} className='form-input'>{columns.map((column) => <option key={column}>{column}</option>)}</select><select value={filter.operator} onChange={(event) => update(index, { operator: event.target.value as FilterOperator, value: null })} className='form-input'>{OPERATORS.map((operator) => <option key={operator}>{operator}</option>)}</select><input disabled={filter.operator.startsWith('is_')} value={displayValue(filter.value)} onChange={(event) => update(index, { value: coerceFilterValue(filter.operator, event.target.value) })} className='form-input' /><button type='button' onClick={() => onChange(filters.filter((_, itemIndex) => itemIndex !== index))}><Trash2 className='h-4 w-4 text-red-500' /></button></div>)}</div>;
}

function displayValue(value: unknown): string {
  return Array.isArray(value) ? value.join(', ') : value == null ? '' : String(value);
}

function validateDefinition(definition: MetricDefinition): string {
  const metric = definition.metric;
  if (!metric.name.trim() || !metric.base_entity || !metric.formula.expression.trim()) return 'Tên, base entity và biểu thức là bắt buộc.';
  if (metric.formula.expression === '*' && metric.formula.function !== 'COUNT') return 'Chỉ COUNT được phép dùng biểu thức *.';
  if (metric.filters.some((item) => !item.field)) return 'Mỗi bộ lọc phải chọn một cột.';
  return '';
}
