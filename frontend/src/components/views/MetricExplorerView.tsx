'use client';

import {
  AlertTriangle,
  BarChart3,
  Calendar,
  ChevronDown,
  ChevronRight,
  Code2,
  Database,
  Eye,
  Filter,
  Layers,
  Loader2,
  Lock,
  Play,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Table as TableIcon,
  Table2,
  Trash2,
  TrendingUp,
  X,
} from 'lucide-react';
import React, { useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SqlCodeViewer } from '@/components/studio/SqlCodeViewer';
import { AIQueryModal } from '@/components/explorer/AIQueryModal';
import {
  CatalogColumn,
  CatalogTable,
  compileSemanticQueryApi,
  DimensionSelection,
  executeSemanticQueryApi,
  FilterOperator,
  MetricRecord,
  SemanticApiError,
  SemanticCatalog,
  SemanticQueryFilter,
  SemanticQueryPreview,
  SemanticQueryRequest,
  SemanticQueryResult,
  SemanticQuerySpec,
  TimeGrain,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { coerceFilterValue, metricName } from '@/lib/metrics';
import { SectionLabel, StatusPill, type WorkspaceDatabase } from '@/components/workspace/shared';
import { ViewHeader } from '@/components/workspace/ViewHeader';

interface Props {
  dbId?: number | null;
  metrics: MetricRecord[];
  catalog: SemanticCatalog | null;
  theme: 'light' | 'dark';
  database?: WorkspaceDatabase | null;
}

interface DraftFilter {
  column_id: number;
  operator: FilterOperator;
  raw: string;
}

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

const TIME_GRAIN_OPTIONS: { label: string; value: TimeGrain | '' }[] = [
  { label: 'Ngày', value: 'day' },
  { label: 'Tuần', value: 'week' },
  { label: 'Tháng', value: 'month' },
  { label: 'Quý', value: 'quarter' },
  { label: 'Năm', value: 'year' },
  { label: 'Gốc', value: '' },
];

export function MetricExplorerView({ dbId, metrics, catalog, theme, database }: Props) {
  const [metricIds, setMetricIds] = useState<number[]>([]);
  const [dimensions, setDimensions] = useState<DimensionSelection[]>([]);
  const [filters, setFilters] = useState<DraftFilter[]>([]);
  const [limit, setLimit] = useState(100);
  const [output, setOutput] = useState<SemanticQueryResult | SemanticQueryPreview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [viewTab, setViewTab] = useState<'table' | 'chart' | 'sql'>('table');
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [dimTab, setDimTab] = useState<'connected' | 'all'>('connected');
  const [openTables, setOpenTables] = useState<Record<number, boolean>>({});

  const approved = metrics.filter((item) => item.status === 'approved' && item.definition);
  const allColumns = catalog ? catalog.tables.flatMap((table) => table.columns) : [];

  const reachableTableIds = useMemo(
    () => (catalog ? getReachableTableIds(metricIds, approved, catalog) : new Set<number>()),
    [metricIds, approved, catalog],
  );

  React.useEffect(() => {
    if (metricIds.length > 0 && reachableTableIds && catalog) {
      setDimensions((prev) => {
        const next = prev.filter((dim) => {
          const table = catalog.tables.find((t) =>
            t.columns.some((c) => c.column_id === dim.column_id),
          );
          return table ? reachableTableIds.has(table.table_id) : true;
        });
        return next.length === prev.length ? prev : next;
      });
    }
  }, [metricIds, reachableTableIds, catalog]);

  if (!catalog) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-2 p-12 text-center text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <p className="text-sm">Đang tải semantic catalog...</p>
      </div>
    );
  }

  if (!catalog.query_supported) {
    return (
      <div className="flex h-full w-full flex-col overflow-hidden bg-background text-foreground">
        <ViewHeader
          title="Metric Explorer"
          description="Compile approved metrics into safe queries — no manual SQL required."
          database={database}
        />
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-500">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div>
            <h2 className="font-semibold text-foreground text-sm">Chế độ xem Technical Preview</h2>
            <p className="mt-1 text-xs text-muted-foreground max-w-md">
              SQL Dump chỉ chứa metadata DDL và không hỗ trợ query. Hãy chọn Live DB.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const request = (): SemanticQueryRequest => ({
    metric_ids: metricIds,
    dimensions,
    filters: filters
      .map((f) => {
        const col = allColumns.find((c) => c.column_id === f.column_id);
        if (!col) return null;
        return {
          column_id: f.column_id,
          operator: f.operator,
          value: coerceFilterValue(f.operator, f.raw),
        };
      })
      .filter((item): item is SemanticQueryFilter => item !== null),
    limit,
  });

  const toggleMetric = (id: number) => {
    setMetricIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  const toggleDimension = (columnId: number) => {
    setDimensions((prev) =>
      prev.some((item) => item.column_id === columnId)
        ? prev.filter((item) => item.column_id !== columnId)
        : [...prev, { column_id: columnId, time_grain: undefined }],
    );
  };

  const setGrain = (columnId: number, grain: TimeGrain | '') => {
    setDimensions((prev) =>
      prev.map((item) =>
        item.column_id === columnId
          ? { ...item, time_grain: grain === '' ? undefined : grain }
          : item,
      ),
    );
  };

  const addFilter = () => {
    if (!allColumns.length) return;
    setFilters((prev) => [...prev, { column_id: allColumns[0].column_id, operator: 'eq', raw: '' }]);
  };

  const updateFilter = (index: number, patch: Partial<DraftFilter>) => {
    setFilters((prev) =>
      prev.map((item, idx) => (idx === index ? { ...item, ...patch } : item)),
    );
  };

  const removeFilter = (index: number) => {
    setFilters((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleAiResolved = (spec: SemanticQuerySpec) => {
    if (spec.metric_ids && spec.metric_ids.length > 0) {
      setMetricIds(spec.metric_ids);
    }
    if (spec.dimensions) {
      setDimensions(spec.dimensions);
    }
    if (spec.filters && spec.filters.length > 0) {
      setFilters(
        spec.filters.map((f: SemanticQueryFilter) => ({
          column_id: f.column_id,
          operator: f.operator,
          raw: String(f.value ?? ''),
        })),
      );
    }
  };

  const runCompile = async () => {
    if (!metricIds.length || !dbId) return;
    setLoading(true);
    setError('');
    try {
      const res = await compileSemanticQueryApi(String(dbId), request());
      setOutput(res);
      setViewTab('sql');
    } catch (err) {
      setError(err instanceof SemanticApiError ? err.message : 'Không thể compile query.');
    } finally {
      setLoading(false);
    }
  };

  const runExecute = async () => {
    if (!metricIds.length || !dbId) return;
    setLoading(true);
    setError('');
    try {
      const res = await executeSemanticQueryApi(String(dbId), request());
      setOutput(res);
      setViewTab('table');
    } catch (err) {
      setError(err instanceof SemanticApiError ? err.message : 'Lỗi thực thi Live DB.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background text-foreground">
      <ViewHeader
        title="Metric Explorer"
        description="Compile approved metrics into safe queries — no manual SQL required."
        database={database}
      />

      <div className="flex min-h-0 flex-1">
        {/* Left Config Panel */}
        <div className="flex w-96 shrink-0 flex-col gap-4 overflow-y-auto border-r border-border p-5">
          {/* Natural Language Prompt Trigger */}
          <div className="rounded-lg border border-border bg-card p-3 shadow-2xs">
            <div className="flex items-center justify-between">
              <SectionLabel>Hỏi bằng ngôn ngữ tự nhiên</SectionLabel>
              <Sparkles className="h-3.5 w-3.5 text-primary" />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Mô tả báo cáo bạn cần xem để AI tự động chọn Metric và Dimension phù hợp.
            </p>
            <Button
              size="sm"
              variant="secondary"
              className="mt-2.5 w-full gap-1.5 text-xs"
              onClick={() => setIsAiModalOpen(true)}
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>AI Tự Động Thiết Lập Truy Vấn</span>
            </Button>
          </div>

          {/* Question Summary Banner */}
          <div className="rounded-lg border border-border bg-secondary/30 p-3 text-xs">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              CÂU HỎI PHÂN TÍCH HIỆN TẠI
            </span>
            <div className="mt-1 space-y-1">
              <p className="font-medium text-foreground">
                {metricIds.length > 0
                  ? `Xem ${metricIds
                      .map((id) => approved.find((m) => m.metric_id === id)?.name || id)
                      .join(', ')}`
                  : 'Chưa chọn chỉ số (Chọn ít nhất 1 metric)'}
                {dimensions.length > 0
                  ? ` theo ${dimensions
                      .map((d) => allColumns.find((c) => c.column_id === d.column_id)?.business_name || d.column_id)
                      .join(', ')}`
                  : ''}
              </p>
            </div>
          </div>

          {/* 1. Metrics Selector */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <SectionLabel>1. CHỈ SỐ ĐO LƯỜNG ({approved.length})</SectionLabel>
            </div>
            <div className="space-y-1">
              {approved.map((m) => {
                const checked = metricIds.includes(m.metric_id);
                return (
                  <label
                    key={m.metric_id}
                    className={cn(
                      'flex cursor-pointer items-center gap-2 rounded-md border p-2 text-xs transition-colors hover:bg-accent/40',
                      checked
                        ? 'border-primary/50 bg-accent text-foreground'
                        : 'border-border bg-card text-muted-foreground',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMetric(m.metric_id)}
                      className="h-3.5 w-3.5 rounded border-border accent-primary cursor-pointer"
                    />
                    <span className="flex-1 font-medium text-foreground">{metricName(m)}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {m.definition?.metric.base_entity}
                    </span>
                  </label>
                );
              })}
              {approved.length === 0 && (
                <p className="p-2 text-xs text-muted-foreground italic">
                  Chưa có metric nào được phê duyệt. Hãy duyệt trong Catalog trước.
                </p>
              )}
            </div>
          </div>

          {/* 2. Dimensions Selector */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <SectionLabel>2. CHIỀU PHÂN TÍCH</SectionLabel>
              <div className="flex rounded-md border border-border bg-card p-0.5 text-[10px]">
                <button
                  type="button"
                  onClick={() => setDimTab('connected')}
                  className={cn(
                    'rounded px-2 py-0.5 transition-colors cursor-pointer',
                    dimTab === 'connected' ? 'bg-primary text-primary-foreground font-semibold' : 'text-muted-foreground',
                  )}
                >
                  Chỉ hiện bảng liên kết
                </button>
                <button
                  type="button"
                  onClick={() => setDimTab('all')}
                  className={cn(
                    'rounded px-2 py-0.5 transition-colors cursor-pointer',
                    dimTab === 'all' ? 'bg-primary text-primary-foreground font-semibold' : 'text-muted-foreground',
                  )}
                >
                  Tất cả
                </button>
              </div>
            </div>

            <div className="space-y-2">
              {catalog.tables.map((table) => {
                const isReachable = reachableTableIds.has(table.table_id);
                if (dimTab === 'connected' && metricIds.length > 0 && !isReachable) {
                  return null;
                }

                const isOpen = openTables[table.table_id] ?? isReachable;

                return (
                  <div
                    key={table.table_id}
                    className="overflow-hidden rounded-md border border-border bg-card shadow-2xs"
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setOpenTables((prev) => ({ ...prev, [table.table_id]: !isOpen }))
                      }
                      className="flex w-full items-center justify-between bg-secondary/30 px-3 py-2 text-left text-xs font-semibold text-foreground cursor-pointer"
                    >
                      <div className="flex items-center gap-1.5">
                        {isOpen ? (
                          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                        )}
                        <span>{table.business_name || table.table_name}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          ({table.table_name})
                        </span>
                      </div>
                      {!isReachable && metricIds.length > 0 && (
                        <span className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                          Chưa liên kết
                        </span>
                      )}
                    </button>

                    {isOpen && (
                      <div className="divide-y divide-border/50 px-2 py-1">
                        {table.columns.map((col) => {
                          const dimSelected = dimensions.find((d) => d.column_id === col.column_id);
                          const isChecked = !!dimSelected;
                          const disabled = metricIds.length > 0 && !isReachable;

                          return (
                            <div
                              key={col.column_id}
                              className="flex items-center justify-between gap-2 py-1.5 text-xs"
                            >
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  disabled={disabled}
                                  onChange={() => toggleDimension(col.column_id)}
                                  className="h-3.5 w-3.5 rounded border-border accent-primary cursor-pointer disabled:opacity-40"
                                />
                                <span
                                  className={cn(
                                    'text-foreground',
                                    disabled && 'opacity-50',
                                  )}
                                >
                                  {col.business_name || col.column_name}
                                </span>
                              </label>

                              {col.is_time_dimension && isChecked && (
                                <select
                                  value={dimSelected?.time_grain || ''}
                                  onChange={(e) =>
                                    setGrain(col.column_id, e.target.value as TimeGrain | '')
                                  }
                                  className="h-6 rounded border border-border bg-background px-1 font-mono text-[10px] outline-none"
                                >
                                  {TIME_GRAIN_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                      {opt.label}
                                    </option>
                                  ))}
                                </select>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3. Filters Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <SectionLabel>3. BỘ LỌC ĐIỀU KIỆN ({filters.length})</SectionLabel>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 gap-1 text-[11px] text-primary"
                onClick={addFilter}
              >
                <Plus className="h-3 w-3" />
                Thêm
              </Button>
            </div>

            <div className="space-y-2">
              {filters.map((f, idx) => (
                <div
                  key={idx}
                  className="flex flex-wrap items-center gap-1.5 rounded-md border border-border bg-card p-2 text-xs"
                >
                  <select
                    value={f.column_id}
                    onChange={(e) =>
                      updateFilter(idx, { column_id: Number(e.target.value) })
                    }
                    className="h-7 flex-1 min-w-[120px] rounded border border-border bg-background px-1.5 text-[11px] outline-none"
                  >
                    {allColumns.map((c) => (
                      <option key={c.column_id} value={c.column_id}>
                        {c.business_name || c.column_name}
                      </option>
                    ))}
                  </select>

                  <select
                    value={f.operator}
                    onChange={(e) =>
                      updateFilter(idx, { operator: e.target.value as FilterOperator })
                    }
                    className="h-7 w-24 rounded border border-border bg-background px-1 text-[11px] outline-none"
                  >
                    {OPERATORS.map((op) => (
                      <option key={op.value} value={op.value}>
                        {op.label}
                      </option>
                    ))}
                  </select>

                  {!f.operator.startsWith('is_') && (
                    <Input
                      value={f.raw}
                      onChange={(e) => updateFilter(idx, { raw: e.target.value })}
                      placeholder="Giá trị..."
                      className="h-7 flex-1 min-w-[80px] px-2 text-[11px]"
                    />
                  )}

                  <button
                    type="button"
                    onClick={() => removeFilter(idx)}
                    className="rounded p-1 text-muted-foreground hover:text-destructive cursor-pointer"
                    aria-label="Remove filter"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="mt-auto space-y-2 pt-4 border-t border-border">
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                className="w-full gap-1.5 text-xs"
                onClick={() => void runCompile()}
                disabled={!metricIds.length || loading}
              >
                <Eye className="h-3.5 w-3.5" />
                <span>Preview SQL</span>
              </Button>
              <Button
                className="w-full gap-1.5 text-xs"
                onClick={() => void runExecute()}
                disabled={!metricIds.length || loading}
              >
                <Play className="h-3.5 w-3.5" />
                <span>Thực thi (Execute)</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Right Results Panel */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
          {/* Result Tab Bar & Guardrails Badge */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-3 bg-secondary/10">
            <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
              {([
                { key: 'table' as const, label: 'Bảng số liệu', icon: Table2 },
                { key: 'chart' as const, label: 'Biểu đồ', icon: TrendingUp },
                { key: 'sql' as const, label: 'SQL Code', icon: Code2 },
              ]).map((t) => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setViewTab(t.key)}
                    className={cn(
                      'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors cursor-pointer',
                      viewTab === t.key
                        ? 'bg-primary text-primary-foreground font-semibold'
                        : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{t.label}</span>
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              <span>Read-only · LIMIT 100 · max 1000 · 15s timeout</span>
            </div>
          </div>

          {/* Results Area */}
          <div className="min-h-0 flex-1 overflow-auto p-6">
            {loading ? (
              <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-2 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-xs">Đang biên dịch & thực thi truy vấn...</p>
              </div>
            ) : error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-xs text-destructive">
                <p className="font-semibold">Lỗi truy vấn:</p>
                <p className="mt-1">{error}</p>
              </div>
            ) : !output ? (
              <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-3 text-center text-muted-foreground">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-secondary text-muted-foreground">
                  <Play className="h-6 w-6" />
                </div>
                <div>
                  <p className="font-semibold text-foreground text-sm">
                    Sẵn sàng biên dịch & phân tích
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Chọn các chỉ số và chiều phân tích ở cột bên trái rồi nhấn Preview SQL hoặc Thực thi.
                  </p>
                </div>
              </div>
            ) : viewTab === 'table' ? (
              isQueryResult(output) ? (
                <div className="overflow-hidden rounded-lg border border-border bg-card shadow-xs">
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-border bg-secondary/50">
                          {output.columns.map((c) => (
                            <th
                              key={c}
                              className="px-4 py-2.5 text-left font-mono text-[11px] uppercase tracking-wider text-muted-foreground"
                            >
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {output.rows.map((row, i) => (
                          <tr
                            key={i}
                            className="border-b border-border last:border-0 hover:bg-accent/40"
                          >
                            {output.columns.map((_, colIdx) => (
                              <td key={colIdx} className="px-4 py-2.5 font-mono text-xs tabular-nums">
                                {String(row[colIdx] ?? '—')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex items-center justify-between border-t border-border bg-secondary/20 px-4 py-2 text-[11px] text-muted-foreground">
                    <span>Tổng số dòng: {output.row_count}</span>
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-border bg-card p-6 text-center text-xs text-muted-foreground">
                  Đây là bản xem trước SQL. Bấm &quot;Thực thi (Execute)&quot; để chạy trên Live DB và xem bảng số liệu.
                </div>
              )
            ) : viewTab === 'chart' ? (
              isQueryResult(output) && output.rows.length > 0 ? (
                <ChartViewer rows={output.rows} columns={output.columns} />
              ) : (
                <div className="rounded-lg border border-border bg-card p-6 text-center text-xs text-muted-foreground">
                  Chưa có dữ liệu đồ thị. Bấm &quot;Thực thi (Execute)&quot; để nạp số liệu từ Live DB.
                </div>
              )
            ) : (
              <div className="overflow-hidden rounded-lg border border-border bg-card shadow-xs">
                <div className="flex items-center justify-between border-b border-border bg-secondary/30 px-4 py-2">
                  <SectionLabel>COMPILED SQL (READ-ONLY)</SectionLabel>
                </div>
                <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-foreground">
                  {output.sql}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>

      <AIQueryModal
        isOpen={isAiModalOpen}
        onClose={() => setIsAiModalOpen(false)}
        dbId={dbId || 0}
        theme={theme || 'dark'}
        onResolved={handleAiResolved}
      />
    </div>
  );
}

function ChartViewer({
  rows,
  columns,
}: {
  rows: unknown[][];
  columns: string[];
}) {
  const numericIdx = columns.findIndex((_, idx) =>
    rows.some((r) => typeof r[idx] === 'number' || (!isNaN(Number(r[idx])) && r[idx] !== '')),
  );
  const labelIdx = numericIdx === 0 ? (columns.length > 1 ? 1 : 0) : 0;
  const numericCol = numericIdx >= 0 ? columns[numericIdx] : null;
  const labelCol = columns[labelIdx] || columns[0];

  if (numericIdx === -1 || !numericCol) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-center text-xs text-muted-foreground">
        Không tìm thấy cột số liệu định lượng để vẽ biểu đồ.
      </div>
    );
  }

  const values = rows.map((r) => Number(r[numericIdx]) || 0);
  const maxVal = Math.max(...values, 1);

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-xs space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-foreground text-sm">
          Biểu đồ phân tích: {numericCol} theo {labelCol}
        </h3>
        <span className="font-mono text-xs text-muted-foreground">
          {rows.length} điểm dữ liệu
        </span>
      </div>

      <div className="space-y-3 pt-2">
        {rows.slice(0, 15).map((r, i) => {
          const val = Number(r[numericIdx]) || 0;
          const pct = Math.min(100, Math.max(2, (val / maxVal) * 100));
          return (
            <div key={i} className="space-y-1">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-foreground truncate max-w-xs">
                  {String(r[labelIdx] ?? '—')}
                </span>
                <span className="text-muted-foreground font-semibold tabular-nums">
                  {val.toLocaleString()}
                </span>
              </div>
              <div className="h-3 w-full rounded-full bg-secondary overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function getReachableTableIds(
  metricIds: number[],
  approvedMetrics: MetricRecord[],
  catalog: SemanticCatalog,
): Set<number> {
  const reachable = new Set<number>();
  const selectedMetrics = approvedMetrics.filter((m) => metricIds.includes(m.metric_id));

  if (!selectedMetrics.length) {
    catalog.tables.forEach((t) => reachable.add(t.table_id));
    return reachable;
  }

  const baseEntities = selectedMetrics
    .map((m) => m.definition?.metric.base_entity)
    .filter((entity): entity is string => Boolean(entity));

  const baseTables = catalog.tables.filter((t) => baseEntities.includes(t.table_name));
  baseTables.forEach((t) => reachable.add(t.table_id));

  // BFS over catalog relationships to mark reachable tables
  const queue = [...reachable];
  while (queue.length > 0) {
    const currentTableId = queue.shift()!;
    for (const rel of catalog.relationships) {
      const fromId = (rel as unknown as { from_table_id?: number; from_entity_id?: number }).from_table_id ?? rel.from_entity_id;
      const toId = (rel as unknown as { to_table_id?: number; to_entity_id?: number }).to_table_id ?? rel.to_entity_id;
      if (fromId === currentTableId && !reachable.has(toId)) {
        reachable.add(toId);
        queue.push(toId);
      }
      if (toId === currentTableId && !reachable.has(fromId)) {
        reachable.add(fromId);
        queue.push(fromId);
      }
    }
  }

  return reachable;
}

function isQueryResult(
  output: SemanticQueryResult | SemanticQueryPreview | null,
): output is SemanticQueryResult {
  return Boolean(output && 'rows' in output && Array.isArray((output as SemanticQueryResult).rows));
}

