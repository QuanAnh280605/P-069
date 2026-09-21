import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { JoinPathSelector } from '@/components/modals/JoinPathSelector';
import { MetricJoinPathOptions } from '@/lib/api';

const options: MetricJoinPathOptions = {
  '20': [
    {
      relationship_ids: [5],
      entity_ids: [10, 20],
      labels: ['Đơn thuộc khách'],
      descriptions: ['Mỗi đơn hàng thuộc về một khách hàng'],
    },
    {
      relationship_ids: [6],
      entity_ids: [10, 20],
      labels: ['Đơn giao cho khách'],
      descriptions: ['Giao dịch được gán cho khách hàng'],
    },
  ],
};

describe('JoinPathSelector', () => {
  afterEach(() => cleanup());

  it('renders nothing when no target has more than one safe path', () => {
    const single: MetricJoinPathOptions = {
      '20': [
        {
          relationship_ids: [5],
          entity_ids: [10, 20],
          labels: ['Đơn thuộc khách'],
          descriptions: ['note'],
        },
      ],
    };
    const { container } = render(
      <JoinPathSelector options={single} value={{}} onChange={vi.fn()} />,
    );
    expect(container.querySelector('[data-testid="join-path-selector"]')).toBeNull();
  });

  it('renders reviewed path labels (not raw ids) for ambiguous targets', () => {
    render(<JoinPathSelector options={options} value={{}} onChange={vi.fn()} />);
    expect(screen.getByText('Ngữ cảnh quan hệ')).toBeInTheDocument();
    expect(screen.getByText('Đơn thuộc khách')).toBeInTheDocument();
    expect(screen.getByText('Đơn giao cho khách')).toBeInTheDocument();
    expect(screen.getByText(/Mỗi đơn hàng thuộc về một khách hàng/)).toBeInTheDocument();
  });

  it('persists the chosen ordered relationship ids via onChange', () => {
    const onChange = vi.fn();
    render(<JoinPathSelector options={options} value={{}} onChange={onChange} />);
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(2);
    fireEvent.click(radios[1]);
    expect(onChange).toHaveBeenCalledWith({ '20': [6] });
  });

  it('keeps an existing valid selection highlighted', () => {
    render(<JoinPathSelector options={options} value={{ '20': [5] }} onChange={vi.fn()} />);
    const radios = screen.getAllByRole('radio');
    expect(radios[0]).toBeChecked();
    expect(radios[1]).not.toBeChecked();
  });

  it('shows a blocking note for a stale stored selection', () => {
    render(
      <JoinPathSelector
        options={options}
        value={{ '20': [99] }}
        onChange={vi.fn()}
        staleTargets={['20']}
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent(/không còn hợp lệ/);
  });

  it('uses a friendly target label when provided', () => {
    render(
      <JoinPathSelector
        options={options}
        value={{}}
        onChange={vi.fn()}
        targetLabels={{ '20': 'Khách hàng' }}
      />,
    );
    expect(screen.getByText('Khách hàng')).toBeInTheDocument();
  });
});
