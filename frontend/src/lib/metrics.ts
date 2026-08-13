import YAML from 'yaml';
import { FilterOperator, MetricDefinition, MetricFilter, MetricStatus } from '@/lib/api';

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

export function metricName(definition: MetricDefinition | null | undefined): string {
  return definition?.metric?.name || 'Chưa đặt tên';
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

export function coerceFilterValue(operator: FilterOperator, rawValue: string): unknown {
  if (operator === 'is_null' || operator === 'is_not_null') {
    return null;
  }
  if (operator === 'in' || operator === 'not_in') {
    return rawValue.split(',').map((item) => item.trim()).filter(Boolean);
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

export function renderMetricYaml(definition: MetricDefinition): string {
  try {
    return YAML.stringify(definition);
  } catch {
    return JSON.stringify(definition, null, 2);
  }
}
