/**
 * Pure form logic for the widget configuration modal: eligibility filtering,
 * chart-compatibility state transitions, validation, and canonical draft
 * building. No React or network access lives here.
 */

import {
  FilterColumnItem,
  MetricRecord,
  RecommendedDimensionItem,
  TimeGrain,
} from '@/lib/api';
import {
  DashboardChartType,
  DashboardWidgetConfig,
  DashboardWidgetHeight,
  DashboardWidgetWidth,
  recommendDashboardChartType,
} from '@/lib/dashboard';

export interface WidgetFormState {
  metricId: number | null;
  chartType: DashboardChartType;
  dimensionColId: number | null;
  dateFilterColumnId: number | null;
  timeGrain: TimeGrain | null;
  width: DashboardWidgetWidth;
  height: DashboardWidgetHeight;
  title: string;
}

export interface WidgetMeta {
  metricId: number;
  dimensions: RecommendedDimensionItem[];
  columns: FilterColumnItem[];
}

export const CHART_LABELS: Record<DashboardChartType, string> = {
  kpi: 'KPI',
  line: 'Biểu đồ đường',
  area: 'Biểu đồ vùng',
  bar: 'Biểu đồ cột',
  pie: 'Biểu đồ tròn',
  table: 'Bảng xếp hạng',
};

export const WIDTH_LABELS: Record<DashboardWidgetWidth, string> = {
  third: '1/3 lưới',
  half: '1/2 lưới',
  full: 'Đầy đủ chiều rộng',
};

export const HEIGHT_LABELS: Record<DashboardWidgetHeight, string> = {
  compact: 'Gọn',
  normal: 'Vừa',
  expanded: 'Cao',
};

export const GRAIN_LABELS: Record<TimeGrain, string> = {
  day: 'Ngày',
  week: 'Tuần',
  month: 'Tháng',
  quarter: 'Quý',
  year: 'Năm',
};

export const SELECT_CLASS =
  'h-9 cursor-pointer rounded-md border border-border bg-background px-2 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-50';

export const PREVIEW_PLACEHOLDER_WIDGET: DashboardWidgetConfig = {
  id: 'preview-placeholder',
  metric_id: 0,
  dimension_col_id: null,
  date_filter_column_id: null,
  time_grain: null,
  chart_type: 'kpi',
  width: 'third',
  height: 'compact',
  custom_title: null,
};

const NEW_FORM: WidgetFormState = {
  metricId: null,
  chartType: 'kpi',
  dimensionColId: null,
  dateFilterColumnId: null,
  timeGrain: null,
  width: 'third',
  height: 'normal',
  title: '',
};

/** Only approved canonical-v2 metrics without diagnostics are executable. */
export function selectExecutableMetrics(metrics: MetricRecord[]): MetricRecord[] {
  return metrics.filter(
    (metric) =>
      metric.status === 'approved' &&
      metric.definition !== null &&
      metric.definition.schema_version === 2 &&
      !(metric.definition.diagnostics && metric.definition.diagnostics.length > 0),
  );
}

export function filterMetricsByName(metrics: MetricRecord[], search: string): MetricRecord[] {
  const query = search.trim().toLowerCase();
  if (!query) return metrics;
  return metrics.filter((metric) => metric.name.toLowerCase().includes(query));
}

function normalizeTitle(value: string): string | null {
  const normalized = value.trim();
  if (!normalized) return null;
  return normalized.slice(0, 200);
}

export function initFormState(
  editing: DashboardWidgetConfig | null,
  eligible: MetricRecord[],
): WidgetFormState {
  if (!editing) return NEW_FORM;
  const known = eligible.some((metric) => metric.metric_id === editing.metric_id);
  return {
    metricId: known ? editing.metric_id : null,
    chartType: editing.chart_type,
    dimensionColId: editing.dimension_col_id,
    dateFilterColumnId: editing.date_filter_column_id,
    timeGrain: editing.time_grain,
    width: editing.width,
    height: editing.height,
    title: editing.custom_title ?? '',
  };
}

/** Drop dependent selections that become incompatible with the new chart. */
export function stateForChartChange(
  prev: WidgetFormState,
  nextChart: DashboardChartType,
  dimensionIsTime: boolean,
): WidgetFormState {
  if (nextChart === 'kpi') {
    return { ...prev, chartType: nextChart, dimensionColId: null, timeGrain: null };
  }
  if (nextChart === 'line' || nextChart === 'area') {
    return { ...prev, chartType: nextChart, dimensionColId: dimensionIsTime ? prev.dimensionColId : null };
  }
  return {
    ...prev,
    chartType: nextChart,
    dimensionColId: dimensionIsTime ? null : prev.dimensionColId,
    timeGrain: null,
  };
}

/** Mirror of the persisted-layout compatibility rules used for validation. */
export function validateForm(form: WidgetFormState): string | null {
  if (form.metricId === null) return 'Hãy chọn một metric đã duyệt.';
  if (form.chartType === 'kpi') {
    if (form.dateFilterColumnId === null) return 'KPI cần một cột thời gian để lọc theo ngày.';
    return null;
  }
  if (form.chartType === 'line' || form.chartType === 'area') {
    if (form.dimensionColId === null) return 'Biểu đồ thời gian cần một cột thời gian.';
    if (form.timeGrain === null) return 'Hãy chọn mốc thời gian cho biểu đồ thời gian.';
    return null;
  }
  if (form.dimensionColId === null) return 'Biểu đồ cần một chiều dữ liệu phân loại.';
  return null;
}

export function buildWidgetDraft(id: string, form: WidgetFormState): DashboardWidgetConfig {
  const isTimeSeries = form.chartType === 'line' || form.chartType === 'area';
  return {
    id,
    metric_id: form.metricId ?? 0,
    dimension_col_id: form.dimensionColId,
    date_filter_column_id: form.dateFilterColumnId,
    time_grain: isTimeSeries ? form.timeGrain : null,
    chart_type: form.chartType,
    width: form.width,
    height: form.height,
    custom_title: normalizeTitle(form.title),
  };
}

function toCatalogColumn(item: RecommendedDimensionItem) {
  return {
    column_id: item.column_id,
    column_name: item.column_name,
    business_name: item.business_name,
    data_type: item.data_type,
    is_time_dimension: false,
    allowed_values: item.cardinality_hint ? Array.from({ length: item.cardinality_hint }) : null,
  };
}

/** Deterministic recommendation (no LLM): reuses the canonical rules. */
export function recommendChartForDimensionItem(item: RecommendedDimensionItem): DashboardChartType {
  return recommendDashboardChartType(toCatalogColumn(item));
}

export function createWidgetId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `w-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
