import { describe, expect, it } from 'vitest';

import {
  formatCellValue,
  formatDimensionValue,
  formatNumberVi,
  formatShortNumber,
  parseTimeSortKey,
  PIE_MAX_SLICES,
  RANKING_MAX_ROWS,
  resolveColumnLabel,
  sortPointsByValueDesc,
  sortRowsByTimeColumn,
  truncatePieSlices,
  truncateRankingRows,
  type DashboardPoint,
} from './dashboardFormatters';

function point(label: string, value: number, rawValue: unknown = value): DashboardPoint {
  return { label, rawLabel: label, value, rawValue };
}

describe('resolveColumnLabel', () => {
  const context = { metricName: 'Doanh thu thuần', dimensionLabel: 'Trạng thái đơn' };

  it('maps compiler aliases to the known metric and dimension labels', () => {
    expect(resolveColumnLabel('metric_5', context)).toBe('Doanh thu thuần');
    expect(resolveColumnLabel('dimension_12', context)).toBe('Trạng thái đơn');
  });

  it('falls back to a numbered Vietnamese label when the dimension is unknown', () => {
    expect(resolveColumnLabel('dimension_99', { metricName: 'M', dimensionLabel: null })).toBe(
      'Chiều 99',
    );
  });

  it('cleans SQL aggregation names into Vietnamese titles', () => {
    expect(resolveColumnLabel('SUM(price)', context)).toBe('Tổng price');
    expect(resolveColumnLabel('AVG(amount)', context)).toBe('Trung bình amount');
    expect(resolveColumnLabel('COUNT(*)', context)).toBe('Số lượng *');
  });

  it('passes through plain identifiers and empty keys', () => {
    expect(resolveColumnLabel('created_at', context)).toBe('created_at');
    expect(resolveColumnLabel('', context)).toBe('');
  });
});

describe('formatNumberVi', () => {
  it('groups thousands with dots in Vietnamese convention', () => {
    expect(formatNumberVi(0)).toBe('0');
    expect(formatNumberVi(999)).toBe('999');
    expect(formatNumberVi(1500)).toBe('1.500');
    expect(formatNumberVi(1234567)).toBe('1.234.567');
    expect(formatNumberVi(-98765)).toBe('-98.765');
  });

  it('renders decimals with commas and rounds beyond two places', () => {
    expect(formatNumberVi(1234.5)).toBe('1.234,5');
    expect(formatNumberVi(1234.567)).toBe('1.234,57');
  });

  it('is null-safe for non-finite numbers', () => {
    expect(formatNumberVi(Number.NaN)).toBe('—');
    expect(formatNumberVi(Number.POSITIVE_INFINITY)).toBe('—');
  });
});

describe('formatShortNumber', () => {
  it('keeps small values at full precision', () => {
    expect(formatShortNumber(999)).toBe('999');
  });

  it('compacts thousands, millions, and billions with Vietnamese suffixes', () => {
    expect(formatShortNumber(1000)).toBe('1 K');
    expect(formatShortNumber(1500)).toBe('1,5 K');
    expect(formatShortNumber(2_500_000)).toBe('2,5 Tr');
    expect(formatShortNumber(1_200_000_000)).toBe('1,2 Tỷ');
    expect(formatShortNumber(2_000_000_000)).toBe('2 Tỷ');
  });

  it('preserves the sign for negative compaction', () => {
    expect(formatShortNumber(-1500)).toBe('-1,5 K');
  });
});

describe('formatCellValue', () => {
  it('renders missing values as an em dash', () => {
    expect(formatCellValue(null)).toBe('—');
    expect(formatCellValue(undefined)).toBe('—');
    expect(formatCellValue('')).toBe('—');
  });

  it('formats numeric cells with Vietnamese grouping', () => {
    expect(formatCellValue(1500)).toBe('1.500');
    expect(formatCellValue('2048.5')).toBe('2.048,5');
  });

  it('maps booleans and keeps other strings verbatim', () => {
    expect(formatCellValue(true)).toBe('Có');
    expect(formatCellValue(false)).toBe('Không');
    expect(formatCellValue('doanh thu')).toBe('doanh thu');
  });
});

