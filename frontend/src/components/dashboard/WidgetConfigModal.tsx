'use client';

/**
 * Accessible modal for creating or editing one dashboard widget. Metrics are
 * restricted to approved canonical-v2 definitions, dependent selections reset
 * whenever the metric or chart type changes, and previews run through the
 * shared bounded query engine only on an explicit "Xem trước" action.
 */

import { useCallback, useMemo, useState } from 'react';

import {
  FilterColumnItem,
  MetricRecord,
  RecommendedDimensionItem,
  TimeGrain,
} from '@/lib/api';
import { DashboardChartType, DashboardWidgetConfig } from '@/lib/dashboard';
import { cn } from '@/lib/utils';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

import { DashboardChart } from './DashboardChart';
import { useDashboardWidgetData, DashboardWidgetData } from './useDashboardWidgetData';
import { useWidgetConfigMeta } from './useWidgetConfigMeta';
import {
  buildWidgetDraft,
  CHART_LABELS,
  createWidgetId,
  filterMetricsByName,
  GRAIN_LABELS,
  HEIGHT_LABELS,
  initFormState,
  PREVIEW_PLACEHOLDER_WIDGET,
  recommendChartForDimensionItem,
  selectExecutableMetrics,
  SELECT_CLASS,
  stateForChartChange,
  validateForm,
  WidgetFormState,
  WidgetMeta,
  WIDTH_LABELS,
} from './widgetConfigForm';

export interface WidgetConfigModalProps {
  open: boolean;
  dbId: number | string;
  querySupported: boolean;
  metrics: MetricRecord[];
  editingWidget: DashboardWidgetConfig | null;
  onSave: (widget: DashboardWidgetConfig) => void;
  onCancel: () => void;
}

/** Gate rendering so every open starts from a fresh, correctly seeded form. */
export function WidgetConfigModal(props: WidgetConfigModalProps) {
  if (!props.open) return null;
  return (
    <WidgetConfigModalInner
      key={props.editingWidget?.id ?? 'new-widget'}
      {...props}
    />
  );
}

