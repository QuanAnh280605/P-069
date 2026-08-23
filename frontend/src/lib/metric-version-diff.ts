import type { MetricDefinition, MetricFilter } from '@/lib/api';

/** Change status of a single display line in a metric version diff. */
export type DiffRowStatus = 'unchanged' | 'removed' | 'added';

/** One rendered line of the diff, tagged with its change status. */
export interface DiffRow {
  status: DiffRowStatus;
  text: string;
}

/**
 * Result of comparing two metric versions.
 *
 * `available: false` means at least one side has no usable definition
 * (legacy versions store `definition: null`), so no line diff can be built.
 */
export type MetricVersionDiffResult =
  | { available: true; rows: DiffRow[] }
  | { available: false };

/**
 * Build deterministic display lines for one metric definition.
 *
 * Only the formula and filters are rendered — never raw SQL or arbitrary JSON.
 * The formula line comes first (`FUNC(expression)`), followed by filter lines
 * sorted lexicographically so equal definitions always produce equal lines
 * regardless of filter array order. Returns `null` for legacy null definitions.
 */
export function buildMetricVersionLines(
  definition: MetricDefinition | null | undefined,
): string[] | null {
  if (!definition?.metric?.formula) return null;
  const lines = [`${definition.metric.formula.function}(${definition.metric.formula.expression})`];
  const filterLines = (definition.metric.filters ?? []).map(renderFilterLine);
  return [...lines, ...filterLines.sort(compareStrings)];
}

/**
 * Compare two line arrays with a longest-common-subsequence diff.
 *
 * Pure and dependency-free. Rows follow document order: shared lines are
 * emitted as `unchanged`, deletions from `previous` as `removed`, and
 * insertions from `current` as `added` (removals precede additions in a hunk).
 */
export function diffMetricVersionLines(previous: string[], current: string[]): DiffRow[] {
  const table = buildLcsTable(previous, current);
  const rows: DiffRow[] = [];
  let i = 0;
  let j = 0;
  while (i < previous.length || j < current.length) {
    if (i < previous.length && j < current.length && previous[i] === current[j]) {
      rows.push({ status: 'unchanged', text: previous[i] });
      i += 1;
      j += 1;
    } else if (i >= previous.length || (j < current.length && table[i][j + 1] > table[i + 1][j])) {
      rows.push({ status: 'added', text: current[j] });
      j += 1;
    } else {
      rows.push({ status: 'removed', text: previous[i] });
      i += 1;
    }
  }
  return rows;
}

/**
 * Diff two metric version definitions into presentable rows.
 *
 * Returns `{ available: false }` when either side lacks a usable definition;
 * otherwise returns LCS rows over the formula/filter display lines.
 */
export function buildMetricVersionDiff(
  previous: MetricDefinition | null | undefined,
  current: MetricDefinition | null | undefined,
): MetricVersionDiffResult {
  const previousLines = buildMetricVersionLines(previous);
  const currentLines = buildMetricVersionLines(current);
  if (!previousLines || !currentLines) return { available: false };
  return { available: true, rows: diffMetricVersionLines(previousLines, currentLines) };
}

function renderFilterLine(filter: MetricFilter): string {
  return `${filter.field} ${filter.operator} ${stringifyFilterValue(filter.value)}`;
}

function stringifyFilterValue(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  return JSON.stringify(value) ?? String(value);
}

function compareStrings(a: string, b: string): number {
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

/**
 * Build the suffix-style LCS length table where `table[i][j]` is the LCS size
 * of `a[i..]` against `b[j..]`.
 */
function buildLcsTable(a: string[], b: string[]): number[][] {
  const table: number[][] = Array.from({ length: a.length + 1 }, () =>
    new Array<number>(b.length + 1).fill(0),
  );
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i][j] =
        a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  return table;
}
