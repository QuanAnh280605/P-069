/**
 * Pure formatting and normalization helpers for dashboard widgets.
 * Adapted from MetricExplorerView behaviors without importing private symbols.
 */

export interface DashboardPoint {
  /** Display-ready label (Vietnamese formatting applied). */
  label: string;
  /** Raw string form of the dimension value, used for time sorting. */
  rawLabel: string;
  /** Numeric value used by charts (missing values normalized to 0). */
  value: number;
  /** Original cell value preserved for accessible/table rendering. */
  rawValue: unknown;
}

export interface WidgetLabelContext {
  metricName: string;
  dimensionLabel: string | null;
}

export const PIE_MAX_SLICES = 8;
export const RANKING_MAX_ROWS = 100;

const MISSING_TEXT = '—';
const EMPTY_LABEL = '(Trống)';
const REMAINDER_LABEL = 'Khác';

function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/** Format a number using Vietnamese conventions (dot groups, comma decimals). */
export function formatNumberVi(value: number): string {
  if (!Number.isFinite(value)) return MISSING_TEXT;
  const sign = value < 0 ? '-' : '';
  const [intRaw, fracRaw] = Math.abs(value).toFixed(2).split('.');
  const frac = fracRaw.replace(/0+$/, '');
  return `${sign}${groupThousands(intRaw)}${frac ? `,${frac}` : ''}`;
}

function compactVi(value: number, divisor: number): string {
  const scaled = (value / divisor).toFixed(1);
  return (scaled.endsWith('.0') ? scaled.slice(0, -2) : scaled).replace('.', ',');
}

/** Compact large numbers with Vietnamese magnitude suffixes (Tỷ/Tr/K). */
export function formatShortNumber(value: number): string {
  if (!Number.isFinite(value)) return MISSING_TEXT;
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_000_000_000) return `${sign}${compactVi(abs, 1_000_000_000)} Tỷ`;
  if (abs >= 1_000_000) return `${sign}${compactVi(abs, 1_000_000)} Tr`;
  if (abs >= 1_000) return `${sign}${compactVi(abs, 1_000)} K`;
  return formatNumberVi(value);
}

function cleanupAggregationTitle(alias: string): string {
  const sumMatch = alias.match(/^SUM\((.+)\)$/i);
  if (sumMatch) return `Tổng ${sumMatch[1]}`;
  const avgMatch = alias.match(/^AVG\((.+)\)$/i);
  if (avgMatch) return `Trung bình ${avgMatch[1]}`;
  const countMatch = alias.match(/^COUNT\((.+)\)$/i);
  if (countMatch) return `Số lượng ${countMatch[1]}`;
  return alias;
}

/**
 * Resolve a compiler alias (`metric_{id}` / `dimension_{id}`) into a human
 * label using only configuration-known names — no compile round-trip needed.
 */
export function resolveColumnLabel(alias: string, context: WidgetLabelContext): string {
  if (!alias) return '';
  const dimensionMatch = alias.match(/^dimension_(\d+)$/i);
  if (dimensionMatch) return context.dimensionLabel ?? `Chiều ${dimensionMatch[1]}`;
  if (/^metric_\d+$/i.test(alias)) return context.metricName;
  return cleanupAggregationTitle(alias);
}

function formatTemporalText(str: string): string | null {
  const dateMatch = str.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (dateMatch) return `${dateMatch[3]}/${dateMatch[2]}/${dateMatch[1]}`;
  const monthMatch = str.match(/^(\d{4})-(\d{2})$/);
  if (monthMatch) return `Tháng ${monthMatch[2]}/${monthMatch[1]}`;
  const weekMatch = str.match(/^(\d{4})-W(\d{1,2})$/i);
  if (weekMatch) return `Tuần ${weekMatch[2]}/${weekMatch[1]}`;
  const quarterMatch = str.match(/^(\d{4})-Q(\d)$/i);
  if (quarterMatch) return `Quý ${quarterMatch[2]}/${quarterMatch[1]}`;
  if (/^\d{4}$/.test(str)) {
    const year = Number(str);
    if (year >= 1990 && year <= 2100) return `Năm ${str}`;
  }
  return null;
}

/** Format categorical / temporal dimension values with Vietnamese labels. */
export function formatDimensionValue(val: unknown): string {
  if (val === null || val === undefined || val === '') return EMPTY_LABEL;
  const str = String(val).trim();
  if (val === true || str.toLowerCase() === 'true') return 'Có';
  if (val === false || str.toLowerCase() === 'false') return 'Không';
  return formatTemporalText(str) ?? str;
}

