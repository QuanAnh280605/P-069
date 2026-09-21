'use client';

import {
  AlertTriangle,
  AreaChart as AreaChartIcon,
  BarChart3,
  Calendar,
  Check,
  Code2,
  Copy,
  Download,
  Eye,
  Filter,
  Layers,
  LineChart as LineChartIcon,
  Loader2,
  PieChart as PieChartIcon,
  Play,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  Table as TableIcon,
  Table2,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

import {
  CatalogColumn,
  CatalogTable,
  compileSemanticQueryApi,
  DimensionSelection,
  executeSemanticQueryApi,
  getMetricJoinPathOptionsApi,
  getMetricRecommendedDimensionsApi,
  MetricDimensionsResponse,
  MetricJoinPathOptions,
  MetricRecord,
  RecommendedDimensionItem,
  SemanticApiError,
  SemanticCatalog,
  SemanticQueryFilter,
  SemanticQueryPreview,
  SemanticQueryRequest,
  SemanticQueryResult,
  TimeGrain,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { metricName } from '@/lib/metrics';
import {
  getDimensionCategory,
  getDimensionCategoryBadge,
  isBusinessDimension,
  isTechnicalKey,
  isTimeDimension,
} from '@/lib/dimensions';
import { SectionLabel, StatusPill, type WorkspaceDatabase } from '@/components/workspace/shared';
import { ViewHeader } from '@/components/workspace/ViewHeader';

/**
 * Stateful selection pushed from the Metrics Dashboard drill-down.
 * `requestKey` is monotonically increasing so the Explorer applies each
 * drill-down exactly once and never replays a stale selection on ordinary
 * navigation back to the Explorer tab.
 */
export interface ExplorerInitialSelection {
  metricId: number;
  dimensionColId?: number | null;
  timeGrain?: TimeGrain | null;
  dateFilters: SemanticQueryFilter[];
  requestKey: number;
}

interface Props {
  dbId?: number | null;
  metrics: MetricRecord[];
  catalog: SemanticCatalog | null;
  theme: 'light' | 'dark';
  database?: WorkspaceDatabase | null;
  initialSelection?: ExplorerInitialSelection | null;
}

const TIME_GRAIN_OPTIONS: { label: string; value: TimeGrain; enLabel: string }[] = [
  { label: 'Ngày', value: 'day', enLabel: 'Day' },
  { label: 'Tuần', value: 'week', enLabel: 'Week' },
  { label: 'Tháng', value: 'month', enLabel: 'Month' },
  { label: 'Quý', value: 'quarter', enLabel: 'Quarter' },
  { label: 'Năm', value: 'year', enLabel: 'Year' },
];

type ChartType = 'bar' | 'line' | 'area' | 'pie';

const PIE_COLORS = [
  '#3b82f6', // blue
  '#10b981', // emerald
  '#8b5cf6', // violet
  '#f59e0b', // amber
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#6366f1', // indigo
  '#14b8a6', // teal
  '#f97316', // orange
  '#84cc16', // lime
];

/**
 * Format raw column aliases / keys into friendly Vietnamese business names.
 */
function formatColumnTitle(
  colKey: string,
  metadata?: Record<string, any>,
  catalog?: SemanticCatalog | null,
  metrics?: MetricRecord[],
): string {
  if (!colKey) return '';

  // 1. Check compiler metadata map (e.g. metadata.dimensions['dimension_101'])
  if (metadata?.dimensions && metadata.dimensions[colKey]) {
    return metadata.dimensions[colKey];
  }
  if (metadata?.metrics && metadata.metrics[colKey]) {
    return metadata.metrics[colKey];
  }

  // 2. Check pattern dimension_{id} or metric_{id}
  const dimMatch = colKey.match(/^dimension_(\d+)$/i);
  if (dimMatch && catalog) {
    const colId = Number(dimMatch[1]);
    for (const table of catalog.tables) {
      const found = table.columns.find((c) => c.column_id === colId);
      if (found) return found.business_name || found.column_name;
    }
  }

  const metricMatch = colKey.match(/^metric_(\d+)$/i);
  if (metricMatch && metrics) {
    const mId = Number(metricMatch[1]);
    const found = metrics.find((m) => m.metric_id === mId);
    if (found) return found.name;
  }

  // 3. Check direct column match in catalog
  if (catalog) {
    for (const table of catalog.tables) {
      const found = table.columns.find(
        (c) => c.column_name.toLowerCase() === colKey.toLowerCase(),
      );
      if (found && found.business_name) return found.business_name;
    }
  }

  // 4. Check direct metric match
  if (metrics) {
    const found = metrics.find(
      (m) => m.name.toLowerCase() === colKey.toLowerCase(),
    );
    if (found) return found.name;
  }

  // 5. Clean up SQL aggregation names
  if (/^SUM\((.+)\)$/i.test(colKey)) {
    return `Tổng ${colKey.replace(/^SUM\((.+)\)$/i, '$1')}`;
  }
  if (/^AVG\((.+)\)$/i.test(colKey)) {
    return `Trung bình ${colKey.replace(/^AVG\((.+)\)$/i, '$1')}`;
  }
  if (/^COUNT\((.+)\)$/i.test(colKey)) {
    return `Số lượng ${colKey.replace(/^COUNT\((.+)\)$/i, '$1')}`;
  }

  return colKey;
}

/**
 * Format categorical / date dimension values according to data types.
 */
function formatDimensionValue(val: unknown): string {
  if (val === null || val === undefined || val === '') return '(Trống)';
  const str = String(val).trim();

  // Boolean
  if (val === true || str.toLowerCase() === 'true') return 'Có';
  if (val === false || str.toLowerCase() === 'false') return 'Không';

  // Date format: YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
    const parts = str.split('T')[0].split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
  }

  // Month format: YYYY-MM
  if (/^\d{4}-\d{2}$/.test(str)) {
    const [year, month] = str.split('-');
    return `Tháng ${month}/${year}`;
  }

  // Week format: YYYY-Www or YYYY-ww
  if (/^\d{4}-W?(\d{1,2})$/i.test(str)) {
    const match = str.match(/^(\d{4})-W?(\d{1,2})$/i);
    if (match) return `Tuần ${match[2]}/${match[1]}`;
  }

  // Quarter format: YYYY-Qx
  if (/^\d{4}-Q(\d)$/i.test(str)) {
    const match = str.match(/^(\d{4})-Q(\d)$/i);
    if (match) return `Quý ${match[2]}/${match[1]}`;
  }

  // Year format: YYYY
  if (/^\d{4}$/.test(str) && Number(str) >= 1990 && Number(str) <= 2100) {
    return `Năm ${str}`;
  }

  return str;
}

/**
 * Format metric numeric values for charts and axes.
 */
function formatShortNumber(num: number): string {
  if (Math.abs(num) >= 1_000_000_000) {
    return `${(num / 1_000_000_000).toFixed(1).replace(/\.0$/, '')} Tỷ`;
  }
  if (Math.abs(num) >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1).replace(/\.0$/, '')} Tr`;
  }
  if (Math.abs(num) >= 1_000) {
    return `${(num / 1_000).toFixed(1).replace(/\.0$/, '')} K`;
  }
  return num.toLocaleString();
}

export function MetricExplorerView({
  dbId,
  metrics,
  catalog,
  theme,
  database,
  initialSelection,
}: Props) {
  const [metricIds, setMetricIds] = useState<number[]>([]);
  const [dimensions, setDimensions] = useState<DimensionSelection[]>([]);
  const [limit, setLimit] = useState(100);
  const [output, setOutput] = useState<SemanticQueryResult | SemanticQueryPreview | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [viewTab, setViewTab] = useState<'table' | 'chart' | 'sql'>('table');
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [metricSearch, setMetricSearch] = useState('');
  const [dimSearch, setDimSearch] = useState('');
  const [copiedSql, setCopiedSql] = useState(false);
  const [recommendedDims, setRecommendedDims] = useState<RecommendedDimensionItem[]>([]);
  const [loadingDims, setLoadingDims] = useState(false);
  const [joinOptions, setJoinOptions] = useState<MetricJoinPathOptions>({});
  const [filters, setFilters] = useState<SemanticQueryFilter[]>([]);
  const [dashboardFilterActive, setDashboardFilterActive] = useState(false);
  const appliedSelectionKey = useRef<number | null>(null);

  const approved = useMemo(
    () => metrics.filter((item) => item.status === 'approved' && item.definition),
    [metrics],
  );

  const displayedMetrics = useMemo(() => {
    if (!metricSearch.trim()) return approved;
    const q = metricSearch.toLowerCase();
    return approved.filter((m) => {
      const name = metricName(m).toLowerCase();
      const techName = (m.name || '').toLowerCase();
      const baseEntity = (m.definition?.metric.base_entity || '').toLowerCase();
      const formulaFn = (m.definition?.metric.formula.function || '').toLowerCase();
      const expr = (m.definition?.metric.formula.expression || '').toLowerCase();
      const desc = (m.description || m.definition?.metric.excluded_notes || '').toLowerCase();
      return (
        name.includes(q) ||
        techName.includes(q) ||
        baseEntity.includes(q) ||
        formulaFn.includes(q) ||
        expr.includes(q) ||
        desc.includes(q)
      );
    });
  }, [approved, metricSearch]);

  const selectedMetric = useMemo(
    () => approved.find((m) => metricIds.includes(m.metric_id)),
    [approved, metricIds],
  );

  const baseTable = useMemo(() => {
    if (!catalog || !selectedMetric?.definition?.metric.base_entity) return null;
    return (
      catalog.tables.find(
        (t) =>
          t.table_name === selectedMetric.definition?.metric.base_entity ||
          t.table_id === selectedMetric.definition?.metric.base_entity_id,
      ) || null
    );
  }, [catalog, selectedMetric]);

  const allColumns = useMemo(
    () => (catalog ? catalog.tables.flatMap((table) => table.columns) : []),
    [catalog],
  );

  const metricDefinedDimensions = useMemo(() => {
    const rawDims = selectedMetric?.definition?.metric?.dimensions || [];
    if (!catalog || rawDims.length === 0) return [];
    const matched: Array<{ column_id: number; name: string; business_name: string; table_name: string }> = [];
    const matchedRaw = new Set<string>();

    // Helper: Map foreign key or entity reference (e.g. 'store_id', 'store') to descriptive name column in recommendedDims
    const resolveEntityNameDim = (dimName: string) => {
      const lower = dimName.toLowerCase().trim();
      const entity = lower.endsWith('_id') ? lower.replace(/_id$/, '') : lower;
      return recommendedDims.find((rec) => {
        const tLower = rec.table_name.toLowerCase();
        if (tLower !== entity && tLower !== lower) return false;
        const cLower = rec.column_name.toLowerCase();
        const bLower = (rec.business_name || '').toLowerCase();
        return cLower === 'name' || cLower.endsWith('_name') || bLower.includes('tên');
      });
    };

    // 0. Check if any raw dimension is an entity or foreign key that maps directly to recommendedDims entity name
    rawDims.forEach((d) => {
      const lower = d.toLowerCase().trim();
      const isFkPattern = lower.endsWith('_id') || lower === 'id' || lower === 'store';
      if (isFkPattern && recommendedDims.length > 0) {
        const entityDim = resolveEntityNameDim(d);
        if (entityDim && !matched.some((m) => m.column_id === entityDim.column_id)) {
          matchedRaw.add(d);
          matched.push({
            column_id: entityDim.column_id,
            name: entityDim.column_name,
            business_name: entityDim.business_name || entityDim.column_name,
            table_name: entityDim.table_business_name || entityDim.table_name,
          });
        }
      }
    });

    // 1. Try to find match in baseTable first (100% fanout safe), but avoid technical foreign keys if entity name exists
    if (baseTable) {
      baseTable.columns.forEach((c) => {
        const matchingDim = rawDims.find(
          (d) =>
            !matchedRaw.has(d) &&
            (d === c.column_name ||
              (c.business_name && d === c.business_name) ||
              d === `${baseTable.table_name}.${c.column_name}` ||
              d.toLowerCase() === c.column_name.toLowerCase()),
        );
        if (matchingDim) {
          const isFk = isTechnicalKey(c) || c.is_foreign_key || c.column_name.endsWith('_id');
          const entityDim = isFk ? resolveEntityNameDim(c.column_name) : undefined;
          if (entityDim && !matched.some((m) => m.column_id === entityDim.column_id)) {
            matchedRaw.add(matchingDim);
            matched.push({
              column_id: entityDim.column_id,
              name: entityDim.column_name,
              business_name: entityDim.business_name || entityDim.column_name,
              table_name: entityDim.table_business_name || entityDim.table_name,
            });
          } else {
            matchedRaw.add(matchingDim);
            matched.push({
              column_id: c.column_id,
              name: c.column_name,
              business_name: c.business_name || c.column_name,
              table_name: baseTable.business_name || baseTable.table_name,
            });
          }
        }
      });
    }

    // 2. For any remaining unmatched dimensions, search recommendedDims (safe joins)
    if (matchedRaw.size < rawDims.length && recommendedDims.length > 0) {
      recommendedDims.forEach((rec) => {
        const matchingDim = rawDims.find(
          (d) =>
            !matchedRaw.has(d) &&
            (d === rec.column_name ||
              (rec.business_name && d === rec.business_name) ||
              d === `${rec.table_name}.${rec.column_name}` ||
              d.toLowerCase() === rec.column_name.toLowerCase() ||
              d.toLowerCase() === `${rec.table_name}.${rec.column_name}`.toLowerCase()),
        );
        if (matchingDim && !matched.some((m) => m.column_id === rec.column_id)) {
          matchedRaw.add(matchingDim);
          matched.push({
            column_id: rec.column_id,
            name: rec.column_name,
            business_name: rec.business_name || rec.column_name,
            table_name: rec.table_business_name || rec.table_name,
          });
        }
      });
    }

    // 3. For any still unmatched dimensions, check other catalog tables
    if (matchedRaw.size < rawDims.length) {
      catalog.tables.forEach((t) => {
        if (baseTable && t.table_id === baseTable.table_id) return;
        t.columns.forEach((c) => {
          const matchingDim = rawDims.find(
            (d) =>
              !matchedRaw.has(d) &&
              (d === c.column_name ||
                (c.business_name && d === c.business_name) ||
                d === `${t.table_name}.${c.column_name}` ||
                (t.business_name && d === `${t.business_name}.${c.column_name}`) ||
                d.toLowerCase() === c.column_name.toLowerCase() ||
                d.toLowerCase() === `${t.table_name}.${c.column_name}`.toLowerCase()),
          );
          if (matchingDim && !matched.some((m) => m.column_id === c.column_id)) {
            matchedRaw.add(matchingDim);
            matched.push({
              column_id: c.column_id,
              name: c.column_name,
              business_name: c.business_name || c.column_name,
              table_name: t.business_name || t.table_name,
            });
          }
        });
      });
    }

    return matched;
  }, [selectedMetric, catalog, baseTable, recommendedDims]);

  useEffect(() => {
    if (metricDefinedDimensions.length > 0) {
      setDimensions((prev) => {
        const existingIds = new Set(prev.map((d) => d.column_id));
        const newDims = metricDefinedDimensions
          .filter((d) => !existingIds.has(d.column_id))
          .map((d) => {
            const col = allColumns.find((c) => c.column_id === d.column_id);
            const isTime = col ? isTimeDimension(col) : false;
            return { column_id: d.column_id, time_grain: isTime ? ('month' as const) : undefined };
          });
        return [...prev, ...newDims];
      });
    }
  }, [metricDefinedDimensions, allColumns]);

  // Time columns available contextually for the selected metric
  const availableTimeColumns = useMemo(() => {
    if (!catalog) return [];
    if (baseTable) {
      const baseTimeCols = baseTable.columns.filter((col) => isTimeDimension(col));
      if (baseTimeCols.length > 0) return baseTimeCols;
    }
    return allColumns.filter((col) => isTimeDimension(col));
  }, [catalog, baseTable, allColumns]);

  // Fetch backend-recommended dimensions whenever selected metric changes
  useEffect(() => {
    if (!dbId || metricIds.length === 0) {
      setRecommendedDims([]);
      return;
    }
    const primaryMetricId = metricIds[0];
    let isMounted = true;
    setLoadingDims(true);

    getMetricRecommendedDimensionsApi(dbId, primaryMetricId)
      .then((res) => {
        if (isMounted && res && Array.isArray(res.dimensions)) {
          setRecommendedDims(res.dimensions);
        }
      })
      .catch((err) => {
        console.error('Failed to load recommended dimensions from backend:', err);
      })
      .finally(() => {
        if (isMounted) setLoadingDims(false);
      });

    return () => {
      isMounted = false;
    };
  }, [dbId, metricIds]);

  // Fetch governed join-path options for the selected metric's base entity so we
  // can flag ambiguous dimensions that lack a persisted preferred path. A single
  // safe path is deterministic (compiler handles it); only multi-path targets
  // require a stored preferred_join_paths entry to be queryable.
  useEffect(() => {
    const baseEntityId = selectedMetric?.definition?.metric.base_entity_id;
    if (!dbId || !baseEntityId) {
      setJoinOptions({});
      return;
    }
    let isMounted = true;
    getMetricJoinPathOptionsApi(dbId, baseEntityId)
      .then((opts) => {
        if (isMounted) setJoinOptions(opts);
      })
      .catch(() => {
        if (isMounted) setJoinOptions({});
      });
    return () => {
      isMounted = false;
    };
  }, [dbId, selectedMetric]);

  const displayedDimensions = useMemo(() => {
    if (!catalog || metricIds.length === 0) return [];

    if (recommendedDims.length > 0) {
      if (!dimSearch.trim()) return recommendedDims;
      const q = dimSearch.toLowerCase();
      return recommendedDims.filter(
        (d) =>
          d.column_name.toLowerCase().includes(q) ||
          (d.business_name && d.business_name.toLowerCase().includes(q)) ||
          d.table_name.toLowerCase().includes(q) ||
          (d.table_business_name && d.table_business_name.toLowerCase().includes(q)),
      );
    }

    if (!baseTable) return [];
    const baseDims = baseTable.columns
      .filter((c) => isBusinessDimension(c))
      .map((c) => ({
        column_id: c.column_id,
        column_name: c.column_name,
        business_name: c.business_name || c.column_name,
        table_id: baseTable.table_id,
        table_name: baseTable.table_name,
        table_business_name: baseTable.business_name || baseTable.table_name,
        tier: 'A' as const,
        tier_label: 'Trực tiếp',
        is_safe_join: true,
        requires_reaggregation: false,
        data_type: c.data_type,
      }));

    if (!dimSearch.trim()) return baseDims;
    const q = dimSearch.toLowerCase();
    return baseDims.filter(
      (d) =>
        d.column_name.toLowerCase().includes(q) ||
        (d.business_name && d.business_name.toLowerCase().includes(q)),
    );
  }, [metricIds, recommendedDims, dimSearch, catalog, baseTable]);

  // Ambiguous dimensions (target reachable via >1 safe governed path) that the
  // selected metric has NOT pinned with a preferred_join_paths entry. These cannot
  // be compiled deterministically, so we disable them and point the user to a Data
  // Lead instead of opening any runtime clarification modal.
  const unsupportedDimensionColumnIds = useMemo(() => {
    const preferred = selectedMetric?.definition?.metric.preferred_join_paths || {};
    const baseTableId = baseTable?.table_id;
    const ids = new Set<number>();
    for (const dim of displayedDimensions) {
      if (baseTableId != null && dim.table_id === baseTableId) continue;
      const opts = joinOptions[String(dim.table_id)];
      if (!opts || opts.length <= 1) continue;
      if (!preferred[String(dim.table_id)]) ids.add(dim.column_id);
    }
    return ids;
  }, [displayedDimensions, joinOptions, selectedMetric, baseTable]);

  useEffect(() => {
    if (!initialSelection) return;
    if (appliedSelectionKey.current === initialSelection.requestKey) return;
    if (!catalog) return;
    appliedSelectionKey.current = initialSelection.requestKey;

    setMetricIds([initialSelection.metricId]);

    const nextDimensions: DimensionSelection[] = [];

    let timeColId: number | null = null;
    if (initialSelection.timeGrain) {
      const metric = approved.find((m) => m.metric_id === initialSelection.metricId);
      const baseTable = metric?.definition?.metric.base_entity
        ? catalog.tables.find(
            (t) =>
              t.table_name === metric.definition?.metric.base_entity ||
              t.table_id === metric.definition?.metric.base_entity_id,
          )
        : undefined;
      const timeCol = baseTable
        ? baseTable.columns.find((c) => isTimeDimension(c))
        : allColumns.find((c) => isTimeDimension(c));
      timeColId = timeCol ? timeCol.column_id : null;
    }

    if (initialSelection.dimensionColId) {
      const dimCol = allColumns.find((c) => c.column_id === initialSelection.dimensionColId);
      const isTimeDim = dimCol ? isTimeDimension(dimCol) : false;
      if (isTimeDim && initialSelection.timeGrain && initialSelection.dimensionColId === timeColId) {
        nextDimensions.push({
          column_id: initialSelection.dimensionColId,
          time_grain: initialSelection.timeGrain,
        });
      } else {
        nextDimensions.push({ column_id: initialSelection.dimensionColId, time_grain: undefined });
      }
    }

    if (initialSelection.timeGrain && timeColId !== null) {
      const alreadyAdded = nextDimensions.some((d) => d.column_id === timeColId);
      if (!alreadyAdded) {
        nextDimensions.push({ column_id: timeColId, time_grain: initialSelection.timeGrain });
      }
    }

    setDimensions(nextDimensions);

    if (initialSelection.dateFilters.length > 0) {
      setFilters(initialSelection.dateFilters);
      setDashboardFilterActive(true);
    } else {
      setFilters([]);
      setDashboardFilterActive(false);
    }
  }, [initialSelection, catalog, approved, allColumns]);

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
          eyebrow="Explore"
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
    filters,
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

  const selectedTimeDimension = dimensions.find((d) => {
    const col = allColumns.find((c) => c.column_id === d.column_id);
    return col && isTimeDimension(col);
  });

  const setTimeDimensionColumn = (columnIdStr: string) => {
    if (!columnIdStr) {
      setDimensions((prev) =>
        prev.filter((d) => {
          const col = allColumns.find((c) => c.column_id === d.column_id);
          return !col || !isTimeDimension(col);
        }),
      );
      return;
    }
    const columnId = Number(columnIdStr);
    const existingGrain = selectedTimeDimension?.time_grain || 'month';
    setDimensions((prev) => {
      const nonTime = prev.filter((d) => {
        const col = allColumns.find((c) => c.column_id === d.column_id);
        return !col || !isTimeDimension(col);
      });
      return [...nonTime, { column_id: columnId, time_grain: existingGrain }];
    });
  };

  const setTimeGrain = (grain: TimeGrain | '') => {
    if (grain === '') {
      if (selectedTimeDimension) {
        setDimensions((prev) =>
          prev.map((item) =>
            item.column_id === selectedTimeDimension.column_id
              ? { ...item, time_grain: undefined }
              : item,
          ),
        );
      }
      return;
    }

    if (!selectedTimeDimension) {
      const primaryTimeCol =
        availableTimeColumns[0] || allColumns.find((col) => isTimeDimension(col));
      if (primaryTimeCol) {
        const alreadySelected = dimensions.some((d) => d.column_id === primaryTimeCol.column_id);
        if (alreadySelected) {
          setDimensions((prev) =>
            prev.map((d) =>
              d.column_id === primaryTimeCol.column_id ? { ...d, time_grain: grain } : d,
            ),
          );
        } else {
          setDimensions((prev) => [
            ...prev,
            { column_id: primaryTimeCol.column_id, time_grain: grain },
          ]);
        }
      }
      return;
    }

    setDimensions((prev) =>
      prev.map((item) =>
        item.column_id === selectedTimeDimension.column_id
          ? { ...item, time_grain: grain }
          : item,
      ),
    );
  };

  const handleReset = () => {
    setMetricIds([]);
    setDimensions([]);
    setMetricSearch('');
    setDimSearch('');
    setOutput(null);
    setError('');
  };

  const handleRemoveDashboardFilter = () => {
    setFilters([]);
    setDashboardFilterActive(false);
  };

  const formatApiErrorMessage = (err: unknown, fallback: string) => {
    if (err instanceof SemanticApiError) {
      const d = err.detail as Record<string, unknown> | null;
      if (d && typeof d === 'object' && typeof d.message === 'string') {
        return d.message;
      }
      return err.message;
    }
    return fallback;
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
      setError(formatApiErrorMessage(err, 'Không thể compile query.'));
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
      setError(formatApiErrorMessage(err, 'Lỗi thực thi Live DB.'));
    } finally {
      setLoading(false);
    }
  };

  const handleCopySql = () => {
    if (!output?.sql) return;
    void navigator.clipboard.writeText(output.sql);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  const handleExportCsv = () => {
    if (!output || !isQueryResult(output)) return;
    const header = output.columns
      .map((c) => formatColumnTitle(c, output.metadata, catalog, approved))
      .join(',');
    const rowsStr = output.rows.map((row) => row.map((v) => `"${String(v ?? '')}"`).join(','));
    const csvContent = 'data:text/csv;charset=utf-8,' + [header, ...rowsStr].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `semantic_query_export_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background text-foreground">
      <ViewHeader
        eyebrow="Explore"
        title="Metric Explorer"
        description="Compile approved metrics into safe queries — no manual SQL required."
        database={database}
      />

      <div className="flex min-h-0 flex-1">
        {/* Left Config Panel */}
        <div className="flex w-96 shrink-0 flex-col gap-4 overflow-y-auto border-r border-border p-4.5 bg-card/40">
          {/* Question Summary Banner */}
          <div className="rounded-xl border border-border bg-secondary/30 p-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-muted-foreground">
                CÂU HỎI PHÂN TÍCH HIỆN TẠI
              </span>
              {(metricIds.length > 0 || dimensions.length > 0) && (
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
                >
                  <RotateCcw className="h-2.5 w-2.5" />
                  <span>Đặt lại</span>
                </button>
              )}
            </div>
            {dashboardFilterActive && (
              <div className="mt-2 flex items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/10 px-2 py-1">
                <span className="text-[10px] font-semibold text-primary uppercase tracking-wider">
                  Bộ lọc từ Dashboard
                </span>
                <button
                  type="button"
                  onClick={handleRemoveDashboardFilter}
                  aria-label="Xóa bộ lọc từ Dashboard"
                  className="rounded-full p-0.5 text-primary hover:bg-primary/20 cursor-pointer"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
            <div className="mt-1.5 space-y-1">
              <p className="font-medium text-foreground leading-relaxed">
                {metricIds.length > 0 ? (
                  <span className="text-primary font-semibold">
                    Xem{' '}
                    {metricIds
                      .map((id) => approved.find((m) => m.metric_id === id)?.name || id)
                      .join(', ')}
                  </span>
                ) : (
                  <span className="text-muted-foreground italic">
                    Chưa chọn chỉ số (Chọn ít nhất 1 metric)
                  </span>
                )}
                {dimensions.length > 0 && (
                  <span className="text-foreground">
                    {' '}
                    theo{' '}
                    <span className="font-semibold">
                      {dimensions
                        .map((d) => {
                          const col = allColumns.find((c) => c.column_id === d.column_id);
                          const name = col?.business_name || col?.column_name || d.column_id;
                          return d.time_grain ? `${name} (${d.time_grain})` : name;
                        })
                        .join(', ')}
                    </span>
                  </span>
                )}
              </p>
            </div>
          </div>


          {/* 1. Metrics Selector */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <SectionLabel>1. CHỈ SỐ ĐO LƯỜNG ({approved.length})</SectionLabel>
              <span className="text-[10px] text-muted-foreground font-mono">Measures</span>
            </div>

            {/* Quick Search for Metrics */}
            {approved.length > 0 && (
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  value={metricSearch}
                  onChange={(e) => setMetricSearch(e.target.value)}
                  placeholder="Tìm nhanh chỉ số đo lường..."
                  className="h-8 pl-8 pr-8 text-xs bg-background"
                />
                {metricSearch && (
                  <button
                    type="button"
                    onClick={() => setMetricSearch('')}
                    className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}

            <div className="space-y-1.5">
              {displayedMetrics.map((m) => {
                const checked = metricIds.includes(m.metric_id);
                const formulaFn = m.definition?.metric.formula.function || 'SUM';
                return (
                  <label
                    key={m.metric_id}
                    className={cn(
                      'flex cursor-pointer items-center justify-between gap-2 rounded-lg border p-2 text-xs transition-all',
                      checked
                        ? 'border-primary bg-primary/10 text-foreground shadow-2xs'
                        : 'border-border bg-card text-muted-foreground hover:bg-accent/40 hover:text-foreground',
                    )}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleMetric(m.metric_id)}
                        className="h-3.5 w-3.5 rounded border-border accent-primary cursor-pointer"
                      />
                      <span className="font-medium truncate">{metricName(m)}</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="rounded bg-secondary/80 px-1.5 py-0.5 font-mono text-[9px] font-semibold text-primary">
                        {formulaFn}
                      </span>
                      {m.definition?.metric.base_entity && (
                        <span className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">
                          {m.definition.metric.base_entity}
                        </span>
                      )}
                    </div>
                  </label>
                );
              })}
              {approved.length === 0 && (
                <p className="p-2 text-xs text-muted-foreground italic">
                  Chưa có metric nào được phê duyệt. Hãy duyệt trong Catalog trước.
                </p>
              )}
              {approved.length > 0 && displayedMetrics.length === 0 && (
                <div className="p-3 text-center text-xs text-muted-foreground italic rounded-lg border border-dashed border-border bg-card/30">
                  Không tìm thấy metric nào khớp với &quot;{metricSearch}&quot;.
                </div>
              )}
            </div>
          </div>

          {/* 2. Chiều phân tích đã gắn trong chỉ số */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <SectionLabel>
                  2. CHIỀU PHÂN TÍCH ({metricDefinedDimensions.length})
                </SectionLabel>
              </div>
              <span className="text-[10px] text-primary font-medium font-mono">Tự động cấu hình bởi AI</span>
            </div>

            <div className="rounded-xl border border-border bg-card/40 p-3">
              {metricIds.length === 0 ? (
                <p className="text-xs text-muted-foreground italic text-center py-2">
                  Chọn một chỉ số ở mục 1 để xem các chiều phân tích đã được AI gắn sẵn.
                </p>
              ) : metricDefinedDimensions.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-[11px] text-muted-foreground">
                    Các chiều phân tích được AI xác nhận và tự động cấu hình cho chỉ số này:
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {metricDefinedDimensions.map((dim) => (
                      <span
                        key={dim.column_id}
                        className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary shadow-2xs"
                      >
                        <span>{dim.business_name}</span>
                        <span className="rounded bg-primary/20 px-1 py-0.2 font-mono text-[9px] text-primary">
                          {dim.table_name}
                        </span>
                      </span>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground italic text-center py-2">
                  Chỉ số này tính toán tổng hợp toàn bộ dữ liệu (chưa gắn chiều phân tích phụ).
                </p>
              )}
            </div>
          </div>

          {/* 3. Time Dimension & Grain */}
          <div className="space-y-2 rounded-xl border border-border bg-card/60 p-3.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <SectionLabel>3. CHIỀU THỜI GIAN & CHU KỲ</SectionLabel>
              <Calendar className="h-3.5 w-3.5 text-primary" />
            </div>

            {/* Time Column Picker */}
            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">
                Cột mốc thời gian (Time Dimension):
              </label>
              <select
                value={selectedTimeDimension?.column_id || ''}
                onChange={(e) => setTimeDimensionColumn(e.target.value)}
                className="h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus:border-primary"
              >
                <option value="">-- Không chọn mốc thời gian --</option>
                {availableTimeColumns.map((col) => {
                  const table = catalog.tables.find((t) =>
                    t.columns.some((c) => c.column_id === col.column_id),
                  );
                  return (
                    <option key={col.column_id} value={col.column_id}>
                      {table ? `${table.business_name || table.table_name} · ` : ''}
                      {col.business_name || col.column_name}
                    </option>
                  );
                })}
              </select>
            </div>

            {/* 5-Grain Buttons */}
            <div>
              <label className="text-[11px] text-muted-foreground block mb-1">
                Chu kỳ tổng hợp (Granularity):
              </label>
              <div className="grid grid-cols-5 gap-1">
                {TIME_GRAIN_OPTIONS.map((g) => {
                  const isActive = selectedTimeDimension?.time_grain === g.value;
                  return (
                    <button
                      key={g.value}
                      type="button"
                      onClick={() => setTimeGrain(isActive ? '' : g.value)}
                      className={cn(
                        'flex flex-col items-center justify-center rounded-md border py-1.5 text-xs transition-all cursor-pointer',
                        isActive
                          ? 'border-primary bg-primary text-primary-foreground font-semibold shadow-2xs'
                          : 'border-border bg-background text-muted-foreground hover:text-foreground hover:border-primary/40',
                      )}
                    >
                      <span className="text-[11px]">{g.label}</span>
                      <span className="text-[9px] font-mono opacity-70">{g.enLabel}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>


          {/* Action Buttons */}
          <div className="mt-auto space-y-2 pt-4 border-t border-border">
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                className="w-full gap-1.5 text-xs font-semibold"
                onClick={() => void runCompile()}
                disabled={!metricIds.length || loading}
              >
                <Eye className="h-3.5 w-3.5" />
                <span>Preview SQL</span>
              </Button>
              <Button
                className="w-full gap-1.5 text-xs font-semibold shadow-sm"
                onClick={() => void runExecute()}
                disabled={!metricIds.length || loading}
              >
                {loading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                <span>Thực thi (Execute)</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Right Results Panel */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
          {/* Result Tab Bar & Guardrails Badge */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-2.5 bg-secondary/15">
            <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1 shadow-2xs">
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
                      'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-all cursor-pointer',
                      viewTab === t.key
                        ? 'bg-primary text-primary-foreground font-semibold shadow-2xs'
                        : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{t.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Quick Actions (Copy / Export) */}
            <div className="flex items-center gap-3">
              {viewTab === 'table' && output && isQueryResult(output) && (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1 text-[11px]"
                  onClick={handleExportCsv}
                >
                  <Download className="h-3 w-3" />
                  <span>Xuất CSV</span>
                </Button>
              )}

              {viewTab === 'sql' && output?.sql && (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1 text-[11px]"
                  onClick={handleCopySql}
                >
                  {copiedSql ? (
                    <Check className="h-3 w-3 text-emerald-500" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  <span>{copiedSql ? 'Đã sao chép' : 'Sao chép SQL'}</span>
                </Button>
              )}

              <div className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground border-l border-border pl-3">
                <ShieldCheck className="h-4 w-4 text-emerald-500" />
                <span>Read-only · LIMIT 100 · max 1000 · 15s timeout</span>
              </div>
            </div>
          </div>

          {/* Results Area */}
          <div className="min-h-0 flex-1 overflow-auto p-6">
            {loading ? (
              <div className="flex h-full min-h-[360px] flex-col items-center justify-center gap-3 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-xs font-medium">Đang biên dịch & thực thi truy vấn an toàn...</p>
              </div>
            ) : error ? (
              <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-5 text-xs text-destructive">
                <div className="flex items-center gap-2 font-semibold text-sm">
                  <AlertTriangle className="h-4 w-4" />
                  <span>Lỗi truy vấn Semantic:</span>
                </div>
                <p className="mt-2 font-mono leading-relaxed bg-background/50 p-3 rounded-lg border border-destructive/20">
                  {error}
                </p>
              </div>
            ) : !output ? (
              <div className="flex h-full min-h-[360px] flex-col items-center justify-center gap-3 text-center text-muted-foreground">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-secondary/50 text-muted-foreground shadow-2xs">
                  <Play className="h-7 w-7 text-primary" />
                </div>
                <div className="max-w-md">
                  <p className="font-semibold text-foreground text-base">
                    Sẵn sàng biên dịch & phân tích số liệu
                  </p>
                  <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">
                    Chọn các chỉ số (Measures) và chiều phân tích (Dimensions / Time Grain) ở bảng điều khiển bên trái, sau đó nhấn <strong>Preview SQL</strong> hoặc <strong>Thực thi</strong>.
                  </p>
                </div>
              </div>
            ) : viewTab === 'table' ? (
              isQueryResult(output) ? (
                <div className="space-y-4">
                  <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-xs">
                        <thead>
                          <tr className="border-b border-border bg-secondary/60">
                            {output.columns.map((c, idx) => (
                              <th
                                key={c}
                                className={cn(
                                  'px-4 py-3 font-semibold uppercase tracking-wider text-muted-foreground',
                                  idx === 0 ? 'text-left' : 'text-right',
                                )}
                              >
                                {formatColumnTitle(c, output.metadata, catalog, approved)}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {output.rows.map((row, i) => (
                            <tr
                              key={i}
                              className="border-b border-border last:border-0 hover:bg-accent/40 transition-colors"
                            >
                              {output.columns.map((_, colIdx) => {
                                const val = row[colIdx];
                                const isNum =
                                  typeof val === 'number' ||
                                  (!isNaN(Number(val)) && val !== '' && val !== null);
                                return (
                                  <td
                                    key={colIdx}
                                    className={cn(
                                      'px-4 py-2.5 text-xs tabular-nums',
                                      colIdx === 0 ? 'text-left text-foreground' : 'text-right',
                                      isNum && colIdx > 0 ? 'font-medium font-mono text-foreground' : 'text-muted-foreground',
                                    )}
                                  >
                                    {colIdx === 0 ? formatDimensionValue(val) : formatCellValue(val)}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="flex items-center justify-between border-t border-border bg-secondary/30 px-4 py-2.5 text-xs text-muted-foreground">
                      <span>Hiển thị <strong>{output.rows.length}</strong> dòng kết quả</span>
                      <span className="font-mono text-[11px]">LIMIT {limit} applied</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-border bg-card p-8 text-center text-xs text-muted-foreground">
                  <p className="text-sm font-semibold text-foreground mb-1">
                    Bản xem trước SQL đã sẵn sàng
                  </p>
                  <p>Nhấn nút &quot;Thực thi (Execute)&quot; để nạp số liệu thực tế từ Live DB.</p>
                </div>
              )
            ) : viewTab === 'chart' ? (
              isQueryResult(output) && output.rows.length > 0 ? (
                <RechartsInteractiveStudio
                  rows={output.rows}
                  columns={output.columns}
                  metadata={output.metadata}
                  catalog={catalog}
                  metrics={approved}
                  chartType={chartType}
                  onChartTypeChange={setChartType}
                />
              ) : (
                <div className="rounded-xl border border-border bg-card p-8 text-center text-xs text-muted-foreground">
                  Chưa có dữ liệu đồ thị. Bấm &quot;Thực thi (Execute)&quot; để nạp số liệu từ Live DB.
                </div>
              )
            ) : (
              <div className="space-y-4">
                <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
                  <div className="flex items-center justify-between border-b border-border bg-secondary/40 px-4 py-2.5">
                    <SectionLabel>COMPILED SQL (READ-ONLY)</SectionLabel>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      Dialect-aware AST compiled
                    </span>
                  </div>
                  <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-foreground bg-secondary/10">
                    {output.sql}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatCellValue(val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'number') {
    return val.toLocaleString();
  }
  if (typeof val === 'string' && !isNaN(Number(val)) && val.trim() !== '') {
    const num = Number(val);
    return num.toLocaleString();
  }
  return String(val);
}

function RechartsInteractiveStudio({
  rows,
  columns,
  metadata,
  catalog,
  metrics,
  chartType,
  onChartTypeChange,
}: {
  rows: unknown[][];
  columns: string[];
  metadata?: Record<string, any>;
  catalog?: SemanticCatalog | null;
  metrics?: MetricRecord[];
  chartType: ChartType;
  onChartTypeChange: (t: ChartType) => void;
}) {
  const numericColIndices = useMemo(() => {
    const indices: number[] = [];
    columns.forEach((_, idx) => {
      const hasNumbers = rows.some(
        (r) =>
          typeof r[idx] === 'number' ||
          (!isNaN(Number(r[idx])) && r[idx] !== '' && r[idx] !== null),
      );
      if (hasNumbers) indices.push(idx);
    });
    return indices;
  }, [rows, columns]);

  const labelColIdx = useMemo(() => {
    const nonNumeric = columns.findIndex((_, idx) => !numericColIndices.includes(idx));
    return nonNumeric >= 0 ? nonNumeric : 0;
  }, [columns, numericColIndices]);

  const primaryNumericIdx = numericColIndices[0] ?? (columns.length > 1 ? 1 : 0);

  // Formatted names for dimension and metric
  const primaryMetricRaw = columns[primaryNumericIdx] || 'Chỉ số';
  const labelColRaw = columns[labelColIdx] || 'Chiều phân tích';

  const primaryMetricName = useMemo(
    () => formatColumnTitle(primaryMetricRaw, metadata, catalog, metrics),
    [primaryMetricRaw, metadata, catalog, metrics],
  );

  const labelColName = useMemo(
    () => formatColumnTitle(labelColRaw, metadata, catalog, metrics),
    [labelColRaw, metadata, catalog, metrics],
  );

  // Format data for Recharts with smart dimension values
  const chartData = useMemo(() => {
    return rows.slice(0, 30).map((r, i) => {
      const rawLabel = r[labelColIdx];
      const formattedLabel = formatDimensionValue(rawLabel) || `Mục ${i + 1}`;
      return {
        name: formattedLabel,
        rawName: String(rawLabel ?? ''),
        value: Number(r[primaryNumericIdx]) || 0,
      };
    });
  }, [rows, labelColIdx, primaryNumericIdx]);

  const values = useMemo(() => chartData.map((d) => d.value), [chartData]);
  const totalSum = useMemo(() => values.reduce((a, b) => a + b, 0), [values]);
  const avgVal = useMemo(() => (values.length ? totalSum / values.length : 0), [values, totalSum]);
  const maxVal = useMemo(() => (values.length ? Math.max(...values) : 1), [values]);
  const minVal = useMemo(() => (values.length ? Math.min(...values) : 0), [values]);

  return (
    <div className="space-y-6">
      {/* KPI Metric Summary Cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <span className="text-[11px] font-medium text-muted-foreground block truncate">
            Tổng {primaryMetricName}
          </span>
          <span className="mt-1 text-lg font-bold font-mono text-foreground block tabular-nums">
            {totalSum.toLocaleString()}
          </span>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <span className="text-[11px] font-medium text-muted-foreground block truncate">
            Trung bình mỗi {labelColName}
          </span>
          <span className="mt-1 text-lg font-bold font-mono text-foreground block tabular-nums">
            {avgVal.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <span className="text-[11px] font-medium text-muted-foreground block truncate">
            Cao nhất / Thấp nhất
          </span>
          <span className="mt-1 text-sm font-bold font-mono text-foreground block tabular-nums">
            {maxVal.toLocaleString()} / {minVal.toLocaleString()}
          </span>
        </div>
        <div className="rounded-xl border border-border bg-card p-4 shadow-2xs">
          <span className="text-[11px] font-medium text-muted-foreground block truncate">
            Số điểm dữ liệu ({labelColName})
          </span>
          <span className="mt-1 text-lg font-bold font-mono text-foreground block tabular-nums">
            {rows.length}
          </span>
        </div>
      </div>

      {/* Chart Canvas & Controls */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-xs space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
          <div>
            <h3 className="font-semibold text-foreground text-sm">
              Biểu đồ trực quan: {primaryMetricName} theo {labelColName}
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Phân tích xu hướng và tương quan dữ liệu
            </p>
          </div>

          {/* Chart Type Selector */}
          <div className="flex rounded-lg border border-border bg-background p-1 text-xs">
            {([
              { key: 'bar' as const, label: 'Cột', icon: BarChart3 },
              { key: 'line' as const, label: 'Đường', icon: LineChartIcon },
              { key: 'area' as const, label: 'Vùng', icon: AreaChartIcon },
              { key: 'pie' as const, label: 'Biểu đồ Tròn (Donut)', icon: PieChartIcon },
            ]).map((c) => {
              const Icon = c.icon;
              return (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => onChartTypeChange(c.key)}
                  className={cn(
                    'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition-colors cursor-pointer',
                    chartType === c.key
                      ? 'bg-primary text-primary-foreground font-semibold shadow-2xs'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{c.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="h-[340px] w-full pt-2">
          {chartType === 'bar' && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/40" />
                <XAxis
                  dataKey="name"
                  tickLine={false}
                  axisLine={false}
                  className="text-[11px] fill-muted-foreground font-medium"
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  className="text-[11px] font-mono fill-muted-foreground"
                  tickFormatter={formatShortNumber}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const item = payload[0];
                    return (
                      <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-semibold text-popover-foreground">{item.payload.name}</p>
                        <p className="font-mono text-primary font-medium mt-0.5">
                          {primaryMetricName}: {Number(item.value).toLocaleString()}
                        </p>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="value" fill="var(--color-primary, #6366f1)" radius={[6, 6, 0, 0]} maxBarSize={48} />
              </BarChart>
            </ResponsiveContainer>
          )}

          {chartType === 'line' && (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/40" />
                <XAxis
                  dataKey="name"
                  tickLine={false}
                  axisLine={false}
                  className="text-[11px] fill-muted-foreground font-medium"
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  className="text-[11px] font-mono fill-muted-foreground"
                  tickFormatter={formatShortNumber}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const item = payload[0];
                    return (
                      <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-semibold text-popover-foreground">{item.payload.name}</p>
                        <p className="font-mono text-primary font-medium mt-0.5">
                          {primaryMetricName}: {Number(item.value).toLocaleString()}
                        </p>
                      </div>
                    );
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="var(--color-primary, #6366f1)"
                  strokeWidth={3}
                  dot={{ r: 4, fill: 'var(--color-primary, #6366f1)' }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}

          {chartType === 'area' && (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
                <defs>
                  <linearGradient id="areaGradientRecharts" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-primary, #6366f1)" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="var(--color-primary, #6366f1)" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/40" />
                <XAxis
                  dataKey="name"
                  tickLine={false}
                  axisLine={false}
                  className="text-[11px] fill-muted-foreground font-medium"
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  className="text-[11px] font-mono fill-muted-foreground"
                  tickFormatter={formatShortNumber}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const item = payload[0];
                    return (
                      <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-semibold text-popover-foreground">{item.payload.name}</p>
                        <p className="font-mono text-primary font-medium mt-0.5">
                          {primaryMetricName}: {Number(item.value).toLocaleString()}
                        </p>
                      </div>
                    );
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="var(--color-primary, #6366f1)"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#areaGradientRecharts)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}

          {chartType === 'pie' && (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart margin={{ top: 10, right: 20, left: 20, bottom: 10 }}>
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const item = payload[0];
                    const val = Number(item.value) || 0;
                    const pct = totalSum > 0 ? ((val / totalSum) * 100).toFixed(1) : '0';
                    return (
                      <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
                        <p className="font-semibold text-popover-foreground">{item.name}</p>
                        <p className="font-mono text-primary font-medium mt-0.5">
                          {primaryMetricName}: {val.toLocaleString()} ({pct}%)
                        </p>
                      </div>
                    );
                  }}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value) => (
                    <span className="text-xs font-medium text-foreground">{value}</span>
                  )}
                />
                <Pie
                  data={chartData.slice(0, 10)}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="45%"
                  innerRadius={65}
                  outerRadius={105}
                  paddingAngle={3}
                  stroke="var(--color-background, #fff)"
                  strokeWidth={2}
                >
                  {chartData.slice(0, 10).map((_, index) => (
                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}

function isQueryResult(
  output: SemanticQueryResult | SemanticQueryPreview | null,
): output is SemanticQueryResult {
  return Boolean(
    output && 'rows' in output && Array.isArray((output as SemanticQueryResult).rows),
  );
}