describe('formatDimensionValue', () => {
  it('labels empty categorical values', () => {
    expect(formatDimensionValue(null)).toBe('(Trống)');
    expect(formatDimensionValue(undefined)).toBe('(Trống)');
    expect(formatDimensionValue('')).toBe('(Trống)');
  });

  it('translates boolean values', () => {
    expect(formatDimensionValue(true)).toBe('Có');
    expect(formatDimensionValue('false')).toBe('Không');
  });

  it('formats date-like values as day/month/year', () => {
    expect(formatDimensionValue('2024-03-05')).toBe('05/03/2024');
    expect(formatDimensionValue('2024-03-05T10:30:00')).toBe('05/03/2024');
  });

  it('formats truncated time grains in Vietnamese', () => {
    expect(formatDimensionValue('2024-03')).toBe('Tháng 03/2024');
    expect(formatDimensionValue('2024-W07')).toBe('Tuần 07/2024');
    expect(formatDimensionValue('2024-Q1')).toBe('Quý 1/2024');
    expect(formatDimensionValue('2024')).toBe('Năm 2024');
  });

  it('keeps ordinary category strings verbatim', () => {
    expect(formatDimensionValue('pending')).toBe('pending');
  });
});

describe('parseTimeSortKey', () => {
  it('parses canonical truncation outputs across grains', () => {
    expect(parseTimeSortKey('2024')).toEqual([2024]);
    expect(parseTimeSortKey('2024-03')).toEqual([2024, 3]);
    expect(parseTimeSortKey('2024-03-05')).toEqual([2024, 3, 5]);
    expect(parseTimeSortKey('2024-Q2')).toEqual([2024, 2]);
    expect(parseTimeSortKey('2024-W07')).toEqual([2024, 7]);
  });

  it('parses timestamp outputs from stricter dialects', () => {
    expect(parseTimeSortKey('2024-03-05T10:30:00')).toEqual([2024, 3, 5]);
    expect(parseTimeSortKey('2024-03-05 10:30:00')).toEqual([2024, 3, 5]);
  });

  it('returns null for non-time values', () => {
    expect(parseTimeSortKey('not-a-date')).toBeNull();
    expect(parseTimeSortKey(42)).toBeNull();
    expect(parseTimeSortKey(null)).toBeNull();
  });
});

describe('sortRowsByTimeColumn', () => {
  it('sorts rows ascending by the time column without mutating input', () => {
    const rows = [
      ['2024-03', 3],
      ['2024-01', 1],
      ['2023-12', 12],
    ];
    const sorted = sortRowsByTimeColumn(rows, 0);
    expect(sorted.map((row) => row[0])).toEqual(['2023-12', '2024-01', '2024-03']);
    expect(rows[0][0]).toBe('2024-03');
  });

  it('orders mixed dialect outputs consistently', () => {
    const rows = [
      ['2024-02-01 00:00:00', 'pg'],
      ['2024-01', 'sqlite'],
      ['2024-03', 'late'],
    ];
    expect(sortRowsByTimeColumn(rows, 0).map((row) => row[1])).toEqual(['sqlite', 'pg', 'late']);
  });

  it('moves unparseable rows last while keeping stable order otherwise', () => {
    const rows = [
      ['unknown', 'a'],
      ['2024-01', 'b'],
      ['unknown', 'c'],
      ['2024-01', 'd'],
    ];
    expect(sortRowsByTimeColumn(rows, 0).map((row) => row[1])).toEqual(['b', 'd', 'a', 'c']);
  });
});

describe('sortPointsByValueDesc', () => {
  it('orders by descending value with stable ties', () => {
    const points = [point('a', 5), point('b', 9), point('c', 5)];
    expect(sortPointsByValueDesc(points).map((item) => item.label)).toEqual(['b', 'a', 'c']);
  });
});

describe('truncatePieSlices', () => {
  it('keeps short series untouched', () => {
    const points = [point('a', 3), point('b', 2)];
    expect(truncatePieSlices(points)).toHaveLength(2);
  });

  it('aggregates overflow into a single remaining slice', () => {
    const points = Array.from({ length: 10 }, (_, index) => point(`p${index}`, 10 - index));
    const sliced = truncatePieSlices(points);
    expect(sliced).toHaveLength(PIE_MAX_SLICES);
    expect(sliced[sliced.length - 1]).toMatchObject({ label: 'Khác', value: 6 });
  });

  it('honors a custom slice budget and handles empty input', () => {
    const points = [point('a', 1), point('b', 2), point('c', 3)];
    const sliced = truncatePieSlices(points, 2);
    expect(sliced.map((item) => item.label)).toEqual(['c', 'Khác']);
    expect(truncatePieSlices([])).toEqual([]);
  });
});

describe('truncateRankingRows', () => {
  it('caps ranking tables at the bounded row limit', () => {
    const points = Array.from({ length: 130 }, (_, index) => point(`r${index}`, index));
    const result = truncateRankingRows(points);
    expect(RANKING_MAX_ROWS).toBe(100);
    expect(result.rows).toHaveLength(100);
    expect(result.hiddenCount).toBe(30);
  });

  it('reports nothing hidden under the limit', () => {
    const result = truncateRankingRows([point('a', 1)]);
    expect(result.rows).toHaveLength(1);
    expect(result.hiddenCount).toBe(0);
  });
});
