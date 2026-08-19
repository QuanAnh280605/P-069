import { describe, expect, it } from 'vitest';

import { MetricSuggestion } from '@/lib/api';
import {
  applySuggestedName,
  coerceFilterValue,
  createMetricDefinition,
  renderMetricYaml,
} from '@/lib/metrics';

describe('metric definition utilities', () => {
  it('renders stable Unicode YAML without empty filters', () => {
    const definition = createMetricDefinition('OrderItem');
    definition.metric.name = 'Doanh thu';
    definition.metric.formula.expression = 'quantity * unit_price';
    definition.metric.excluded_notes = 'Chưa trừ hoàn tiền';
    const yaml = renderMetricYaml(definition);
    expect(yaml).toContain('name: Doanh thu');
    expect(yaml).toContain('Chưa trừ hoàn tiền');
    expect(yaml).not.toContain('filters:');
  });

  it('converts operator-specific filter values', () => {
    expect(coerceFilterValue('in', '1, 2, active')).toEqual([1, 2, 'active']);
    expect(coerceFilterValue('is_null', 'ignored')).toBeNull();
    expect(coerceFilterValue('eq', 'true')).toBe(true);
  });
});

describe('applySuggestedName', () => {
  it('renames the metric, re-renders YAML, and drops the conflict flag', () => {
    const definition = createMetricDefinition('OrderItem');
    definition.metric.name = 'Doanh thu';
    definition.metric.formula.expression = 'quantity * unit_price';
    const suggestion: MetricSuggestion = {
      definition,
      yaml_preview: renderMetricYaml(definition),
      conflict: {
        proposed_metric_name: 'Doanh thu',
        existing_metric_id: 12,
        existing_metric_name: 'Doanh thu',
        existing_metric_status: 'approved',
        suggested_name: 'Doanh thu (mới)',
        clarify_question: 'Tên "Doanh thu" đã được dùng cho metric khác công thức. Bạn muốn đổi tên?',
      },
    };
    const inputSnapshot = JSON.parse(JSON.stringify(suggestion));

    const result = applySuggestedName(suggestion);

    expect(result.definition.metric.name).toBe('Doanh thu (mới)');
    expect(result.yaml_preview).toContain('Doanh thu (mới)');
    expect(result.yaml_preview).not.toContain('name: Doanh thu\n');
    expect(result.conflict).toBeUndefined();
    // Input is not mutated
    expect(suggestion).toEqual(inputSnapshot);
    expect(suggestion.definition.metric.name).toBe('Doanh thu');
  });

  it('returns the suggestion unchanged when there is no usable suggested name', () => {
    const definition = createMetricDefinition('OrderItem');
    definition.metric.name = 'Doanh thu';
    const plain: MetricSuggestion = { definition, yaml_preview: renderMetricYaml(definition) };
    const emptySuggestion: MetricSuggestion = {
      definition: createMetricDefinition('OrderItem'),
      yaml_preview: '',
      conflict: {
        proposed_metric_name: 'Doanh thu',
        existing_metric_id: null,
        existing_metric_name: 'Doanh thu',
        existing_metric_status: null,
        suggested_name: '   ',
        clarify_question: '',
      },
    };
    const plainSnapshot = JSON.parse(JSON.stringify(plain));
    const emptySnapshot = JSON.parse(JSON.stringify(emptySuggestion));

    expect(applySuggestedName(plain)).toEqual(plain);
    expect(applySuggestedName(emptySuggestion)).toEqual(emptySuggestion);

    // Inputs are not mutated
    expect(plain).toEqual(plainSnapshot);
    expect(emptySuggestion).toEqual(emptySnapshot);
  });
});
