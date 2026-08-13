import { MetricDefinition, MetricRecord, MetricStatus, MetricSuggestion } from './api';

export function metricName(
  item?: MetricRecord | MetricSuggestion | { name?: string; definition?: MetricDefinition | null } | null
): string {
  if (!item) return 'Unnamed Metric';
  if ('name' in item && item.name) return item.name;
  if (item.definition?.metric?.name) return item.definition.metric.name;
  return 'Unnamed Metric';
}

export function statusLabel(status?: string | null): string {
  if (!status) return 'Chờ duyệt';
  switch (status.toLowerCase()) {
    case 'approved':
      return 'Đã duyệt';
    case 'needs_review':
      return 'Cần xem xét';
    case 'pending_approval':
    case 'pending':
    case 'draft':
    default:
      return 'Chờ duyệt';
  }
}

function objectToYaml(obj: unknown, indentLevel = 0): string {
  if (obj === null || obj === undefined) return '';
  const indent = '  '.repeat(indentLevel);

  if (typeof obj !== 'object') {
    if (typeof obj === 'string') {
      if (obj.includes('\n') || obj.includes(':')) {
        return `'${obj.replace(/'/g, "''")}'`;
      }
      return obj;
    }
    return String(obj);
  }

  if (Array.isArray(obj)) {
    if (obj.length === 0) return '[]';
    return obj
      .map((item) => {
        if (typeof item === 'object' && item !== null) {
          const itemYaml = objectToYaml(item, indentLevel + 1).trimStart();
          return `${indent}- ${itemYaml}`;
        }
        return `${indent}- ${objectToYaml(item, 0)}`;
      })
      .join('\n');
  }

  const entries = Object.entries(obj as Record<string, unknown>);
  if (entries.length === 0) return '{}';

  return entries
    .map(([key, val]) => {
      if (val === null || val === undefined) return `${indent}${key}: null`;
      if (typeof val === 'object') {
        if (Array.isArray(val) && val.length === 0) return `${indent}${key}: []`;
        if (!Array.isArray(val) && Object.keys(val).length === 0) return `${indent}${key}: {}`;
        return `${indent}${key}:\n${objectToYaml(val, indentLevel + 1)}`;
      }
      return `${indent}${key}: ${objectToYaml(val, 0)}`;
    })
    .join('\n');
}

export function renderMetricYaml(definition?: MetricDefinition | null): string {
  if (!definition) return '';
  return objectToYaml(definition);
}

export function createMetricDefinition(tableName: string = ''): MetricDefinition {
  return {
    metric: {
      name: '',
      formula: {
        function: 'COUNT',
        expression: '*',
      },
      base_entity: tableName,
      filters: [],
      status: 'pending_approval',
      confidence: 'medium',
      excluded_notes: '',
    },
  };
}

export function withPendingStatus(definition: MetricDefinition): MetricDefinition {
  const currentStatus: MetricStatus = definition.metric?.status || 'pending_approval';
  return {
    ...definition,
    metric: {
      ...definition.metric,
      status: currentStatus,
    },
  };
}

export function coerceFilterValue(operator: string, value: string): unknown {
  if (operator === 'is_null' || operator === 'is_not_null') {
    return null;
  }
  if (!value) return '';
  if (operator === 'in' || operator === 'not_in') {
    return value.split(',').map((v) => v.trim()).filter(Boolean);
  }
  if (!isNaN(Number(value)) && value.trim() !== '') {
    return Number(value);
  }
  return value;
}
