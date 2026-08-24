/**
 * Query construction and bounded execution for dashboard widgets.
 * Requests always flow through `executeSemanticQueryApi`; the Target DB is
 * never contacted directly from the client.
 */

import {
  executeSemanticQueryApi,
  SemanticQueryFilter,
  SemanticQueryRequest,
  SemanticQueryResult,
  TimeGrain,
} from '@/lib/api';
import {
  buildDateRangeFilters,
  DashboardDatePreset,
  DashboardWidgetConfig,
  resolveDatePresetBounds,
} from '@/lib/dashboard';

import {
  compareTimeKeys,
  DashboardPoint,
  formatDimensionValue,
  parseFiniteNumber,
  parseTimeSortKey,
} from './dashboardFormatters';

export const WIDGET_ROW_LIMIT = 100;
export const MAX_CONCURRENT_WIDGET_QUERIES = 6;
export const KPI_TREND_DEFAULT_GRAIN: TimeGrain = 'month';

/** Raised when a persisted widget cannot be translated into valid queries. */
export class DashboardWidgetConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DashboardWidgetConfigError';
  }
}

type ReleaseFunction = () => void;

let activeExecutions = 0;
const waitingCallers: ReleaseFunction[] = [];

/**
 * Module-level scheduler shared by every dashboard card: at most three
 * semantic executions may be in flight at any moment.
 */
export async function scheduleWidgetExecution<T>(task: () => Promise<T>): Promise<T> {
  if (activeExecutions >= MAX_CONCURRENT_WIDGET_QUERIES) {
    await new Promise<void>((resolve) => waitingCallers.push(resolve));
  }
  activeExecutions += 1;
  try {
    return await task();
  } finally {
    const next = waitingCallers.shift();
    if (next) next();
    else activeExecutions -= 1;
  }
}

/** Test hook: clears queued waiters and resets the in-flight counter. */
export function resetWidgetQueryScheduler(): void {
  activeExecutions = 0;
  waitingCallers.length = 0;
}

/** Execute one widget request through the bounded scheduler. */
export async function runWidgetExecution(
  dbId: string,
  request: SemanticQueryRequest,
): Promise<SemanticQueryResult> {
  return scheduleWidgetExecution(() => executeSemanticQueryApi(dbId, request));
}

/** Global grain wins over the persisted widget grain. */
export function resolveEffectiveGrain(
  widgetGrain: TimeGrain | null,
  globalGrain: TimeGrain | null,
): TimeGrain | null {
  return globalGrain ?? widgetGrain;
}

/** Emit date-preset filters only for widgets that opted into a date column. */
export function emitWidgetDateFilters(
  widget: DashboardWidgetConfig,
  datePreset: DashboardDatePreset | null,
  now: Date,
): SemanticQueryFilter[] {
  if (!datePreset || widget.date_filter_column_id === null) return [];
  return buildDateRangeFilters(widget.date_filter_column_id, resolveDatePresetBounds(datePreset, now));
}

export interface BuildWidgetRequestsInput {
  widget: DashboardWidgetConfig;
  globalGrain: TimeGrain | null;
  datePreset: DashboardDatePreset | null;
  now?: Date;
}

/**
 * Build the execution plan for one widget: KPI returns a total request plus a
 * trend request; every other chart returns exactly one request.
 */
export function buildWidgetQueryRequests(input: BuildWidgetRequestsInput): SemanticQueryRequest[] {
  assertWidgetQueryable(input.widget, input.globalGrain);
  const filters = emitWidgetDateFilters(input.widget, input.datePreset, input.now ?? new Date());
  if (input.widget.chart_type === 'kpi') {
    return buildKpiRequests(input.widget, filters, input.globalGrain);
  }
  return [buildSingleRequest(input.widget, filters, input.globalGrain)];
}

function assertWidgetQueryable(widget: DashboardWidgetConfig, globalGrain: TimeGrain | null): void {
  if (widget.chart_type === 'kpi') {
    if (widget.date_filter_column_id === null) {
      throw new DashboardWidgetConfigError('KPI widgets require date_filter_column_id');
    }
    return;
  }
  if (widget.dimension_col_id === null) {
    throw new DashboardWidgetConfigError(`${widget.chart_type} widgets require dimension_col_id`);
  }
  if (
    (widget.chart_type === 'line' || widget.chart_type === 'area') &&
    resolveEffectiveGrain(widget.time_grain, globalGrain) === null
  ) {
    throw new DashboardWidgetConfigError('Time-series charts require a resolvable time grain');
  }
}

