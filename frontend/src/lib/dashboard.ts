import {
  CatalogColumn,
  CatalogTable,
  MetricDefinition,
  MetricRecord,
  SemanticCatalog,
  SemanticQueryFilter,
  TimeGrain,
} from '@/lib/api';
import { isBusinessDimension, isTimeDimension } from '@/lib/dimensions';

export type DashboardChartType = 'kpi' | 'line' | 'area' | 'bar' | 'pie' | 'table';
export type DashboardWidgetWidth = 'third' | 'half' | 'full';
export type DashboardWidgetHeight = 'compact' | 'normal' | 'expanded';

export interface DashboardWidgetConfig {
  id: string;
  metric_id: number;
  dimension_col_id: number | null;
  date_filter_column_id: number | null;
  time_grain: TimeGrain | null;
  chart_type: DashboardChartType;
  width: DashboardWidgetWidth;
  height: DashboardWidgetHeight;
  col_span?: number;
  row_span?: number;
  custom_title: string | null;
}

export interface DashboardLayout {
  widgets: DashboardWidgetConfig[];
}

export interface DashboardLayoutState {
  db_id: number;
  layout: DashboardLayout | null;
  version: number;
  updated_at: string | null;
  updated_by: number | null;
}

export const DASHBOARD_MAX_WIDGETS = 24;
export const DASHBOARD_GRID_COLUMNS = 24;
export const DASHBOARD_ROW_HEIGHT_PX = 40;
export const DASHBOARD_WIDTH_SPAN: Record<DashboardWidgetWidth, number> = {
  third: 8,
  half: 12,
  full: 24,
};
export const DASHBOARD_HEIGHT_ROWS: Record<DashboardWidgetHeight, number> = {
  compact: 5,
  normal: 7,
  expanded: 10,
};

export function getWidgetColSpan(widget: DashboardWidgetConfig): number {
  if (typeof widget.col_span === 'number' && widget.col_span >= 1 && widget.col_span <= 24) {
    return widget.col_span;
  }
  return DASHBOARD_WIDTH_SPAN[widget.width] ?? 12;
}

export function getWidgetRowSpan(widget: DashboardWidgetConfig): number {
  if (typeof widget.row_span === 'number' && widget.row_span >= 1 && widget.row_span <= 48) {
    return widget.row_span;
  }
  return DASHBOARD_HEIGHT_ROWS[widget.height] ?? 7;
}

export function colSpanToWidth(colSpan: number): DashboardWidgetWidth {
  if (colSpan <= 8) return 'third';
  if (colSpan <= 16) return 'half';
  return 'full';
}

export function rowSpanToHeight(rowSpan: number): DashboardWidgetHeight {
  if (rowSpan <= 5) return 'compact';
  if (rowSpan <= 8) return 'normal';
  return 'expanded';
}
export const DASHBOARD_STARTER_WIDGET_LIMIT = 5;

export type DashboardDatePreset =
  | 'last_7_days'
  | 'last_30_days'
  | 'last_90_days'
  | 'this_month'
  | 'this_quarter'
  | 'this_year';

export const DASHBOARD_DATE_PRESETS: DashboardDatePreset[] = [
  'last_7_days',
  'last_30_days',
  'last_90_days',
  'this_month',
  'this_quarter',
  'this_year',
];

export interface DashboardDateRange {
  start: string;
  endExclusive: string;
}

export class DashboardLayoutParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DashboardLayoutParseError';
  }
}

const CHART_TYPES: readonly DashboardChartType[] = ['kpi', 'line', 'area', 'bar', 'pie', 'table'];
const WIDGET_WIDTHS: readonly DashboardWidgetWidth[] = ['third', 'half', 'full'];
const WIDGET_HEIGHTS: readonly DashboardWidgetHeight[] = ['compact', 'normal', 'expanded'];
const TIME_GRAINS: readonly TimeGrain[] = ['day', 'week', 'month', 'quarter', 'year'];

function requireRecord(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new DashboardLayoutParseError(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0;
}

function parseColumnReference(value: unknown, label: string): number | null {
  if (value === undefined || value === null) return null;
  if (!isPositiveInteger(value)) {
    throw new DashboardLayoutParseError(`${label} must be a positive integer or null`);
  }
  return value;
}

function parseRequiredEnum<T extends string>(value: unknown, allowed: readonly T[], label: string): T {
  if (typeof value === 'string' && (allowed as readonly string[]).includes(value)) {
    return value as T;
  }
  throw new DashboardLayoutParseError(`Unsupported ${label}: ${String(value)}`);
}

function parseOptionalEnum<T extends string>(value: unknown, allowed: readonly T[], label: string): T | null {
  if (value === undefined || value === null) return null;
  return parseRequiredEnum(value, allowed, label);
}

function parseCustomTitle(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'string') {
    throw new DashboardLayoutParseError('custom_title must be a string or null');
  }
  const normalized = value.trim();
  if (normalized.length > 200) {
    throw new DashboardLayoutParseError('custom_title exceeds 200 characters');
  }
  return normalized || null;
}