/** Format arbitrary result cells with null safety for tables. */
export function formatCellValue(val: unknown): string {
  if (val === null || val === undefined || val === '') return MISSING_TEXT;
  if (typeof val === 'boolean') return val ? 'Có' : 'Không';
  if (typeof val === 'number') return formatNumberVi(val);
  if (typeof val === 'string') {
    const parsed = parseFiniteNumber(val);
    if (parsed !== null) return formatNumberVi(parsed);
  }
  return String(val);
}

/** Parse a finite number from raw cells; missing or non-numeric yields null. */
export function parseFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

/**
 * Parse canonical time-truncation outputs into a comparable key tuple.
 * Works across dialects (e.g. SQLite `2024-01`, Postgres `2024-01-01 …`).
 */
export function parseTimeSortKey(value: unknown): number[] | null {
  if (value instanceof Date) return [value.getUTCFullYear(), value.getUTCMonth() + 1, value.getUTCDate()];
  if (typeof value !== 'string') return null;
  const str = value.trim();
  const dayMatch = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ].*)?$/);
  if (dayMatch) return dayMatch.slice(1).map(Number);
  const monthMatch = str.match(/^(\d{4})-(\d{1,2})$/);
  if (monthMatch) return monthMatch.slice(1).map(Number);
  const quarterMatch = str.match(/^(\d{4})-Q([1-4])$/i);
  if (quarterMatch) return [Number(quarterMatch[1]), Number(quarterMatch[2])];
  const weekMatch = str.match(/^(\d{4})-W(\d{1,2})$/i);
  if (weekMatch) return [Number(weekMatch[1]), Number(weekMatch[2])];
  if (/^\d{4}$/.test(str)) return [Number(str)];
  return null;
}

/** Compare two parsed time keys element-wise; shorter (coarser) sorts first. */
export function compareTimeKeys(a: number[], b: number[]): number {
  const shared = Math.min(a.length, b.length);
  for (let i = 0; i < shared; i += 1) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

interface KeyedEntry {
  index: number;
  key: number[] | null;
}

function compareKeyedEntries(left: KeyedEntry, right: KeyedEntry): number {
  if (left.key && right.key) {
    const compared = compareTimeKeys(left.key, right.key);
    if (compared !== 0) return compared;
  } else if (left.key && !right.key) return -1;
  else if (!left.key && right.key) return 1;
  return left.index - right.index;
}

/** Stable ascending sort of rows by a time column; unparseable rows go last. */
export function sortRowsByTimeColumn(rows: unknown[][], columnIndex: number): unknown[][] {
  return rows
    .map((row, index) => ({ row, index, key: parseTimeSortKey(row[columnIndex]) }))
    .sort(compareKeyedEntries)
    .map((entry) => entry.row);
}

/** Stable ascending sort of points by their raw label's time key. */
export function sortPointsByTimeKey(points: DashboardPoint[]): DashboardPoint[] {
  return points
    .map((point, index) => ({ point, index, key: parseTimeSortKey(point.rawLabel) }))
    .sort(compareKeyedEntries)
    .map((entry) => entry.point);
}

/** Stable descending sort by numeric value. */
export function sortPointsByValueDesc(points: DashboardPoint[]): DashboardPoint[] {
  return points
    .map((point, index) => ({ point, index }))
    .sort((left, right) => right.point.value - left.point.value || left.index - right.index)
    .map((entry) => entry.point);
}

/** Sort descending, keep the top slices, aggregate overflow into "Khác". */
export function truncatePieSlices(
  points: DashboardPoint[],
  maxSlices: number = PIE_MAX_SLICES,
): DashboardPoint[] {
  const ordered = sortPointsByValueDesc(points);
  if (ordered.length <= maxSlices) return ordered;
  const kept = ordered.slice(0, Math.max(1, maxSlices - 1));
  const remainder = ordered.slice(kept.length);
  const remainderValue = remainder.reduce((sum, item) => sum + item.value, 0);
  return [
    ...kept,
    { label: REMAINDER_LABEL, rawLabel: '', value: remainderValue, rawValue: remainderValue },
  ];
}

/** Sort descending and cap ranking tables at the bounded row limit. */
export function truncateRankingRows(
  points: DashboardPoint[],
  maxRows: number = RANKING_MAX_ROWS,
): { rows: DashboardPoint[]; hiddenCount: number } {
  const ordered = sortPointsByValueDesc(points);
  return {
    rows: ordered.slice(0, maxRows),
    hiddenCount: Math.max(0, ordered.length - maxRows),
  };
}
