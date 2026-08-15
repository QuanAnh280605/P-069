import { describe, expect, it } from 'vitest';

import { coerceFilterValue, createMetricDefinition, renderMetricYaml } from '@/lib/metrics';

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