function assertChartCompatibility(widget: DashboardWidgetConfig): void {
  if (widget.chart_type === 'kpi') {
    if (widget.date_filter_column_id === null) {
      throw new DashboardLayoutParseError('KPI widgets require date_filter_column_id');
    }
    if (widget.dimension_col_id !== null || widget.time_grain !== null) {
      throw new DashboardLayoutParseError('KPI widgets must not define a dimension column or time grain');
    }
    return;
  }
  if (widget.chart_type === 'line' || widget.chart_type === 'area') {
    if (widget.dimension_col_id === null || widget.time_grain === null) {
      throw new DashboardLayoutParseError('Line and area charts require a time dimension and grain');
    }
    return;
  }
  if (widget.dimension_col_id === null) {
    throw new DashboardLayoutParseError('Bar, pie, and table charts require a categorical dimension');
  }
}

function parseDimensionSpan(value: unknown, min: number, max: number, label: string): number | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'number' || !Number.isInteger(value) || value < min || value > max) {
    throw new DashboardLayoutParseError(`${label} must be an integer between ${min} and ${max}`);
  }
  return value;
}

function parseDashboardWidget(raw: unknown): DashboardWidgetConfig {
  const record = requireRecord(raw, 'widget');
  if (typeof record.id !== 'string' || record.id.length < 1 || record.id.length > 64) {
    throw new DashboardLayoutParseError('Widget id must be a string of 1-64 characters');
  }
  if (!isPositiveInteger(record.metric_id)) {
    throw new DashboardLayoutParseError('Widget metric_id must be a positive integer');
  }
  const colSpan = parseDimensionSpan(record.col_span, 1, 24, 'col_span');
  const rowSpan = parseDimensionSpan(record.row_span, 1, 48, 'row_span');
  const widget: DashboardWidgetConfig = {
    id: record.id,
    metric_id: record.metric_id,
    dimension_col_id: parseColumnReference(record.dimension_col_id, 'dimension_col_id'),
    date_filter_column_id: parseColumnReference(record.date_filter_column_id, 'date_filter_column_id'),
    time_grain: parseOptionalEnum(record.time_grain, TIME_GRAINS, 'time_grain'),
    chart_type: parseRequiredEnum(record.chart_type, CHART_TYPES, 'chart_type'),
    width: parseRequiredEnum(record.width, WIDGET_WIDTHS, 'width'),
    height: parseRequiredEnum(record.height, WIDGET_HEIGHTS, 'height'),
    ...(colSpan !== null ? { col_span: colSpan } : {}),
    ...(rowSpan !== null ? { row_span: rowSpan } : {}),
    custom_title: parseCustomTitle(record.custom_title),
  };
  assertChartCompatibility(widget);
  return widget;
}

function parseDashboardLayout(raw: unknown): DashboardLayout {
  const record = requireRecord(raw, 'layout');
  if (!Array.isArray(record.widgets)) {
    throw new DashboardLayoutParseError('layout.widgets must be an array');
  }
  if (record.widgets.length > DASHBOARD_MAX_WIDGETS) {
    throw new DashboardLayoutParseError(`A layout holds at most ${DASHBOARD_MAX_WIDGETS} widgets`);
  }
  const widgets = record.widgets.map(parseDashboardWidget);
  const seenIds = new Set<string>();
  for (const widget of widgets) {
    if (seenIds.has(widget.id)) {
      throw new DashboardLayoutParseError(`Duplicate widget id: ${widget.id}`);
    }
    seenIds.add(widget.id);
  }
  return { widgets };
}

export function parseDashboardLayoutPayload(payload: unknown): DashboardLayoutState {
  const record = requireRecord(payload, 'dashboard state');
  const dbId = record.db_id;
  const version = record.version;
  if (typeof dbId !== 'number' || !Number.isInteger(dbId) || dbId < 0) {
    throw new DashboardLayoutParseError('db_id must be a non-negative integer');
  }
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 0) {
    throw new DashboardLayoutParseError('version must be a non-negative integer');
  }
  if (record.updated_at !== null && record.updated_at !== undefined && typeof record.updated_at !== 'string') {
    throw new DashboardLayoutParseError('updated_at must be a string or null');
  }
  if (
    record.updated_by !== null &&
    record.updated_by !== undefined &&
    !isPositiveInteger(record.updated_by)
  ) {
    throw new DashboardLayoutParseError('updated_by must be a positive integer or null');
  }
  return {
    db_id: dbId,
    layout: record.layout === null || record.layout === undefined ? null : parseDashboardLayout(record.layout),
    version,
    updated_at: record.updated_at ?? null,
    updated_by: record.updated_by ?? null,
  };
}

export function recommendDashboardChartType(dimension: CatalogColumn | null): DashboardChartType {
  if (!dimension) return 'kpi';
  if (isTimeDimension(dimension)) return 'line';
  const allowedValues = dimension.allowed_values;
  if (Array.isArray(allowedValues) && allowedValues.length >= 1 && allowedValues.length <= 6) {
    return 'pie';
  }
  return 'bar';
}

