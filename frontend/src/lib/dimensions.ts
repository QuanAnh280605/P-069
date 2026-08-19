import { CatalogColumn } from './api';

export type DimensionCategory = 'categorical' | 'entity' | 'code' | 'technical' | 'measure' | 'time';

/**
 * Check if a column represents a timestamp or date dimension.
 */
export function isTimeDimension(col: CatalogColumn): boolean {
  if (col.is_time_dimension) return true;
  const dt = (col.data_type || '').toLowerCase();
  return dt.includes('date') || dt.includes('time') || dt.includes('timestamp');
}

/**
 * Check if a column is a technical ID / Primary Key / Foreign Key.
 */
export function isTechnicalKey(col: CatalogColumn): boolean {
  if (col.is_primary_key || col.is_foreign_key) return true;
  const name = col.column_name.toLowerCase();
  if (name === 'id' || name === '_id' || name === 'guid' || name === 'uuid') return true;
  if (/^(id|_id|uuid|guid|pk_|fk_)/i.test(name)) return true;
  if (name.endsWith('_id') || name.endsWith('id') || name.endsWith('_pk') || name.endsWith('_fk')) {
    if (!['valid', 'paid', 'grid', 'liquid', 'solid'].includes(name)) {
      return true;
    }
  }
  return false;
}

/**
 * Check if a column is a continuous numerical measure candidate (e.g. price, amount, cost, revenue, qty).
 */
export function isMeasureField(col: CatalogColumn): boolean {
  const dt = (col.data_type || '').toUpperCase();
  const isNumeric = ['INT', 'FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC', 'REAL', 'BIGINT', 'MONEY', 'NUMBER'].some(
    (type) => dt.includes(type),
  );
  if (!isNumeric) return false;

  const name = col.column_name.toLowerCase();
  const measureKeywords = [
    'price',
    'amount',
    'total',
    'subtotal',
    'cost',
    'revenue',
    'sales',
    'discount',
    'tax',
    'fee',
    'rate',
    'salary',
    'wage',
    'quantity',
    'qty',
    'score',
    'points',
    'balance',
    'profit',
    'margin',
  ];

  return measureKeywords.some((kw) => name === kw || name.startsWith(`${kw}_`) || name.endsWith(`_${kw}`));
}

/**
 * Check if a column is an internal / sensitive / system field that should never be a business dimension.
 */
export function isSensitiveField(col: CatalogColumn): boolean {
  const name = col.column_name.toLowerCase();
  const sensitivePatterns = [
    'password',
    'passwd',
    'secret',
    'token',
    'hash',
    'salt',
    'checksum',
    'raw_payload',
    'avatar_url',
    'image_url',
    'deleted_at',
    'is_deleted',
  ];
  return sensitivePatterns.some((pattern) => name.includes(pattern));
}

/**
 * Filter columns that are valid, high-value business dimensions (Categorical & Entity descriptors).
 */
export function isBusinessDimension(col: CatalogColumn): boolean {
  if (isTimeDimension(col)) return false;
  if (isTechnicalKey(col)) return false;
  if (isMeasureField(col)) return false;
  if (isSensitiveField(col)) return false;
  return true;
}

/**
 * Classify a column into its Semantic Layer semantic category.
 */
export function getDimensionCategory(col: CatalogColumn): DimensionCategory {
  if (isTimeDimension(col)) return 'time';
  if (isTechnicalKey(col)) return 'technical';
  if (isMeasureField(col)) return 'measure';

  const name = col.column_name.toLowerCase();
  if (
    name.includes('name') ||
    name.includes('title') ||
    name === 'description' ||
    name.endsWith('_name')
  ) {
    return 'entity';
  }

  if (name.includes('code') || name.includes('sku') || name.includes('isbn') || name.endsWith('_code')) {
    return 'code';
  }

  return 'categorical';
}

/**
 * Get human-readable badge metadata for a dimension category.
 */
export function getDimensionCategoryBadge(category: DimensionCategory): {
  label: string;
  enLabel: string;
  badgeClass: string;
} {
  switch (category) {
    case 'entity':
      return {
        label: 'Thực thể',
        enLabel: 'Entity',
        badgeClass: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
      };
    case 'code':
      return {
        label: 'Mã / SKU',
        enLabel: 'Code',
        badgeClass: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
      };
    case 'technical':
      return {
        label: 'Khóa ID',
        enLabel: 'Key',
        badgeClass: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
      };
    case 'measure':
      return {
        label: 'Đo lường',
        enLabel: 'Measure',
        badgeClass: 'bg-rose-500/10 text-rose-500 border-rose-500/20',
      };
    case 'time':
      return {
        label: 'Thời gian',
        enLabel: 'Time',
        badgeClass: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20',
      };
    case 'categorical':
    default:
      return {
        label: 'Phân loại',
        enLabel: 'Categorical',
        badgeClass: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
      };
  }
}
