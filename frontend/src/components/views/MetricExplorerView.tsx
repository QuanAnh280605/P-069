'use client';

import { AlertTriangle, Filter, Loader2, Play, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';

import {
  CatalogColumn,
  executeSemanticQueryApi,
  FilterOperator,
  MetricRecord,
  SemanticApiError,
  SemanticCatalog,
  SemanticQueryFilter,
  SemanticQueryResult,
} from '@/lib/api';
import { SqlCodeViewer } from '@/components/studio/SqlCodeViewer';
import { coerceFilterValue, metricName } from '@/lib/metrics';

interface MetricExplorerViewProps {
  dbId?: number | null;
  metrics: MetricRecord[];
  catalog: SemanticCatalog | null;
  theme: 'light' | 'dark';
}

interface DraftFilter {
  column_id: number;
  operator: FilterOperator;
  raw: string;
}

const OPERATORS: FilterOperator[] = ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in', 'is_null', 'is_not_null'];

export function MetricExplorerView({ dbId, metrics, catalog, theme }: MetricExplorerViewProps) {
  const [metricIds, setMetricIds] = useState<number[]>([]);
  const [dimensionIds, setDimensionIds] = useState<number[]>([]);
  const [filters, setFilters] = useState<DraftFilter[]>([]);
  const [limit, setLimit] = useState(100);
  const [result, setResult] = useState<SemanticQueryResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const approved = metrics.filter((item) => item.status === 'approved' && item.definition);
  const baseEntity = approved.find((item) => metricIds.includes(item.metric_id))?.definition?.metric.base_entity;
  const tables = reachableTables(catalog, baseEntity);
  const columns = tables.flatMap((table) => table.columns);

  if (!catalog) return <State message='Đang tải semantic catalog...' />;
  if (!catalog.query_supported) return <State warning message='SQL Dump chỉ chứa metadata DDL và không hỗ trợ thực thi query. Hãy chọn một Live DB.' />;

  const toggleMetric = (metric: MetricRecord) => {
    setMetricIds((current) => current.includes(metric.metric_id) ? current.filter((id) => id !== metric.metric_id) : [...current, metric.metric_id]);
    setResult(null);
  };

  const run = async () => {
    if (!dbId || !metricIds.length) return setError('Chọn ít nhất một metric đã phê duyệt.');
    setLoading(true);
    setError('');
    try {
      setResult(await executeSemanticQueryApi(String(dbId), { metric_ids: metricIds, dimension_ids: dimensionIds, filters: buildFilters(filters), limit }));
    } catch (caught) {
      setError(queryError(caught));
    } finally {
      setLoading(false);
    }
  };

  return <div className='grid gap-4 xl:grid-cols-[360px_1fr]'><aside className='space-y-5 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900'><section><h3 className='mb-2 text-xs font-bold uppercase text-slate-500'>Metrics đã phê duyệt</h3><div className='space-y-2'>{approved.map((metric) => { const selectedBase = baseEntity; const base = metric.definition?.metric.base_entity; const disabled = Boolean(selectedBase && base !== selectedBase); return <label key={metric.metric_id} className={`flex items-start gap-2 rounded-xl border p-3 text-xs ${disabled ? 'cursor-not-allowed opacity-45' : 'cursor-pointer'}`} title={disabled ? 'Các metric trong một query phải cùng base entity' : ''}><input type='checkbox' checked={metricIds.includes(metric.metric_id)} disabled={disabled} onChange={() => toggleMetric(metric)} /><span><strong>{metricName(metric)}</strong><small className='mt-1 block font-mono text-slate-500'>{base}</small></span></label>; })}{!approved.length && <p className='text-xs text-amber-600'>Chưa có metric approved. Hãy duyệt metric trong Catalog.</p>}</div></section><Selector title='Dimensions' columns={columns} selected={dimensionIds} onToggle={(id) => setDimensionIds(toggle(dimensionIds, id))} /><RuntimeFilters filters={filters} columns={columns} onChange={setFilters} /><label className='block text-xs font-bold'>LIMIT<input type='number' min={1} max={1000} value={limit} onChange={(event) => setLimit(Math.min(1000, Math.max(1, Number(event.target.value))))} className='form-input mt-1' /></label><button onClick={() => void run()} disabled={loading || !metricIds.length} className='w-full rounded-xl bg-indigo-600 py-2.5 text-xs font-bold text-white disabled:opacity-50'>{loading ? <Loader2 className='mr-1 inline h-4 w-4 animate-spin' /> : <Play className='mr-1 inline h-4 w-4' />}{loading ? 'Đang thực thi...' : 'Compile & Execute'}</button>{error && <p className='rounded-xl bg-red-50 p-3 text-xs text-red-700 dark:bg-red-950/30 dark:text-red-300'>{error}</p>}</aside><main className='min-w-0 space-y-4'><ResultPanel result={result} theme={theme} /></main></div>;
}

function Selector({ title, columns, selected, onToggle }: { title: string; columns: CatalogColumn[]; selected: number[]; onToggle: (id: number) => void }) {
  return <section><h3 className='mb-2 text-xs font-bold uppercase text-slate-500'>{title}</h3><div className='max-h-48 space-y-1 overflow-auto'>{columns.map((column) => <label key={column.column_id} className='flex cursor-pointer gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-slate-50 dark:hover:bg-slate-800'><input type='checkbox' checked={selected.includes(column.column_id)} onChange={() => onToggle(column.column_id)} /><span>{column.business_name} <small className='font-mono text-slate-500'>({column.column_name})</small></span></label>)}</div></section>;
}

function RuntimeFilters({ filters, columns, onChange }: { filters: DraftFilter[]; columns: CatalogColumn[]; onChange: (filters: DraftFilter[]) => void }) {
  const update = (index: number, patch: Partial<DraftFilter>) => onChange(filters.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  return <section className='space-y-2'><div className='flex justify-between'><h3 className='text-xs font-bold uppercase text-slate-500'><Filter className='mr-1 inline h-3.5 w-3.5' />Filters</h3><button type='button' disabled={!columns.length} onClick={() => onChange([...filters, { column_id: columns[0].column_id, operator: 'eq', raw: '' }])} className='text-xs text-indigo-600 disabled:opacity-40'><Plus className='mr-1 inline h-3.5 w-3.5' />Thêm</button></div>{filters.map((filter, index) => <div key={index} className='grid grid-cols-[1fr_90px_auto] gap-1'><select value={filter.column_id} onChange={(event) => update(index, { column_id: Number(event.target.value) })} className='form-input'>{columns.map((column) => <option value={column.column_id} key={column.column_id}>{column.column_name}</option>)}</select><select value={filter.operator} onChange={(event) => update(index, { operator: event.target.value as FilterOperator })} className='form-input'>{OPERATORS.map((operator) => <option key={operator}>{operator}</option>)}</select><button onClick={() => onChange(filters.filter((_, itemIndex) => itemIndex !== index))}><Trash2 className='h-4 w-4 text-red-500' /></button>{!filter.operator.startsWith('is_') && <input value={filter.raw} onChange={(event) => update(index, { raw: event.target.value })} placeholder={filter.operator.includes('in') ? 'A, B, C' : 'Giá trị'} className='form-input col-span-2' />}</div>)}</section>;
}

function ResultPanel({ result, theme }: { result: SemanticQueryResult | null; theme: 'light' | 'dark' }) {
  if (!result) return <State message='Chọn metric và bấm Compile & Execute để xem kết quả.' />;
  return <><div className='rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900'><div className='mb-3 flex justify-between'><h2 className='text-sm font-bold'>Kết quả truy vấn</h2><span className='text-xs text-slate-500'>{result.row_count} dòng</span></div>{result.rows.length ? <div className='overflow-auto'><table className='w-full text-left text-xs'><thead><tr>{result.columns.map((column) => <th key={column} className='border-b p-2 font-bold'>{column}</th>)}</tr></thead><tbody>{result.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((value, index) => <td key={index} className='border-b border-slate-100 p-2 font-mono dark:border-slate-800'>{formatCell(value)}</td>)}</tr>)}</tbody></table></div> : <p className='py-10 text-center text-xs text-slate-500'>Query hợp lệ nhưng không có dữ liệu.</p>}</div><details className='rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900'><summary className='cursor-pointer text-xs font-bold'>SQL compiled và parameters</summary><div className='mt-3 space-y-2'><SqlCodeViewer sql={result.sql} title='SQL read-only do SemanticQueryCompiler tạo' theme={theme} /><pre className='overflow-auto rounded-xl bg-slate-950 p-3 text-xs text-cyan-300'>{JSON.stringify(result.parameters, null, 2)}</pre></div></details></>;
}