function findBaseTable(catalog: SemanticCatalog, definition: MetricDefinition): CatalogTable | null {
  const entity = definition.metric.base_entity;
  const entityId = definition.metric.base_entity_id ?? null;
  return (
    catalog.tables.find(
      (candidate) => candidate.table_name === entity || (entityId !== null && candidate.table_id === entityId),
    ) ?? null
  );
}

function starterWidgetFor(
  metric: MetricRecord,
  table: CatalogTable,
  isFirstCard: boolean,
): DashboardWidgetConfig | null {
  const base = {
    id: `starter-${metric.metric_id}`,
    metric_id: metric.metric_id,
    custom_title: null,
  };
  const timeColumn = table.columns.find((column) => isTimeDimension(column)) ?? null;
  if (timeColumn) {
    if (isFirstCard) {
      return {
        ...base,
        dimension_col_id: null,
        date_filter_column_id: timeColumn.column_id,
        time_grain: null,
        chart_type: 'kpi',
        width: 'third',
        height: 'compact',
      };
    }
    return {
      ...base,
      dimension_col_id: timeColumn.column_id,
      date_filter_column_id: timeColumn.column_id,
      time_grain: 'month',
      chart_type: 'line',
      width: 'half',
      height: 'normal',
    };
  }
  const dimension = table.columns.find((column) => isBusinessDimension(column)) ?? null;
  if (!dimension) return null;
  const chartType = recommendDashboardChartType(dimension);
  return {
    ...base,
    dimension_col_id: dimension.column_id,
    date_filter_column_id: null,
    time_grain: null,
    chart_type: chartType,
    width: chartType === 'table' ? 'full' : 'third',
    height: 'normal',
  };
}

export function buildStarterDashboardWidgets(input: {
  metrics: MetricRecord[];
  catalog: SemanticCatalog | null;
}): DashboardWidgetConfig[] {
  if (!input.catalog) return [];
  const widgets: DashboardWidgetConfig[] = [];
  for (const item of input.metrics) {
    if (widgets.length >= DASHBOARD_STARTER_WIDGET_LIMIT) break;
    const definition = item.definition;
    if (item.status !== 'approved' || !definition || definition.schema_version !== 2) continue;
    if (!Array.isArray(definition.metric.filters)) continue;
    if (definition.diagnostics && definition.diagnostics.length > 0) continue;
    const table = findBaseTable(input.catalog, definition);
    if (!table) continue;
    const widget = starterWidgetFor(item, table, widgets.length === 0);
    if (widget) widgets.push(widget);
  }
  return widgets.slice(0, DASHBOARD_STARTER_WIDGET_LIMIT);
}

export function formatDateOnlyUtc(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function addDaysUtc(date: Date, days: number): Date {
  const shifted = new Date(date.getTime());
  shifted.setUTCDate(shifted.getUTCDate() + days);
  return shifted;
}

function utcDayStart(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

function rollingBounds(today: Date, days: number): DashboardDateRange {
  return {
    start: formatDateOnlyUtc(addDaysUtc(today, -(days - 1))),
    endExclusive: formatDateOnlyUtc(addDaysUtc(today, 1)),
  };
}

function calendarBounds(today: Date, startMonthOffset: number, monthsAhead: number): DashboardDateRange {
  const year = today.getUTCFullYear();
  return {
    start: formatDateOnlyUtc(new Date(Date.UTC(year, startMonthOffset, 1))),
    endExclusive: formatDateOnlyUtc(new Date(Date.UTC(year, startMonthOffset + monthsAhead, 1))),
  };
}

export function resolveDatePresetBounds(preset: DashboardDatePreset, now: Date): DashboardDateRange {
  const today = utcDayStart(now);
  switch (preset) {
    case 'last_7_days':
      return rollingBounds(today, 7);
    case 'last_30_days':
      return rollingBounds(today, 30);
    case 'last_90_days':
      return rollingBounds(today, 90);
    case 'this_month':
      return calendarBounds(today, today.getUTCMonth(), 1);
    case 'this_quarter':
      return calendarBounds(today, Math.floor(today.getUTCMonth() / 3) * 3, 3);
    case 'this_year':
      return calendarBounds(today, 0, 12);
  }
}

export function buildDateRangeFilters(columnId: number, range: DashboardDateRange): SemanticQueryFilter[] {
  return [
    { column_id: columnId, operator: 'gte', value: range.start },
    { column_id: columnId, operator: 'lt', value: range.endExclusive },
  ];
}

/**
 * Resolve the date filters a Dashboard drill-down should push into the Explorer.
 * The Dashboard's viewer-local date preset is honored; a null preset means
 * all-time (no runtime date filter), and a widget without a date column also
 * yields no filters.
 */
export function resolveDrillDownDateFilters(
  widget: DashboardWidgetConfig,
  datePreset: DashboardDatePreset | null,
  now: Date,
): SemanticQueryFilter[] {
  if (widget.date_filter_column_id === null || datePreset === null) return [];
  return buildDateRangeFilters(
    widget.date_filter_column_id,
    resolveDatePresetBounds(datePreset, now),
  );
}
