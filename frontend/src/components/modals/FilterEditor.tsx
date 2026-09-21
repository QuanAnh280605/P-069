'use client';

import { Plus, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  FilterOperator,
  MetricFilter,
} from '@/lib/api';
import { coerceFilterValue } from '@/lib/metrics';

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

function displayValue(value: unknown): string {
  return Array.isArray(value) ? value.join(', ') : value == null ? '' : String(value);
}

function FilterValueInput({
  filter,
  onUpdate,
}: {
  filter: MetricFilter;
  onUpdate: (patch: Partial<MetricFilter>) => void;
}) {
  return (
    <Input
      disabled={filter.operator.startsWith('is_')}
      value={displayValue(filter.value)}
      onChange={(e) => onUpdate({ value: coerceFilterValue(filter.operator, e.target.value) })}
      className="h-8 flex-1 px-2 text-xs"
    />
  );
}

function FilterRow({
  filter,
  columns,
  onUpdate,
  onRemove,
}: {
  filter: MetricFilter;
  columns: string[];
  onUpdate: (patch: Partial<MetricFilter>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <select
        value={filter.field}
        onChange={(e) => onUpdate({ field: e.target.value })}
        className="h-8 flex-1 rounded border border-border bg-card text-foreground px-2 text-xs outline-none dark:bg-zinc-900 dark:text-zinc-100 [&>option]:bg-white [&>option]:text-zinc-900 dark:[&>option]:bg-zinc-900 dark:[&>option]:text-zinc-100"
      >
        {columns.map((c) => (
          <option key={c} value={c} className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100">
            {c}
          </option>
        ))}
      </select>
      <select
        value={filter.operator}
        onChange={(e) => onUpdate({ operator: e.target.value as FilterOperator, value: null })}
        className="h-8 w-24 rounded border border-border bg-card text-foreground px-1 text-xs outline-none dark:bg-zinc-900 dark:text-zinc-100 [&>option]:bg-white [&>option]:text-zinc-900 dark:[&>option]:bg-zinc-900 dark:[&>option]:text-zinc-100"
      >
        {OPERATORS.map((op) => (
          <option key={op.value} value={op.value} className="bg-white text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100">
            {op.label}
          </option>
        ))}
      </select>
      <FilterValueInput filter={filter} onUpdate={onUpdate} />
      <button
        type="button"
        onClick={onRemove}
        className="rounded p-1 text-muted-foreground hover:text-destructive cursor-pointer"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

interface FilterEditorProps {
  filters: MetricFilter[];
  columns: string[];
  onChange: (filters: MetricFilter[]) => void;
}

export function FilterEditor({ filters, columns, onChange }: FilterEditorProps) {
  const update = (index: number, patch: Partial<MetricFilter>) =>
    onChange(filters.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs font-medium">Bộ lọc cố định</Label>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onChange([...filters, { field: columns[0] || '', operator: 'eq', value: '' }])}
          className="h-6 gap-1 text-[11px] text-primary"
        >
          <Plus className="h-3 w-3" />
          Thêm
        </Button>
      </div>
      {filters.map((filter, index) => (
        <FilterRow
          key={index}
          filter={filter}
          columns={columns}
          onUpdate={(patch) => update(index, patch)}
          onRemove={() => onChange(filters.filter((_, i) => i !== index))}
        />
      ))}
    </div>
  );
}
