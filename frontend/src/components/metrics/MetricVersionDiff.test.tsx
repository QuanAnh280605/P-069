import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { MetricVersionDiff } from '@/components/metrics/MetricVersionDiff';
import { MetricDefinition } from '@/lib/api';

function makeDefinition(
  expression: string,
  filters: Array<{ field: string; operator: 'eq' | 'in'; value: unknown }> = [],
): MetricDefinition {
  return {
    metric: {
      name: 'Doanh thu',
      formula: { function: 'SUM', expression },
      base_entity: 'OrderItem',
      filters,
      status: 'approved',
      excluded_notes: '',
    },
  };
}

describe('MetricVersionDiff', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders removed formula in red and added formula in green', () => {
    render(
      <MetricVersionDiff
        previousDefinition={makeDefinition('a')}
        currentDefinition={makeDefinition('a - b')}
      />,
    );

    const removed = screen.getByText('SUM(a)').closest('[data-status]');
    const added = screen.getByText('SUM(a - b)').closest('[data-status]');

    expect(removed).toHaveAttribute('data-status', 'removed');
    expect(removed?.className).toMatch(/text-red-/);
    expect(removed).toHaveTextContent('−');
    expect(added).toHaveAttribute('data-status', 'added');
    expect(added?.className).toMatch(/text-emerald-/);
    expect(added).toHaveTextContent('+');
  });

  it('renders unchanged rows in a neutral style without change markers', () => {
    render(
      <MetricVersionDiff
        previousDefinition={makeDefinition('a')}
        currentDefinition={makeDefinition('a')}
      />,
    );

    const unchanged = screen.getByText('SUM(a)').closest('[data-status]');
    expect(unchanged).toHaveAttribute('data-status', 'unchanged');
    expect(unchanged?.className).toMatch(/text-muted-foreground/);
    expect(unchanged?.className).not.toMatch(/text-red-|text-emerald-/);
  });

  it('labels formula and filter lines in Vietnamese', () => {
    render(
      <MetricVersionDiff
        previousDefinition={makeDefinition('a', [
          { field: 'order_status', operator: 'eq', value: 'DONE' },
        ])}
        currentDefinition={makeDefinition('a - b', [
          { field: 'order_status', operator: 'eq', value: 'DONE' },
        ])}
      />,
    );

    const container = screen.getByTestId('metric-version-diff');
    const formulaRow = Array.from(container.querySelectorAll('[data-status]')).find((row) =>
      row.textContent?.includes('SUM(a)'),
    );
    const filterRow = Array.from(container.querySelectorAll('[data-status]')).find((row) =>
      row.textContent?.includes('order_status'),
    );
    expect(formulaRow).toHaveTextContent('Công thức');
    expect(filterRow).toHaveTextContent('Bộ lọc');
  });

  it('shows an unavailable state when either side lacks a definition', () => {
    render(
      <MetricVersionDiff previousDefinition={null} currentDefinition={makeDefinition('a')} />,
    );

    expect(screen.queryByTestId('metric-version-diff')).not.toBeInTheDocument();
    expect(screen.getByText(/legacy/i)).toBeInTheDocument();
  });
});