function State({ message, warning = false }: { message: string; warning?: boolean }) {
  return <div className={`rounded-2xl border p-10 text-center text-sm ${warning ? 'border-amber-300 bg-amber-50 text-amber-800 dark:bg-amber-950/30' : 'border-slate-200 bg-white text-slate-500 dark:border-slate-800 dark:bg-slate-900'}`}>{warning && <AlertTriangle className='mx-auto mb-2 h-6 w-6' />}{message}</div>;
}

function reachableTables(catalog: SemanticCatalog | null, base?: string) {
  if (!catalog) return [];
  if (!base) return catalog.tables;
  const start = catalog.tables.find((table) => table.table_name === base);
  if (!start) return [];
  const ids = new Set([start.table_id]);
  let changed = true;
  while (changed) { changed = false; for (const edge of catalog.relationships) { if (ids.has(edge.from_entity_id) && !ids.has(edge.to_entity_id)) { ids.add(edge.to_entity_id); changed = true; } if (ids.has(edge.to_entity_id) && !ids.has(edge.from_entity_id)) { ids.add(edge.from_entity_id); changed = true; } } }
  return catalog.tables.filter((table) => ids.has(table.table_id));
}

function buildFilters(filters: DraftFilter[]): SemanticQueryFilter[] {
  return filters.map((item) => ({ column_id: item.column_id, operator: item.operator, value: coerceFilterValue(item.operator, item.raw) }));
}

function queryError(error: unknown): string {
  if (error instanceof SemanticApiError && error.status === 504) return 'Query vượt quá thời gian tối đa 15 giây.';
  if (error instanceof SemanticApiError && error.status === 400) return `Không thể compile query: ${error.message}`;
  return error instanceof Error ? error.message : 'Không thể thực thi query.';
}

function toggle(values: number[], value: number): number[] { return values.includes(value) ? values.filter((item) => item !== value) : [...values, value]; }
function formatCell(value: unknown): string { return value == null ? 'NULL' : typeof value === 'object' ? JSON.stringify(value) : String(value); }
