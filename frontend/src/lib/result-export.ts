import type { SemanticQueryResult } from '@/lib/semantic-query';

const DANGEROUS_CELL = /^\s*[=+\-@]/;

export function safeSpreadsheetCell(value: unknown): string {
  const text = value == null ? '' : String(value);
  return DANGEROUS_CELL.test(text) ? `'${text}` : text;
}

export function buildCsv(result: SemanticQueryResult): string {
  const rows = [result.columns, ...result.rows];
  return `\uFEFF${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`;
}

export function buildExcelXml(result: SemanticQueryResult): string {
  const rows = [result.columns, ...result.rows].map(excelRow).join('');
  return `<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="Query result"><Table>${rows}</Table></Worksheet></Workbook>`;
}

export function downloadQueryResult(result: SemanticQueryResult, format: 'csv' | 'xls'): void {
  const isCsv = format === 'csv';
  const content = isCsv ? buildCsv(result) : buildExcelXml(result);
  const type = isCsv ? 'text/csv;charset=utf-8' : 'application/vnd.ms-excel;charset=utf-8';
  downloadBlob(content, type, `semantic-query.${format}`);
}

function csvCell(value: unknown): string {
  const safe = safeSpreadsheetCell(value).replaceAll('"', '""');
  return `"${safe}"`;
}

function excelRow(values: unknown[]): string {
  const cells = values.map(excelCell).join('');
  return `<Row>${cells}</Row>`;
}

function excelCell(value: unknown): string {
  const safe = escapeXml(safeSpreadsheetCell(value));
  return `<Cell><Data ss:Type="String">${safe}</Data></Cell>`;
}

function escapeXml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function downloadBlob(content: string, type: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
