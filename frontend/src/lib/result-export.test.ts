import { describe, expect, it } from 'vitest';

import { buildCsv, buildExcelXml, safeSpreadsheetCell } from '@/lib/result-export';

const result = {
  sql: 'SELECT 1',
  parameters: {},
  columns: ['name', 'amount'],
  rows: [['A, "quoted"', '=2+3']],
  row_count: 1,
};

describe('result export', () => {
  it('escapes CSV and neutralizes spreadsheet formulas', () => {
    const csv = buildCsv(result);
    expect(csv).toContain('"A, ""quoted"""');
    expect(csv).toContain('"\'=2+3"');
  });

  it('writes Excel-compatible XML with string cells', () => {
    const xml = buildExcelXml(result);
    expect(xml).toContain('ss:Type="String"');
    expect(xml).toContain('&quot;quoted&quot;');
    expect(xml).toContain('&apos;=2+3');
  });

  it.each(['=SUM(A1)', '+cmd', '-1+2', '@value'])('neutralizes %s', (value) => {
    expect(safeSpreadsheetCell(value)).toBe(`'${value}`);
  });
});