function buildKpiRequests(
  widget: DashboardWidgetConfig,
  filters: SemanticQueryFilter[],
  globalGrain: TimeGrain | null,
): SemanticQueryRequest[] {
  const dateColumnId = widget.date_filter_column_id;
  if (dateColumnId === null) {
    throw new DashboardWidgetConfigError('KPI widgets require date_filter_column_id');
  }
  const grain = resolveEffectiveGrain(null, globalGrain) ?? KPI_TREND_DEFAULT_GRAIN;
  return [
    { metric_ids: [widget.metric_id], filters, limit: 1 },
    {
      metric_ids: [widget.metric_id],
      dimensions: [{ column_id: dateColumnId, time_grain: grain }],
      filters,
      limit: WIDGET_ROW_LIMIT,
    },
  ];
}

function buildSingleRequest(
  widget: DashboardWidgetConfig,
  filters: SemanticQueryFilter[],
  globalGrain: TimeGrain | null,
): SemanticQueryRequest {
  const dimensionId = widget.dimension_col_id ?? -1;
  if (widget.chart_type === 'bar' || widget.chart_type === 'pie' || widget.chart_type === 'table') {
    return {
      metric_ids: [widget.metric_id],
      dimensions: [{ column_id: dimensionId }],
      filters,
      limit: WIDGET_ROW_LIMIT,
    };
  }
  return {
    metric_ids: [widget.metric_id],
    dimensions: [
      { column_id: dimensionId, time_grain: resolveEffectiveGrain(widget.time_grain, globalGrain) },
    ],
    filters,
    limit: WIDGET_ROW_LIMIT,
  };
}

export interface BuildWidgetPointsInput {
  result: SemanticQueryResult;
  metricId: number;
  dimensionId: number | null;
  sortByTime: boolean;
}

/** Map a raw result into display points with null safety and time sorting. */
export function buildWidgetPoints(input: BuildWidgetPointsInput): DashboardPoint[] {
  const columns = Array.isArray(input.result.columns) ? input.result.columns : [];
  const rows = Array.isArray(input.result.rows) ? input.result.rows : [];
  const valueIndex = resolveValueColumnIndex(columns, input.metricId);
  const labelIndex = resolveLabelColumnIndex(columns, input.dimensionId, valueIndex);
  const points = rows.map((row) => toPoint(row, labelIndex, valueIndex));
  return input.sortByTime ? sortPointsByTimeKey(points) : points;
}

function sortPointsByTimeKey(points: DashboardPoint[]): DashboardPoint[] {
  return points
    .map((point, index) => ({ point, index, key: parseTimeSortKey(point.rawLabel) }))
    .sort((left, right) => compareKeyed(left, right))
    .map((entry) => entry.point);
}

interface KeyedPointEntry {
  point: DashboardPoint;
  index: number;
  key: number[] | null;
}

function compareKeyed(left: KeyedPointEntry, right: KeyedPointEntry): number {
  if (left.key && right.key) {
    const compared = compareTimeKeys(left.key, right.key);
    if (compared !== 0) return compared;
  } else if (left.key && !right.key) return -1;
  else if (!left.key && right.key) return 1;
  return left.index - right.index;
}

function toPoint(
  row: unknown[],
  labelIndex: number,
  valueIndex: number,
): DashboardPoint {
  const rawLabel = row[labelIndex];
  const rawValue = row[valueIndex];
  return {
    label: formatDimensionValue(rawLabel),
    rawLabel: rawLabel === null || rawLabel === undefined ? '' : String(rawLabel),
    value: parseFiniteNumber(rawValue) ?? 0,
    rawValue: rawValue ?? null,
  };
}

function resolveValueColumnIndex(columns: string[], metricId: number): number {
  const aliasIndex = columns.indexOf(`metric_${metricId}`);
  if (aliasIndex >= 0) return aliasIndex;
  return columns.length > 1 ? columns.length - 1 : 0;
}

function resolveLabelColumnIndex(
  columns: string[],
  dimensionId: number | null,
  valueIndex: number,
): number {
  if (dimensionId !== null) {
    const aliasIndex = columns.indexOf(`dimension_${dimensionId}`);
    if (aliasIndex >= 0) return aliasIndex;
  }
  const fallback = columns.findIndex((_, index) => index !== valueIndex);
  return fallback >= 0 ? fallback : 0;
}

/** Strictly extract the KPI total; missing or non-numeric cells yield null. */
export function extractTotalValue(result: SemanticQueryResult, metricId: number): number | null {
  const columns = Array.isArray(result.columns) ? result.columns : [];
  const rows = Array.isArray(result.rows) ? result.rows : [];
  const aliasIndex = columns.indexOf(`metric_${metricId}`);
  const valueIndex = aliasIndex >= 0 ? aliasIndex : Math.max(0, columns.length - 1);
  if (rows.length === 0) return null;
  return parseFiniteNumber(rows[0][valueIndex]);
}
