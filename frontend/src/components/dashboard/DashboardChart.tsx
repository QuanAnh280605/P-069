'use client';

/**
 * Theme-aware dashboard widget renderer for KPI, line, area, bar, pie, and
 * ranking-table charts. Colors come from theme CSS variables only; every
 * chart ships an accessible textual fallback.
 */

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

import {
  DashboardChartType,
  DashboardWidgetConfig,
} from '@/lib/dashboard';
import { cn } from '@/lib/utils';

import {
  DashboardPoint,
  formatCellValue,
  formatNumberVi,
  formatShortNumber,
  PIE_MAX_SLICES,
  sortPointsByTimeKey,
  truncatePieSlices,
} from './dashboardFormatters';
import { DashboardWidgetData } from './useDashboardWidgetData';

export interface DashboardChartProps {
  widget: DashboardWidgetConfig;
  title: string;
  metricName: string;
  dimensionLabel: string | null;
  data: DashboardWidgetData;
}

const SERIES_COLORS = [1, 2, 3, 4, 5].map((n) => `var(--color-chart-${n})`);
const CHART_MARGIN = { top: 8, right: 12, left: 0, bottom: 4 };

function axisTickFormatter(value: unknown): string {
  return formatShortNumber(Number(value));
}

/** Render one dashboard widget visualization body including states and fallbacks. */
export function DashboardChart({ widget, title, metricName, dimensionLabel, data }: DashboardChartProps) {
  return (
    <div className="flex h-full w-full min-h-0 min-w-0 flex-1 flex-col">
      <WidgetBody
        widget={widget}
        title={title}
        metricName={metricName}
        dimensionLabel={dimensionLabel}
        data={data}
      />
    </div>
  );
}

function WidgetBody(props: DashboardChartProps) {
  const { widget, title, metricName, dimensionLabel, data } = props;
  if (data.status === 'idle') return <UnavailableState />;
  if (data.status === 'loading') return <LoadingSkeleton label={title} />;
  if (data.status === 'error') {
    return (
      <ErrorState
        message={data.errorMessage}
        isConfiguration={data.isConfigurationError}
        onRetry={data.retry}
      />
    );
  }
  if (isMissingData(widget.chart_type, data)) return <EmptyState />;
  return (
    <SuccessBody
      widget={widget}
      title={title}
      metricName={metricName}
      dimensionLabel={dimensionLabel}
      data={data}
    />
  );
}

function isMissingData(chartType: DashboardChartType, data: DashboardWidgetData): boolean {
  if (chartType === 'kpi') return data.totalValue === null && data.trendPoints.length === 0;
  return data.points.length === 0;
}

function SuccessBody({ widget, title, metricName, dimensionLabel, data }: DashboardChartProps) {
  if (widget.chart_type === 'kpi') {
    return (
      <>
        <KpiPanel metricName={metricName} data={data} />
        <SummaryTable title={title} metricName={metricName} points={data.trendPoints} />
      </>
    );
  }
  if (widget.chart_type === 'table') {
    return (
      <RankingTable title={title} metricName={metricName} dimensionLabel={dimensionLabel} data={data} />
    );
  }
  return (
    <>
      {widget.chart_type === 'pie' ? (
        <PiePanel metricName={metricName} points={data.points} />
      ) : (
        <CartesianPanel chartType={widget.chart_type} metricName={metricName} points={data.points} />
      )}
      <SummaryTable title={title} metricName={metricName} points={data.points} />
    </>
  );
}

function LoadingSkeleton({ label }: { label: string }) {
  return (
    <div role="status" aria-busy="true" className="flex h-full flex-col gap-2">
      <span className="sr-only">Đang tải {label}</span>
      <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
      <div className="min-h-0 flex-1 animate-pulse rounded-lg bg-muted" />
    </div>
  );
}

function ErrorState({
  message,
  isConfiguration,
  onRetry,
}: {
  message: string | null;
  isConfiguration: boolean;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex h-full flex-col justify-center gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3"
    >
      <p className="text-sm font-medium text-destructive">
        {isConfiguration ? 'Cấu hình widget không hợp lệ.' : 'Không thể tải dữ liệu cho widget này.'}
      </p>
      {message && <p className="break-words text-xs text-muted-foreground">{message}</p>}
      <button
        type="button"
        onClick={onRetry}
        className="self-start rounded-md border border-border px-3 py-1 text-xs font-medium text-foreground hover:bg-accent"
      >
        Thử lại
      </button>
    </div>
  );
}

function EmptyState() {
  return (
    <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
      Chưa có dữ liệu cho phạm vi đã chọn.
    </p>
  );
}

function UnavailableState() {
  return (
    <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
      Truy vấn không khả dụng cho nguồn dữ liệu này.
    </p>
  );
}

function KpiPanel({ metricName, data }: { metricName: string; data: DashboardWidgetData }) {
  const total = data.totalValue;
  return (
    <div className="flex min-h-0 flex-1 flex-col justify-between gap-2">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Tổng trong kỳ
        </p>
        <p
          className="mt-1 text-2xl font-bold tabular-nums text-foreground"
          title={total === null ? undefined : formatNumberVi(total)}
        >
          {total === null ? '—' : formatNumberVi(total)}
        </p>
      </div>
      <div className="h-12 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data.trendPoints} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--color-chart-1)"
              strokeWidth={2}
              fill="var(--color-chart-1)"
              fillOpacity={0.15}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <p className="sr-only">{trendSummary(metricName, data.trendPoints)}</p>
    </div>
  );
}

