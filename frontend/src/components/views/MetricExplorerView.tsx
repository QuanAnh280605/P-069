'use client';

import {
  AlertTriangle,
  BarChart3,
  Box,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Database,
  Eye,
  Filter,
  Layers,
  Loader2,
  Lock,
  MapPin,
  Play,
  Plus,
  RotateCcw,
  Sparkles,
  Table as TableIcon,
  Tag,
  Trash2,
  User,
  X,
} from 'lucide-react';
import React, { useMemo, useState } from 'react';

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
import { coerceFilterValue, metricName } from '@/lib/metrics';

interface Props {
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

export function MetricExplorerView({ dbId, metrics, catalog, theme }: Props) {
  const [metricIds, setMetricIds] = useState<number[]>([]);
  const [dimensions, setDimensions] = useState<DimensionSelection[]>([]);
  const [filters, setFilters] = useState<DraftFilter[]>([]);
  const [limit, setLimit] = useState(100);
  const [output, setOutput] = useState<SemanticQueryResult | SemanticQueryPreview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [viewTab, setViewTab] = useState<'table' | 'chart' | 'sql'>('table');
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);

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
        }))
      );
    }
  };

  if (!catalog) return <State message="Đang tải semantic catalog..." />;
  if (!catalog.query_supported) {
    return (
      <State
        warning
        message="SQL Dump chỉ chứa metadata DDL và không hỗ trợ query. Hãy chọn Live DB."
      />
    );
  }

  const approved = metrics.filter((item) => item.status === 'approved' && item.definition);
  const allColumns = catalog.tables.flatMap((table) => table.columns);

  // 🧠 Compute reachable tables based on selected metric's base entity & relationships
  const reachableTableIds = useMemo(
    () => getReachableTableIds(metricIds, approved, catalog),
    [metricIds, approved, catalog]
  );

  // Auto-deselect dimensions that become unreachable when selected metrics change
  React.useEffect(() => {
    if (metricIds.length > 0 && reachableTableIds && catalog) {
      setDimensions((prev) => {
        const next = prev.filter((dim) => {
          const table = catalog.tables.find((t) => t.columns.some((c) => c.column_id === dim.column_id));
          return table ? reachableTableIds.has(table.table_id) : true;
        });
        return next.length === prev.length ? prev : next;
      });
    }
  }, [metricIds, reachableTableIds, catalog]);

  const request = (): SemanticQueryRequest => ({
    metric_ids: metricIds,
    dimensions,
    filters: buildFilters(filters),
    limit,
  });

  const submit = async (preview: boolean) => {
    if (!dbId || !metricIds.length) {
      return setError('Vui lòng chọn ít nhất một metric đã phê duyệt để thực thi.');
    }
    setLoading(true);
    setError('');
    try {
      const result = preview
        ? await compileSemanticQueryApi(String(dbId), request())
        : await executeSemanticQueryApi(String(dbId), request());
      setOutput(result);
      if (preview) setViewTab('sql');
    } catch (caught) {
      setError(queryError(caught));
    } finally {
      setLoading(false);
    }
  };

  const handleClearAll = () => {
    setMetricIds([]);
    setDimensions([]);
    setFilters([]);
    setOutput(null);
    setError('');
  };

  return (
    <div className="space-y-4">
      {/* 🧭 Top Banner: Natural Query Summary Bar */}
      <QuerySummaryBanner
        selectedMetrics={approved.filter((m) => metricIds.includes(m.metric_id))}
        selectedDimensions={dimensions}
        allColumns={allColumns}
        filters={filters}
        onRemoveMetric={(id) => setMetricIds(metricIds.filter((item) => item !== id))}
        onRemoveDimension={(colId) => setDimensions(dimensions.filter((item) => item.column_id !== colId))}
        onRemoveFilter={(idx) => setFilters(filters.filter((_, i) => i !== idx))}
        onClearAll={handleClearAll}
        onOpenAiModal={() => setIsAiModalOpen(true)}
      />

      {/* Main Grid: Left Controls Sidebar & Right Result Panel */}
      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        {/* Sidebar Controls */}
        <aside className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4.5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          {/* Section 1: Metrics */}
          <MetricSelector metrics={approved} selected={metricIds} onChange={setMetricIds} />

          {/* Section 2: Dimensions grouped by Table with Reachability Filter */}
          <GroupedDimensionSelector
            tables={catalog.tables}
            selected={dimensions}
            reachableTableIds={reachableTableIds}
            hasSelectedMetrics={metricIds.length > 0}
            onChange={setDimensions}
          />

          {/* Section 3: Runtime Filters */}
          <RuntimeFilters filters={filters} columns={allColumns} onChange={setFilters} />

          {/* Section 4: Limit & Action Buttons */}
          <div className="space-y-3 pt-2 border-t border-slate-100 dark:border-slate-800/80">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                Giới hạn dòng (LIMIT)
              </label>
              <div className="flex gap-1">
                {[50, 100, 500, 1000].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setLimit(val)}
                    className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition-all ${
                      limit === val
                        ? 'bg-indigo-600 text-white font-bold'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
                    }`}
                  >
                    {val}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => void submit(true)}
                disabled={loading || !metricIds.length}
                className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-indigo-500/80 py-2.5 text-xs font-bold text-indigo-600 hover:bg-indigo-50/50 disabled:opacity-40 transition-all dark:text-indigo-400 dark:hover:bg-indigo-950/40 cursor-pointer"
              >
                <Eye className="h-4 w-4" />
                Preview SQL
              </button>

              <button
                type="button"
                onClick={() => void submit(false)}
                disabled={loading || !metricIds.length}
                className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-500/20 hover:from-indigo-500 hover:to-indigo-600 disabled:opacity-40 transition-all cursor-pointer"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 fill-white" />
                )}
                Thực thi (Execute)
              </button>
            </div>

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
                <p className="font-semibold mb-0.5">Lỗi thực thi:</p>
                {error}
              </div>
            )}
          </div>
        </aside>

        {/* Main Result Workspace */}
        <main className="min-w-0">
          <ResultPanel
            output={output}
            theme={theme}
            metrics={approved}
            catalog={catalog}
            viewTab={viewTab}
            onTabChange={setViewTab}
          />
        </main>
      </div>

      {/* Guided Wizard AI Query Modal */}
      {dbId && (
        <AIQueryModal
          isOpen={isAiModalOpen}
          dbId={dbId}
          theme={theme}
          onClose={() => setIsAiModalOpen(false)}
          onResolved={handleAiResolved}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 🧠 Reachable Tables Logic (Semantic Safe Path Checking)
// ---------------------------------------------------------------------------

function getReachableTableIds(
  selectedMetricIds: number[],
  metrics: MetricRecord[],
  catalog: SemanticCatalog | null
): Set<number> | null {
  if (!catalog || selectedMetricIds.length === 0) return null;

  const selectedMetrics = metrics.filter((m) => selectedMetricIds.includes(m.metric_id));
  if (selectedMetrics.length === 0) return null;

  const baseTableIds = new Set<number>();
  for (const m of selectedMetrics) {
    const metricBaseId =
      m.definition?.metric.base_entity_id ||
      (m as { base_entity_id?: number }).base_entity_id;
    const metricBaseName = (m.definition?.metric.base_entity || '').toLowerCase().trim();

    if (metricBaseId && catalog.tables.some((t) => t.table_id === metricBaseId)) {
      baseTableIds.add(metricBaseId);
    } else if (metricBaseName) {
      const cleanBaseName = metricBaseName.includes('.')
        ? metricBaseName.split('.').pop()!
        : metricBaseName;
      const found = catalog.tables.find((t) => {
        const cleanTableName = t.table_name.toLowerCase().includes('.')
          ? t.table_name.toLowerCase().split('.').pop()!
          : t.table_name.toLowerCase();
        return (
          cleanTableName === cleanBaseName ||
          t.table_name.toLowerCase() === metricBaseName ||
          t.business_name?.toLowerCase() === metricBaseName
        );
      });
      if (found) baseTableIds.add(found.table_id);
    }
  }

  // If no base table could be resolved, return an empty set rather than null, so user is protected
  if (baseTableIds.size === 0) {
    return new Set<number>();
  }

  // Build adjacency graph from relationships (many-to-one links)
  const graph = new Map<number, number[]>();
  for (const rel of catalog.relationships || []) {
    const relType = (rel as { relationship_type?: string }).relationship_type?.toLowerCase() || 'many_to_one';
    if (relType === 'many_to_one' || relType === 'many-to-one') {
      const list = graph.get(rel.from_entity_id) || [];
      list.push(rel.to_entity_id);
      graph.set(rel.from_entity_id, list);
    }
  }

  const reachable = new Set<number>();
  for (const baseId of baseTableIds) {
    reachable.add(baseId);
    const queue = [baseId];
    const visited = new Set<number>([baseId]);

    while (queue.length > 0) {
      const curr = queue.shift()!;
      const neighbors = graph.get(curr) || [];
      for (const next of neighbors) {
        if (!visited.has(next)) {
          visited.add(next);
          reachable.add(next);
          queue.push(next);
        }
      }
    }
  }

  return reachable;
}

// ---------------------------------------------------------------------------
// 🧭 Query Summary Banner (Natural Question Builder)
// ---------------------------------------------------------------------------

function QuerySummaryBanner({
  selectedMetrics,
  selectedDimensions,
  allColumns,
  filters,
  onRemoveMetric,
  onRemoveDimension,
  onRemoveFilter,
  onClearAll,
  onOpenAiModal,
}: {
  selectedMetrics: MetricRecord[];
  selectedDimensions: DimensionSelection[];
  allColumns: CatalogColumn[];
  filters: DraftFilter[];
  onRemoveMetric: (id: number) => void;
  onRemoveDimension: (colId: number) => void;
  onRemoveFilter: (idx: number) => void;
  onClearAll: () => void;
  onOpenAiModal?: () => void;
}) {
  const hasSelections = selectedMetrics.length > 0 || selectedDimensions.length > 0 || filters.length > 0;

  return (
    <div className="rounded-2xl border border-indigo-100 bg-gradient-to-r from-indigo-50/70 via-white to-purple-50/70 p-4 shadow-xs dark:border-indigo-950/50 dark:from-slate-900 dark:via-slate-900 dark:to-indigo-950/30">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-100/60 pb-2.5 dark:border-slate-800">
        <div className="flex items-center gap-2 text-xs font-bold text-indigo-900 dark:text-indigo-300">
          <Sparkles className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
          <span>CÂU HỎI PHÂN TÍCH HIỆN TẠI</span>
        </div>
        <div className="flex items-center gap-3">
          {onOpenAiModal && (
            <button
              type="button"
              onClick={onOpenAiModal}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1 text-xs font-semibold text-white hover:bg-indigo-700 transition-colors shadow-xs cursor-pointer"
            >
              <Sparkles className="h-3.5 w-3.5" />
              ✨ AI Assistant
            </button>
          )}
          {hasSelections && (
            <button
              type="button"
              onClick={onClearAll}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400 cursor-pointer"
            >
              <RotateCcw className="h-3 w-3" />
              Làm mới bộ chọn
            </button>
          )}
        </div>
      </div>

      {!hasSelections ? (
        <p className="mt-2.5 text-xs text-slate-500 italic dark:text-slate-400">
          👉 Hãy chọn ít nhất một <strong>Metric (Chỉ số)</strong> ở thanh bên trái để bắt đầu tạo câu hỏi phân tích.
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs leading-relaxed">
          {/* Metrics Chips */}
          <span className="font-semibold text-slate-600 dark:text-slate-400">Đo lường:</span>
          {selectedMetrics.length === 0 ? (
            <span className="rounded-lg border border-dashed border-amber-300 bg-amber-50/80 px-2.5 py-1 text-[11px] font-medium text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300">
              Chưa chọn metric
            </span>
          ) : (
            selectedMetrics.map((metric) => (
              <span
                key={metric.metric_id}
                className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-100/80 px-2.5 py-1 font-semibold text-indigo-900 shadow-2xs dark:border-indigo-800 dark:bg-indigo-950/80 dark:text-indigo-200"
              >
                <Tag className="h-3 w-3 text-indigo-600 dark:text-indigo-400" />
                {metricName(metric)}
                <button
                  type="button"
                  onClick={() => onRemoveMetric(metric.metric_id)}
                  className="rounded hover:bg-indigo-200 dark:hover:bg-indigo-800 cursor-pointer p-0.5"
                  title="Bỏ chọn"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))
          )}

          {/* Dimensions Chips */}
          <span className="ml-2 font-semibold text-slate-600 dark:text-slate-400">➔ Cắt lát theo:</span>
          {selectedDimensions.length === 0 ? (
            <span className="text-[11px] text-slate-400 italic">Tổng toàn cục (không gom nhóm)</span>
          ) : (
            selectedDimensions.map((dim) => {
              const col = allColumns.find((c) => c.column_id === dim.column_id);
              const name = col?.business_name || col?.column_name || `Cột #${dim.column_id}`;
              const grainText = dim.time_grain ? ` (${translateGrain(dim.time_grain)})` : '';
              return (
                <span
                  key={dim.column_id}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-purple-200 bg-purple-100/80 px-2.5 py-1 font-semibold text-purple-900 shadow-2xs dark:border-purple-800 dark:bg-purple-950/80 dark:text-purple-200"
                >
                  {col?.is_time_dimension ? (
                    <Calendar className="h-3 w-3 text-purple-600 dark:text-purple-400" />
                  ) : (
                    <MapPin className="h-3 w-3 text-purple-600 dark:text-purple-400" />
                  )}
                  {name}
                  {grainText}
                  <button
                    type="button"
                    onClick={() => onRemoveDimension(dim.column_id)}
                    className="rounded hover:bg-purple-200 dark:hover:bg-purple-800 cursor-pointer p-0.5"
                    title="Bỏ chọn"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              );
            })
          )}

          {/* Filters Chips */}
          {filters.length > 0 && (
            <>
              <span className="ml-2 font-semibold text-slate-600 dark:text-slate-400">➔ Bộ lọc:</span>
              {filters.map((flt, idx) => {
                const col = allColumns.find((c) => c.column_id === flt.column_id);
                const colName = col?.business_name || col?.column_name || `Cột #${flt.column_id}`;
                return (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  >
                    <Filter className="h-3 w-3 text-slate-500" />
                    {colName} {flt.operator} {flt.raw ? `"${flt.raw}"` : ''}
                    <button
                      type="button"
                      onClick={() => onRemoveFilter(idx)}
                      className="rounded hover:bg-slate-200 dark:hover:bg-slate-700 cursor-pointer p-0.5"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 📦 Section 1: Metric Selector
// ---------------------------------------------------------------------------

function MetricSelector({
  metrics,
  selected,
  onChange,
}: {
  metrics: MetricRecord[];
  selected: number[];
  onChange: (ids: number[]) => void;
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
          <Tag className="h-3.5 w-3.5 text-indigo-500" />
          1. CHỈ SỐ ĐO LƯỜNG (METRICS)
        </h3>
        <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
          {metrics.length} chỉ số
        </span>
      </div>

      <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
        {metrics.length === 0 ? (
          <p className="text-xs text-slate-400 italic p-2 border rounded-xl">
            Chưa có metric nào được phê duyệt.
          </p>
        ) : (
          metrics.map((metric) => {
            const isChecked = selected.includes(metric.metric_id);
            return (
              <label
                key={metric.metric_id}
                className={`group flex cursor-pointer items-start gap-2.5 rounded-xl border p-2.5 text-xs transition-all ${
                  isChecked
                    ? 'border-indigo-500 bg-indigo-50/70 shadow-xs dark:border-indigo-500/80 dark:bg-indigo-950/50 dark:hover:bg-indigo-950/70 hover:bg-indigo-50'
                    : 'border-slate-200 bg-slate-50/50 hover:border-indigo-300 hover:bg-indigo-50/30 dark:border-slate-800 dark:bg-slate-800/40 dark:hover:border-indigo-500/60 dark:hover:bg-slate-800/90'
                }`}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => onChange(toggle(selected, metric.metric_id))}
                  className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 cursor-pointer"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-bold text-slate-800 dark:text-slate-100">
                      {metricName(metric)}
                    </span>
                    {metric.definition?.metric.formula.function && (
                      <span className="rounded bg-slate-200/80 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                        {metric.definition.metric.formula.function}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                    <span className="inline-flex items-center gap-1 font-mono">
                      <Box className="h-3 w-3" />
                      {metric.definition?.metric.base_entity}
                    </span>
                    {metric.definition?.metric.filters && metric.definition.metric.filters.length > 0 && (
                      <span className="rounded-sm bg-amber-100 px-1 text-[10px] text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                        {metric.definition.metric.filters.length} bộ lọc
                      </span>
                    )}
                  </div>
                </div>
              </label>
            );
          })
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// 🗂️ Section 2: Grouped Dimension Selector by Entity (Table Accordion)
// ---------------------------------------------------------------------------

function GroupedDimensionSelector({
  tables,
  selected,
  reachableTableIds,
  hasSelectedMetrics,
  onChange,
}: {
  tables: CatalogTable[];
  selected: DimensionSelection[];
  reachableTableIds: Set<number> | null;
  hasSelectedMetrics: boolean;
  onChange: (items: DimensionSelection[]) => void;
}) {
  const [expandedTables, setExpandedTables] = useState<number[]>(() => {
    if (!hasSelectedMetrics || !reachableTableIds) {
      return tables.map((t) => t.table_id);
    }
    return tables.filter((t) => reachableTableIds.has(t.table_id)).map((t) => t.table_id);
  });

  const [onlyShowReachable, setOnlyShowReachable] = useState<boolean>(true);

  // Auto-expand reachable tables and collapse unreachable tables when selected metrics change
  React.useEffect(() => {
    if (hasSelectedMetrics && reachableTableIds) {
      const nextExpanded = tables.filter((t) => reachableTableIds.has(t.table_id)).map((t) => t.table_id);
      setExpandedTables((prev) => {
        if (prev.length === nextExpanded.length && prev.every((id, idx) => id === nextExpanded[idx])) {
          return prev;
        }
        return nextExpanded;
      });
    }
  }, [hasSelectedMetrics, reachableTableIds, tables]);

  const toggleTable = (tableId: number) => {
    setExpandedTables((prev) =>
      prev.includes(tableId) ? prev.filter((id) => id !== tableId) : [...prev, tableId]
    );
  };

  const updateGrain = (columnId: number, grain: string) => {
    onChange(
      selected.map((item) =>
        item.column_id === columnId
          ? { ...item, time_grain: (grain || null) as TimeGrain | null }
          : item
      )
    );
  };

  const toggleDimension = (columnId: number) => {
    const exists = selected.some((item) => item.column_id === columnId);
    if (exists) {
      onChange(selected.filter((item) => item.column_id !== columnId));
    } else {
      onChange([...selected, { column_id: columnId }]);
    }
  };

  // Sort tables: Reachable tables first, unreachable tables at the bottom
  const sortedTables = useMemo(() => {
    if (!hasSelectedMetrics || !reachableTableIds) return tables;
    const reachable = tables.filter((t) => reachableTableIds.has(t.table_id));
    const unreachable = tables.filter((t) => !reachableTableIds.has(t.table_id));
    return onlyShowReachable ? reachable : [...reachable, ...unreachable];
  }, [tables, hasSelectedMetrics, reachableTableIds, onlyShowReachable]);

  const unreachableCount = useMemo(() => {
    if (!hasSelectedMetrics || !reachableTableIds) return 0;
    return tables.filter((t) => !reachableTableIds.has(t.table_id)).length;
  }, [tables, hasSelectedMetrics, reachableTableIds]);

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
          <Layers className="h-3.5 w-3.5 text-purple-500" />
          2. CHIỀU PHÂN TÍCH (DIMENSIONS)
        </h3>
        <span className="text-[11px] font-medium text-slate-500">
          Đã chọn: <strong className="text-purple-600 dark:text-purple-400">{selected.length}</strong>
        </span>
      </div>

      {/* Filter tabs if unreachable tables exist */}
      {hasSelectedMetrics && unreachableCount > 0 && (
        <div className="flex items-center justify-between gap-1 rounded-lg bg-slate-100 p-0.5 text-[10px] font-medium dark:bg-slate-800">
          <button
            type="button"
            onClick={() => setOnlyShowReachable(true)}
            className={`flex-1 rounded-md py-1 transition-all cursor-pointer text-center ${
              onlyShowReachable
                ? 'bg-white font-bold text-purple-600 shadow-2xs dark:bg-slate-900 dark:text-purple-400'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Chỉ hiện bảng liên kết ({tables.length - unreachableCount})
          </button>
          <button
            type="button"
            onClick={() => setOnlyShowReachable(false)}
            className={`flex-1 rounded-md py-1 transition-all cursor-pointer text-center ${
              !onlyShowReachable
                ? 'bg-white font-bold text-slate-800 shadow-2xs dark:bg-slate-900 dark:text-white'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            Tất cả ({tables.length})
          </button>
        </div>
      )}

      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
        {sortedTables.length === 0 ? (
          <p className="text-xs text-slate-400 italic p-3 text-center border rounded-xl">
            Không có bảng nào có liên kết với Metric đang chọn.
          </p>
        ) : (
          sortedTables.map((table) => {
            const isExpanded = expandedTables.includes(table.table_id);
            const isReachable = !hasSelectedMetrics || !reachableTableIds || reachableTableIds.has(table.table_id);

            const tableSelectedCount = table.columns.filter((c) =>
              selected.some((s) => s.column_id === c.column_id)
            ).length;

            return (
              <div
                key={table.table_id}
                className={`rounded-xl border transition-all overflow-hidden ${
                  isReachable
                    ? 'border-slate-200/90 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-800/30'
                    : 'border-slate-200/50 bg-slate-100/40 dark:border-slate-800/50 dark:bg-slate-900/30 opacity-70'
                }`}
              >
                {/* Table Accordion Header */}
                <button
                  type="button"
                  onClick={() => toggleTable(table.table_id)}
                  className="flex w-full items-center justify-between px-3 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-100/70 dark:text-slate-200 dark:hover:bg-slate-800/60 cursor-pointer"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {getTableIcon(table.table_name)}
                    <span className="truncate">{table.business_name || table.table_name}</span>
                    <span className="font-mono text-[10px] text-slate-400">({table.table_name})</span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {!isReachable ? (
                      <span className="inline-flex items-center gap-1 rounded bg-slate-200 px-1.5 py-0.5 text-[9px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                        <Lock className="h-2.5 w-2.5" /> Chưa liên kết
                      </span>
                    ) : tableSelectedCount > 0 ? (
                      <span className="rounded-full bg-purple-100 px-1.5 py-0.2 text-[10px] font-bold text-purple-700 dark:bg-purple-950 dark:text-purple-300">
                        {tableSelectedCount}
                      </span>
                    ) : null}

                    {isExpanded ? (
                      <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
                    )}
                  </div>
                </button>

                {/* Table Columns List */}
                {isExpanded && (
                  <div className="divide-y divide-slate-100 bg-white p-1.5 dark:divide-slate-800 dark:bg-slate-900/90">
                    {table.columns.map((column) => {
                      const active = selected.find((item) => item.column_id === column.column_id);
                      return (
                      <div
                        key={column.column_id}
                        className={`rounded-lg p-1.5 text-xs transition-colors ${
                          !isReachable
                            ? 'opacity-50 cursor-not-allowed'
                            : 'hover:bg-slate-50 dark:hover:bg-slate-800/60'
                        }`}
                        title={
                          !isReachable
                            ? 'Bảng này chưa có quan hệ Many-to-One an toàn với Metric đang chọn'
                            : undefined
                        }
                      >
                        <label
                          className={`flex items-center justify-between gap-2 ${
                            isReachable ? 'cursor-pointer' : 'cursor-not-allowed'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <input
                              type="checkbox"
                              disabled={!isReachable}
                              checked={Boolean(active)}
                              onChange={() => isReachable && toggleDimension(column.column_id)}
                              className={`rounded border-slate-300 text-purple-600 focus:ring-purple-500 dark:border-slate-700 ${
                                isReachable ? 'cursor-pointer' : 'cursor-not-allowed'
                              }`}
                            />
                            {getColumnIcon(column)}
                            <span className="truncate text-slate-800 dark:text-slate-200">
                              {column.business_name || column.column_name}
                            </span>
                            <span className="font-mono text-[10px] text-slate-400">
                              ({column.column_name})
                            </span>
                          </div>

                          {column.is_time_dimension && (
                            <span className="rounded bg-indigo-50 px-1 text-[9px] font-semibold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                              Thời gian
                            </span>
                          )}
                        </label>

                        {/* Segmented Time Grain Selector Pills */}
                        {active && column.is_time_dimension && isReachable && (
                          <div className="mt-2 pl-6">
                            <div className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 mb-1">
                              <span>Gom nhóm theo:</span>
                            </div>
                            <div className="grid grid-cols-6 gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
                              {TIME_GRAIN_OPTIONS.map((grain) => {
                                const isCurrentGrain = (active.time_grain || '') === grain.value;
                                return (
                                  <button
                                    key={grain.label}
                                    type="button"
                                    onClick={() => updateGrain(column.column_id, grain.value)}
                                    className={`rounded py-1 text-[10px] font-medium transition-all cursor-pointer ${
                                      isCurrentGrain
                                        ? 'bg-purple-600 text-white font-bold shadow-2xs'
                                        : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'
                                    }`}
                                  >
                                    {grain.label}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  </section>
);
}

// ---------------------------------------------------------------------------
// 🔍 Section 3: Runtime Filters
// ---------------------------------------------------------------------------

function RuntimeFilters({
  filters,
  columns,
  onChange,
}: {
  filters: DraftFilter[];
  columns: CatalogColumn[];
  onChange: (filters: DraftFilter[]) => void;
}) {
  const update = (index: number, patch: Partial<DraftFilter>) =>
    onChange(filters.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-slate-500" />
          3. BỘ LỌC ĐIỀU KIỆN (FILTERS)
        </h3>
        <button
          type="button"
          disabled={!columns.length}
          onClick={() =>
            onChange([
              ...filters,
              { column_id: columns[0].column_id, operator: 'eq', raw: '' },
            ])
          }
          className="inline-flex items-center gap-1 text-xs font-bold text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" />
          Thêm lọc
        </button>
      </div>

      {filters.length === 0 ? (
        <p className="text-[11px] text-slate-400 italic">Không có bộ lọc runtime nào.</p>
      ) : (
        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
          {filters.map((filter, index) => (
            <div
              key={index}
              className="rounded-xl border border-slate-200 bg-slate-50/70 p-2 text-xs dark:border-slate-800 dark:bg-slate-800/50 space-y-1.5"
            >
              <div className="flex items-center justify-between gap-1">
                <select
                  value={filter.column_id}
                  onChange={(event) => update(index, { column_id: Number(event.target.value) })}
                  className="form-input flex-1 text-xs"
                >
                  {columns.map((column) => (
                    <option value={column.column_id} key={column.column_id}>
                      {column.business_name || column.column_name} ({column.column_name})
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => onChange(filters.filter((_, itemIndex) => itemIndex !== index))}
                  className="rounded p-1 text-slate-400 hover:text-red-500 transition-colors cursor-pointer"
                  title="Xóa bộ lọc"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>

              <div className="grid grid-cols-[130px_1fr] gap-1.5">
                <select
                  value={filter.operator}
                  onChange={(event) =>
                    update(index, { operator: event.target.value as FilterOperator })
                  }
                  className="form-input text-xs"
                >
                  {OPERATORS.map((op) => (
                    <option key={op.value} value={op.value}>
                      {op.label}
                    </option>
                  ))}
                </select>

                {!filter.operator.startsWith('is_') && (
                  <input
                    type="text"
                    placeholder="Giá trị lọc..."
                    value={filter.raw}
                    onChange={(event) => update(index, { raw: event.target.value })}
                    className="form-input text-xs"
                  />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// 📊 Result Panel (Table View, Chart View, SQL Code View)
// ---------------------------------------------------------------------------

function ResultPanel({
  output,
  theme,
  metrics,
  catalog,
  viewTab,
  onTabChange,
}: {
  output: SemanticQueryResult | SemanticQueryPreview | null;
  theme: 'light' | 'dark';
  metrics: MetricRecord[];
  catalog: SemanticCatalog | null;
  viewTab: 'table' | 'chart' | 'sql';
  onTabChange: (tab: 'table' | 'chart' | 'sql') => void;
}) {
  if (!output) {
    return <State message="Hãy chọn ít nhất 1 Metric, sau đó nhấn Preview SQL hoặc Thực thi." />;
  }

  const isExecutedResult = 'rows' in output;
  const result = isExecutedResult ? (output as SemanticQueryResult) : null;

  return (
    <div className="space-y-4">
      {/* Tab Switcher & Result Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-xs dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-2">
          {result ? (
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
              <TableIcon className="h-4 w-4 text-indigo-600" />
              Kết quả truy vấn ({result.row_count} dòng)
            </h2>
          ) : (
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
              <Eye className="h-4 w-4 text-indigo-600" />
              Bản xem trước SQL (Preview Mode)
            </h2>
          )}
        </div>

        {/* View Mode Buttons */}
        <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
          <button
            type="button"
            onClick={() => onTabChange('table')}
            disabled={!result}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold transition-all cursor-pointer ${
              viewTab === 'table' && result
                ? 'bg-white text-indigo-600 shadow-xs dark:bg-slate-900 dark:text-indigo-400'
                : 'text-slate-600 hover:text-slate-900 disabled:opacity-40 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            <TableIcon className="h-3.5 w-3.5" />
            Bảng số liệu
          </button>

          <button
            type="button"
            onClick={() => onTabChange('chart')}
            disabled={!result || result.rows.length === 0}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold transition-all cursor-pointer ${
              viewTab === 'chart'
                ? 'bg-white text-purple-600 shadow-xs dark:bg-slate-900 dark:text-purple-400'
                : 'text-slate-600 hover:text-slate-900 disabled:opacity-40 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            Biểu đồ trực quan
          </button>

          <button
            type="button"
            onClick={() => onTabChange('sql')}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-semibold transition-all cursor-pointer ${
              viewTab === 'sql'
                ? 'bg-white text-slate-900 shadow-xs dark:bg-slate-900 dark:text-white'
                : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            <Code2 className="h-3.5 w-3.5" />
            SQL Code
          </button>
        </div>
      </div>

      {/* View Content based on Tab */}
      {viewTab === 'table' && result && (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="overflow-x-auto max-h-96">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800/90 z-10">
                <tr>
                  {result.columns.map((column) => (
                    <th
                      key={column}
                      className="border-b border-slate-200 p-2.5 font-bold text-slate-700 dark:border-slate-700 dark:text-slate-200"
                    >
                      {resolveColumnHeader(column, output, metrics, catalog)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {result.rows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={result.columns.length}
                      className="p-6 text-center text-slate-400 italic"
                    >
                      Không có bản ghi nào thỏa mãn điều kiện.
                    </td>
                  </tr>
                ) : (
                  result.rows.map((row, rowIndex) => (
                    <tr
                      key={rowIndex}
                      className="hover:bg-indigo-50/30 dark:hover:bg-slate-800/50 transition-colors"
                    >
                      {row.map((value, colIndex) => (
                        <td
                          key={colIndex}
                          className="p-2.5 font-mono text-slate-800 dark:text-slate-200"
                        >
                          {formatCell(value)}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {viewTab === 'chart' && result && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <SimpleAnalyticsChart
            result={result}
            output={output}
            metrics={metrics}
            catalog={catalog}
          />
        </div>
      )}

      {/* SQL Viewer Box */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-3">
        <SqlCodeViewer
          sql={output.sql}
          title="SQL read-only do SemanticQueryCompiler biên dịch"
          theme={theme}
        />

        {output.parameters && Object.keys(output.parameters).length > 0 && (
          <div>
            <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1">
              Parameters Bound:
            </span>
            <pre className="overflow-x-auto rounded-xl bg-slate-950 p-3 text-xs text-cyan-300 font-mono">
              {JSON.stringify(output.parameters, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 📈 Simple Visual Chart Component for Data Explorer
// ---------------------------------------------------------------------------

function SimpleAnalyticsChart({
  result,
  output,
  metrics,
  catalog,
}: {
  result: SemanticQueryResult;
  output: SemanticQueryResult | SemanticQueryPreview | null;
  metrics: MetricRecord[];
  catalog: SemanticCatalog | null;
}) {
  const chartData = useMemo(() => {
    if (!result || result.rows.length === 0) return null;
    const isSingleRow = result.rows.length === 1;

    const dimensionColName = result.columns[0];
    const metricColName = result.columns[result.columns.length - 1];

    const parsedRows = result.rows.map((row) => {
      const label = formatCell(row[0]);
      const rawVal = row[row.length - 1];
      const numVal = typeof rawVal === 'number' ? rawVal : parseFloat(String(rawVal)) || 0;
      return { label, val: numVal, formatted: formatCell(rawVal) };
    });

    const maxVal = Math.max(...parsedRows.map((r) => r.val), 1);
    return {
      isSingleRow,
      dimensionTitle: resolveColumnHeader(dimensionColName, output, metrics, catalog),
      metricTitle: resolveColumnHeader(metricColName, output, metrics, catalog),
      rows: parsedRows,
      maxVal,
    };
  }, [result, output, metrics, catalog]);

  if (!chartData) {
    return <p className="text-xs text-slate-400 italic">Không có dữ liệu để vẽ biểu đồ.</p>;
  }

  if (chartData.isSingleRow) {
    const single = chartData.rows[0];
    return (
      <div className="text-center py-6">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">
          {chartData.metricTitle}
        </span>
        <div className="text-3xl font-extrabold text-indigo-600 dark:text-indigo-400 font-mono">
          {single.formatted}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-2 dark:border-slate-800">
        <h4 className="text-xs font-bold text-slate-700 dark:text-slate-300">
          Phân bố: <span className="text-indigo-600 dark:text-indigo-400">{chartData.metricTitle}</span> theo{' '}
          <span className="text-purple-600 dark:text-purple-400">{chartData.dimensionTitle}</span>
        </h4>
        <span className="text-[11px] text-slate-400">{chartData.rows.length} nhóm</span>
      </div>

      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-2">
        {chartData.rows.map((item, idx) => {
          const percentage = Math.min(100, Math.max(5, (item.val / chartData.maxVal) * 100));
          return (
            <div key={idx} className="space-y-1 text-xs">
              <div className="flex items-center justify-between font-medium">
                <span className="text-slate-700 dark:text-slate-300 truncate max-w-[240px]">
                  {item.label}
                </span>
                <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
                  {item.formatted}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-500"
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 🛠️ Helper Utilities
// ---------------------------------------------------------------------------

function State({ message, warning = false }: { message: string; warning?: boolean }) {
  return (
    <div
      className={
        'rounded-2xl border p-10 text-center text-sm ' +
        (warning
          ? 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300'
          : 'border-slate-200 bg-white text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400')
      }
    >
      {warning && <AlertTriangle className="mx-auto mb-2 h-6 w-6" />}
      {message}
    </div>
  );
}

function resolveColumnHeader(
  col: string,
  output: SemanticQueryResult | SemanticQueryPreview | null,
  metrics: MetricRecord[],
  catalog: SemanticCatalog | null,
): string {
  if (output && 'metadata' in output && output.metadata) {
    const meta = output.metadata as Record<string, Record<string, string>>;
    if (meta.metrics?.[col]) return meta.metrics[col];
    if (meta.dimensions?.[col]) return meta.dimensions[col];
  }
  if (col.startsWith('metric_')) {
    const id = Number(col.replace('metric_', ''));
    const found = metrics.find((item) => item.metric_id === id);
    if (found) return metricName(found);
  }
  if (col.startsWith('dimension_')) {
    const colId = Number(col.replace('dimension_', ''));
    const found = catalog?.tables.flatMap((t) => t.columns).find((item) => item.column_id === colId);
    if (found) return found.business_name || found.column_name;
  }
  return col;
}

function getTableIcon(tableName: string) {
  const lower = tableName.toLowerCase();
  if (lower.includes('order') || lower.includes('don_hang')) return <Box className="h-3.5 w-3.5 text-indigo-500" />;
  if (lower.includes('customer') || lower.includes('khach_hang') || lower.includes('user'))
    return <User className="h-3.5 w-3.5 text-emerald-500" />;
  if (lower.includes('item') || lower.includes('product') || lower.includes('san_pham'))
    return <Tag className="h-3.5 w-3.5 text-purple-500" />;
  return <Database className="h-3.5 w-3.5 text-slate-400" />;
}

function getColumnIcon(column: CatalogColumn) {
  if (column.is_time_dimension) return <Calendar className="h-3 w-3 text-indigo-500" />;
  const lower = column.column_name.toLowerCase();
  if (lower.includes('city') || lower.includes('tinh') || lower.includes('dia_chi') || lower.includes('address'))
    return <MapPin className="h-3 w-3 text-emerald-500" />;
  return <Tag className="h-3 w-3 text-slate-400" />;
}

function translateGrain(grain: TimeGrain): string {
  const map: Record<TimeGrain, string> = {
    day: 'Theo Ngày',
    week: 'Theo Tuần',
    month: 'Theo Tháng',
    quarter: 'Theo Quý',
    year: 'Theo Năm',
  };
  return map[grain] || grain;
}

function buildFilters(filters: DraftFilter[]): SemanticQueryFilter[] {
  return filters.map((item) => ({
    column_id: item.column_id,
    operator: item.operator,
    value: coerceFilterValue(item.operator, item.raw),
  }));
}

function queryError(error: unknown): string {
  if (error instanceof SemanticApiError && error.status === 504) {
    return 'Query vượt quá thời gian tối đa 15 giây.';
  }
  return error instanceof Error ? error.message : 'Không thể compile hoặc thực thi query.';
}

function toggle(values: number[], value: number): number[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function formatNumber(num: number): string {
  if (Number.isInteger(num) || Math.abs(num - Math.round(num)) < 1e-6) {
    return Math.round(num).toLocaleString('vi-VN');
  }
  return num.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return formatNumber(value);

  if (typeof value === 'string') {
    const trimmed = value.trim();
    // Numeric string e.g. "228842722125.000"
    if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
      const num = parseFloat(trimmed);
      if (!isNaN(num)) return formatNumber(num);
    }
    // ISO Date string
    if (/^\d{4}-\d{2}-\d{2}/.test(trimmed)) {
      const date = new Date(trimmed);
      if (!isNaN(date.getTime())) {
        if (/^\d{4}-\d{2}$/.test(trimmed)) {
          return `Tháng ${trimmed.slice(5, 7)}/${trimmed.slice(0, 4)}`;
        }
        return date.toLocaleDateString('vi-VN');
      }
    }
    return trimmed;
  }

  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
