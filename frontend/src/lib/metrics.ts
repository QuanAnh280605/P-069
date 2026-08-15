import YAML from 'yaml';
import { FilterOperator, MetricDefinition, MetricFilter, MetricRecord, MetricStatus } from '@/lib/api';

export function createMetricDefinition(baseEntity: string = ''): MetricDefinition {
  return {
    metric: {
      name: '',
      formula: {
        function: 'SUM',
        expression: '',
      },
      base_entity: baseEntity,
      filters: [],
      status: 'pending_approval',
      confidence: 'high',
      excluded_notes: '',
    },
  };
}

export function withPendingStatus(definition: MetricDefinition): MetricDefinition {
  return {
    metric: {
      ...definition.metric,
      status: 'pending_approval',
    },
  };
}

export function metricName(item: MetricRecord | MetricDefinition | null | undefined): string {
  if (!item) return 'Chưa đặt tên';
  if ('name' in item && typeof item.name === 'string' && item.name) {
    return item.name;
  }
  if ('metric' in item && item.metric?.name) {
    return item.metric.name;
  }
  if ('definition' in item && item.definition?.metric?.name) {
    return item.definition.metric.name;
  }
  return 'Chưa đặt tên';
}

export function statusLabel(status?: MetricStatus | string): string {
  switch (status) {
    case 'approved':
      return 'Đã duyệt';
    case 'pending_approval':
      return 'Chờ duyệt';
    case 'draft':
      return 'Bản nháp';
    case 'needs_review':
      return 'Cần xem xét';
    default:
      return status || 'Chờ duyệt';
  }
}

export function coerceFilterValue(operator: FilterOperator | string, rawValue: string): unknown {
  if (operator === 'is_null' || operator === 'is_not_null') {
    return null;
  }
  if (operator === 'in' || operator === 'not_in') {
    return rawValue
      .split(',')
      .map((item) => {
        const t = item.trim();
        if (t !== '' && !isNaN(Number(t))) return Number(t);
        if (t.toLowerCase() === 'true') return true;
        if (t.toLowerCase() === 'false') return false;
        return t;
      })
      .filter(Boolean);
  }
  const trimmed = rawValue.trim();
  if (trimmed === '') return null;
  if (!isNaN(Number(trimmed))) {
    return Number(trimmed);
  }
  if (trimmed.toLowerCase() === 'true') return true;
  if (trimmed.toLowerCase() === 'false') return false;
  return trimmed;
}

export function renderMetricYaml(definition?: MetricDefinition | null): string {
  if (!definition) return '';
  const clone = JSON.parse(JSON.stringify(definition));
  if (clone.metric && Array.isArray(clone.metric.filters) && clone.metric.filters.length === 0) {
    delete clone.metric.filters;
  }
  try {
    return YAML.stringify(clone);
  } catch {
    return JSON.stringify(clone, null, 2);
  }
}