function trendSummary(metricName: string, points: DashboardPoint[]): string {
  if (points.length === 0) return `Chưa có dữ liệu xu hướng cho ${metricName}.`;
  const detail = points.map((point) => `${point.label}: ${formatCellValue(point.rawValue)}`).join('; ');
  return `Xu hướng ${metricName}: ${detail}`;
}

function SummaryTable({
  title,
  metricName,
  points,
}: {
  title: string;
  metricName: string;
  points: DashboardPoint[];
}) {
  return (
    <table className="sr-only">
      <caption>{title}</caption>
      <thead>
        <tr>
          <th scope="col">Mục</th>
          <th scope="col">{metricName}</th>
        </tr>
      </thead>
      <tbody>
        {points.map((point) => (
          <tr key={`${point.rawLabel}-${point.label}`}>
            <th scope="row">{point.label}</th>
            <td>{formatCellValue(point.rawValue)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ChartAxes() {
  return (
    <>
      <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/40" />
      <XAxis
        dataKey="label"
        tickLine={false}
        axisLine={false}
        interval={0}
        angle={-20}
        textAnchor="end"
        height={48}
        tick={{ fontSize: 10 }}
        className="fill-muted-foreground"
      />
      <YAxis
        tickLine={false}
        axisLine={false}
        width={52}
        tickFormatter={axisTickFormatter}
        tick={{ fontSize: 10 }}
        className="fill-muted-foreground"
      />
    </>
  );
}

function TooltipCard({
  active,
  payload,
  label,
  metricName,
}: {
  active?: boolean;
  payload?: Array<{ value?: unknown }>;
  label?: unknown;
  metricName: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-popover-foreground">{String(label ?? '')}</p>
      <p className="mt-0.5 font-mono font-medium text-primary">
        {metricName}: {formatCellValue(payload[0]?.value)}
      </p>
    </div>
  );
}

function CartesianPanel({
  chartType,
  metricName,
  points,
}: {
  chartType: 'line' | 'area' | 'bar';
  metricName: string;
  points: DashboardPoint[];
}) {
  const ordered = chartType === 'bar' ? points : sortPointsByTimeKey(points);
  return (
    <div className="min-h-0 flex-1">
      <ResponsiveContainer width="100%" height="100%">
        {chartType === 'bar' ? (
          <BarChart data={ordered} margin={CHART_MARGIN}>
            <ChartAxes />
            <Tooltip content={<TooltipCard metricName={metricName} />} />
            <Bar
              dataKey="value"
              fill="var(--color-chart-1)"
              radius={[4, 4, 0, 0]}
              maxBarSize={40}
              isAnimationActive={false}
            />
          </BarChart>
        ) : chartType === 'line' ? (
          <LineChart data={ordered} margin={CHART_MARGIN}>
            <ChartAxes />
            <Tooltip content={<TooltipCard metricName={metricName} />} />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--color-chart-1)"
              strokeWidth={2.5}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        ) : (
          <AreaChart data={ordered} margin={CHART_MARGIN}>
            <ChartAxes />
            <Tooltip content={<TooltipCard metricName={metricName} />} />
            <Area
              type="monotone"
              dataKey="value"
              stroke="var(--color-chart-1)"
              strokeWidth={2}
              fill="var(--color-chart-1)"
              fillOpacity={0.18}
              isAnimationActive={false}
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function PiePanel({ metricName, points }: { metricName: string; points: DashboardPoint[] }) {
  const sliced = truncatePieSlices(points).slice(0, PIE_MAX_SLICES);
  return (
    <div className="min-h-0 flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
          <Tooltip content={<TooltipCard metricName={metricName} />} />
          <Legend
            verticalAlign="bottom"
            height={24}
            formatter={(value) => <span className="text-xs text-foreground">{value}</span>}
          />
          <Pie
            data={sliced}
            dataKey="value"
            nameKey="label"
            innerRadius="55%"
            outerRadius="80%"
            paddingAngle={2}
            stroke="var(--color-card)"
            strokeWidth={1}
            isAnimationActive={false}
          >
            {sliced.map((point, index) => (
              <Cell key={`${point.rawLabel}-${point.label}`} fill={SERIES_COLORS[index % SERIES_COLORS.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function RankingTable({
  title,
  metricName,
  dimensionLabel,
  data,
}: {
  title: string;
  metricName: string;
  dimensionLabel: string | null;
  data: DashboardWidgetData;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{title}</caption>
          <RankingHeader dimensionLabel={dimensionLabel} metricName={metricName} />
          <tbody>
            {data.points.map((point, index) => (
              <tr key={`${point.rawLabel}-${index}`} className="border-b border-border/60">
                <td className="px-2 py-1.5 tabular-nums text-muted-foreground">{index + 1}</td>
                <th scope="row" className="px-2 py-1.5 font-normal text-foreground">{point.label}</th>
                <td className="px-2 py-1.5 text-right tabular-nums text-foreground">
                  {formatCellValue(point.rawValue)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.hiddenCount > 0 && (
        <p className="pt-2 text-xs text-muted-foreground">+{data.hiddenCount} mục khác không hiển thị</p>
      )}
    </div>
  );
}

function RankingHeader({
  dimensionLabel,
  metricName,
}: {
  dimensionLabel: string | null;
  metricName: string;
}) {
  return (
    <thead className="sticky top-0 bg-card">
      <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
        <th scope="col" className="px-2 py-2 font-medium">#</th>
        <th scope="col" className="px-2 py-2 font-medium">{dimensionLabel ?? 'Mục'}</th>
        <th scope="col" className="px-2 py-2 text-right font-medium">{metricName}</th>
      </tr>
    </thead>
  );
}