function WidgetConfigModalInner(props: WidgetConfigModalProps) {
  const eligibleMetrics = useMemo(() => selectExecutableMetrics(props.metrics), [props.metrics]);
  const [form, setForm] = useState<WidgetFormState>(() =>
    initFormState(props.editingWidget, eligibleMetrics),
  );
  const [widgetId] = useState(() => props.editingWidget?.id ?? createWidgetId());
  const [previewWidget, setPreviewWidget] = useState<DashboardWidgetConfig | null>(null);
  const sanitizeOnLoad = useCallback((meta: WidgetMeta) => {
    const dimensionIds = new Set(meta.dimensions.map((item) => item.column_id));
    const timeIds = new Set(
      meta.columns.filter((column) => column.is_time_dimension).map((column) => column.column_id),
    );
    setForm((prev) => ({
      ...prev,
      dimensionColId:
        prev.dimensionColId !== null && dimensionIds.has(prev.dimensionColId) ? prev.dimensionColId : null,
      dateFilterColumnId:
        prev.dateFilterColumnId !== null && timeIds.has(prev.dateFilterColumnId)
          ? prev.dateFilterColumnId
          : null,
    }));
  }, []);
  const { currentMeta, errorMessage: metaError, loading: loadingMeta } = useWidgetConfigMeta(
    form.metricId,
    props.dbId,
    sanitizeOnLoad,
  );

  const timeColumns = useMemo(
    () => (currentMeta ? currentMeta.columns.filter((column) => column.is_time_dimension) : []),
    [currentMeta],
  );
  const dimensionIsTime =
    form.dimensionColId !== null && timeColumns.some((column) => column.column_id === form.dimensionColId);
  const validationMessage = validateForm(form);
  const canSave = validationMessage === null && !loadingMeta && metaError === null;

  const previewData = useDashboardWidgetData({
    dbId: props.dbId,
    widget: previewWidget ?? PREVIEW_PLACEHOLDER_WIDGET,
    globalGrain: null,
    datePreset: null,
    refreshGeneration: 0,
    enabled: previewWidget !== null && props.querySupported,
  });

  const handleMetricChange = useCallback((value: string) => {
    const metricId = value === '' ? null : Number(value);
    setForm((prev) => ({ ...prev, metricId, dimensionColId: null, dateFilterColumnId: null, timeGrain: null }));
  }, []);

  const handleChartChange = useCallback(
    (value: string) => {
      const nextChart = value as DashboardChartType;
      setForm((prev) => stateForChartChange(prev, nextChart, dimensionIsTime));
    },
    [dimensionIsTime],
  );

  const patchForm = useCallback((patch: Partial<WidgetFormState>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  }, []);

  const runPreview = useCallback(() => {
    if (!canSave || form.metricId === null) return;
    setPreviewWidget(buildWidgetDraft(widgetId, form));
  }, [canSave, form, widgetId]);

  const handleSave = useCallback(() => {
    if (!canSave || form.metricId === null) return;
    props.onSave(buildWidgetDraft(widgetId, form));
  }, [canSave, form, widgetId, props]);

  const selectedMetric =
    eligibleMetrics.find((metric) => metric.metric_id === form.metricId) ?? null;

  return (
    <Dialog open onOpenChange={(next) => { if (!next) props.onCancel(); }}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-base font-semibold">
            {props.editingWidget ? 'Chỉnh sửa widget' : 'Thêm widget mới'}
          </DialogTitle>
          <DialogDescription>
            Cấu hình widget từ metric đã duyệt. Dữ liệu chỉ được truy vấn khi bấm “Xem trước”.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <MetricPicker metrics={eligibleMetrics} value={form.metricId} onChange={handleMetricChange} />
          <FormField label="Loại biểu đồ" id="widget-chart">
            <select
              id="widget-chart"
              className={SELECT_CLASS}
              value={form.chartType}
              onChange={(event) => handleChartChange(event.target.value)}
            >
              {(Object.keys(CHART_LABELS) as DashboardChartType[]).map((chart) => (
                <option key={chart} value={chart}>{CHART_LABELS[chart]}</option>
              ))}
            </select>
          </FormField>
          {form.chartType !== 'kpi' && (
            <DimensionField
              form={form}
              dimensions={currentMeta?.dimensions ?? []}
              timeColumns={timeColumns}
              recommendation={resolveRecommendation(form, currentMeta)}
              onSelect={(dimensionColId) => patchForm({ dimensionColId })}
            />
          )}
          {(form.chartType === 'line' || form.chartType === 'area') && (
            <FormField label="Mốc thời gian" id="widget-grain">
              <select
                id="widget-grain"
                className={SELECT_CLASS}
                value={form.timeGrain ?? ''}
                onChange={(event) => patchForm({ timeGrain: (event.target.value || null) as TimeGrain | null })}
              >
                {(Object.keys(GRAIN_LABELS) as TimeGrain[]).map((grain) => (
                  <option key={grain} value={grain}>{GRAIN_LABELS[grain]}</option>
                ))}
              </select>
            </FormField>
          )}
          <DateFilterField
            timeColumns={timeColumns}
            value={form.dateFilterColumnId}
            required={form.chartType === 'kpi'}
            onChange={(dateFilterColumnId) => patchForm({ dateFilterColumnId })}
          />
          <LayoutFields form={form} onPatch={patchForm} />
          <PreviewPanel
            querySupported={props.querySupported}
            canPreview={canSave && props.querySupported}
            previewWidget={previewWidget}
            metricName={selectedMetric?.name ?? null}
            dimensionLabel={resolveDimensionLabel(form, currentMeta, timeColumns)}
            data={previewData}
            onPreview={runPreview}
          />
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
          {metaError ? (
            <p role="alert" className="flex-1 text-xs font-medium text-destructive">{metaError}</p>
          ) : validationMessage ? (
            <p role="alert" className="flex-1 text-xs font-medium text-destructive">{validationMessage}</p>
          ) : (
            <p className="flex-1" />
          )}
          <Button type="button" variant="outline" onClick={props.onCancel}>Hủy</Button>
          <Button type="button" disabled={!canSave} onClick={handleSave}>Lưu</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function resolveRecommendation(
  form: WidgetFormState,
  meta: WidgetMeta | null,
): DashboardChartType | null {
  if (form.chartType !== 'bar' && form.chartType !== 'pie' && form.chartType !== 'table') return null;
  const item = meta?.dimensions.find((candidate) => candidate.column_id === form.dimensionColId);
  return item ? recommendChartForDimensionItem(item) : null;
}

function resolveDimensionLabel(
  form: WidgetFormState,
  meta: WidgetMeta | null,
  timeColumns: FilterColumnItem[],
): string | null {
  if (form.chartType === 'kpi') return null;
  const categorical = meta?.dimensions.find((item) => item.column_id === form.dimensionColId);
  if (categorical) return categorical.business_name;
  const time = timeColumns.find((column) => column.column_id === form.dimensionColId);
  return time?.business_name ?? null;
}

function FormField({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id} className="text-xs font-medium text-muted-foreground">{label}</Label>
      {children}
    </div>
  );
}

function MetricPicker({
  metrics,
  value,
  onChange,
}: {
  metrics: MetricRecord[];
  value: number | null;
  onChange: (value: string) => void;
}) {
  const [search, setSearch] = useState('');
  const filtered = filterMetricsByName(metrics, search);
  return (
    <div className="flex flex-col gap-3">
      <FormField label="Tìm metric" id="widget-metric-search">
        <Input
          id="widget-metric-search"
          type="text"
          placeholder="Tìm metric đã duyệt…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </FormField>
      <FormField label="Metric" id="widget-metric">
        <select
          id="widget-metric"
          className={SELECT_CLASS}
          value={value === null ? '' : String(value)}
          onChange={(event) => onChange(event.target.value)}
        >
          {filtered.map((metric) => (
            <option key={metric.metric_id} value={String(metric.metric_id)}>{metric.name}</option>
          ))}
        </select>
      </FormField>
      {filtered.length === 0 && (
        <p className="text-xs text-muted-foreground">Không có metric đã duyệt nào.</p>
      )}
    </div>
  );
}

function DimensionField({
  form,
  dimensions,
  timeColumns,
  recommendation,
  onSelect,
}: {
  form: WidgetFormState;
  dimensions: RecommendedDimensionItem[];
  timeColumns: FilterColumnItem[];
  recommendation: DashboardChartType | null;
  onSelect: (columnId: number | null) => void;
}) {
  const isTimeSeries = form.chartType === 'line' || form.chartType === 'area';
  const label = isTimeSeries ? 'Cột thời gian' : 'Chiều dữ liệu';
  const options = isTimeSeries
    ? timeColumns.map((column) => ({ id: column.column_id, name: column.business_name }))
    : dimensions.map((item) => ({ id: item.column_id, name: item.business_name }));
  return (
    <FormField label={label} id="widget-dimension">
      <div className="flex items-center gap-2">
        <select
          id="widget-dimension"
          className={cn(SELECT_CLASS, 'flex-1')}
          value={form.dimensionColId === null ? '' : String(form.dimensionColId)}
          onChange={(event) => onSelect(event.target.value === '' ? null : Number(event.target.value))}
        >
          <option value="">— Chọn —</option>
          {options.map((option) => (
            <option key={option.id} value={String(option.id)}>{option.name}</option>
          ))}
        </select>
        {recommendation && (
          <span className="whitespace-nowrap rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
            Đề xuất: {CHART_LABELS[recommendation]}
          </span>
        )}
      </div>
    </FormField>
  );
}

function DateFilterField({
  timeColumns,
  value,
  required,
  onChange,
}: {
  timeColumns: FilterColumnItem[];
  value: number | null;
  required: boolean;
  onChange: (columnId: number | null) => void;
}) {
  return (
    <FormField label="Cột lọc ngày" id="widget-date-filter">
      <select
        id="widget-date-filter"
        className={SELECT_CLASS}
        aria-required={required}
        value={value === null ? '' : String(value)}
        onChange={(event) => onChange(event.target.value === '' ? null : Number(event.target.value))}
      >
        {!required && <option value="">Không áp dụng</option>}
        {timeColumns.map((column) => (
          <option key={column.column_id} value={String(column.column_id)}>{column.business_name}</option>
        ))}
      </select>
    </FormField>
  );
}

function LayoutFields({
  form,
  onPatch,
}: {
  form: WidgetFormState;
  onPatch: (patch: Partial<WidgetFormState>) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <FormField label="Độ rộng" id="widget-width">
        <select
          id="widget-width"
          className={SELECT_CLASS}
          value={form.width}
          onChange={(event) => onPatch({ width: event.target.value as typeof form.width })}
        >
          {(Object.keys(WIDTH_LABELS) as (keyof typeof WIDTH_LABELS)[]).map((width) => (
            <option key={width} value={width}>{WIDTH_LABELS[width]}</option>
          ))}
        </select>
      </FormField>
      <FormField label="Chiều cao" id="widget-height">
        <select
          id="widget-height"
          className={SELECT_CLASS}
          value={form.height}
          onChange={(event) => onPatch({ height: event.target.value as typeof form.height })}
        >
          {(Object.keys(HEIGHT_LABELS) as (keyof typeof HEIGHT_LABELS)[]).map((height) => (
            <option key={height} value={height}>{HEIGHT_LABELS[height]}</option>
          ))}
        </select>
      </FormField>
      <div className="sm:col-span-2">
        <FormField label="Tiêu đề widget" id="widget-title">
          <Input
            id="widget-title"
            type="text"
            maxLength={200}
            placeholder="Bỏ trống để dùng tên metric"
            value={form.title}
            onChange={(event) => onPatch({ title: event.target.value })}
          />
        </FormField>
      </div>
    </div>
  );
}

function PreviewPanel({
  querySupported,
  canPreview,
  previewWidget,
  metricName,
  dimensionLabel,
  data,
  onPreview,
}: {
  querySupported: boolean;
  canPreview: boolean;
  previewWidget: DashboardWidgetConfig | null;
  metricName: string | null;
  dimensionLabel: string | null;
  data: DashboardWidgetData;
  onPreview: () => void;
}) {
  return (
    <section className="rounded-lg border border-border bg-secondary/30 p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">Xem trước</h3>
        <Button type="button" size="sm" variant="outline" disabled={!canPreview} onClick={onPreview}>
          Xem trước
        </Button>
      </div>
      {!querySupported ? (
        <p
          role="note"
          className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-600 dark:text-amber-400"
        >
          Nguồn SQL Dump chỉ chứa metadata cấu trúc và không hỗ trợ truy vấn trực tiếp. Không thể xem
          trước dữ liệu Live DB cho nguồn này.
        </p>
      ) : previewWidget ? (
        <>
          <p className="mt-1 text-xs text-muted-foreground">
            Dữ liệu mẫu truy vấn trực tiếp từ Live DB (tối đa 100 dòng).
          </p>
          <div className="mt-2 h-64 rounded-xl border border-border bg-card p-3 flex flex-col">
            <DashboardChart
              widget={previewWidget}
              title={previewWidget.custom_title ?? metricName ?? 'Widget'}
              metricName={metricName ?? ''}
              dimensionLabel={dimensionLabel}
              data={data}
            />
          </div>
        </>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">
          Hoàn tất cấu hình hợp lệ rồi nhấn “Xem trước” để chạy truy vấn mẫu.
        </p>
      )}
    </section>
  );
}
