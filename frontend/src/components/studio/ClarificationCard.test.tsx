import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ClarificationCard } from '@/components/studio/ClarificationCard';
import { ChatClarificationOption, ClarificationResolution } from '@/lib/api';

function makeOptions(): ChatClarificationOption[] {
  return [
    { id: 'opt_1', label: 'Theo khách hàng', spec: { metric_ids: [1] } },
    { id: 'opt_2', label: 'Theo tháng', spec: { metric_ids: [1] } },
    { id: 'opt_3', label: 'Theo chi nhánh', spec: { metric_ids: [1] } },
  ];
}

describe('ClarificationCard', () => {
  beforeEach(() => {
    cleanup();
  });

  it('renders the prompt, numbered option badges, ↵ affordance, and Something else / Skip controls', () => {
    render(
      <ClarificationCard
        prompt="Bạn muốn xem doanh thu theo chiều nào?"
        options={makeOptions()}
        onSelectOption={vi.fn()}
        onCustomAnswer={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    expect(screen.getByText('Bạn muốn xem doanh thu theo chiều nào?')).toBeInTheDocument();
    expect(screen.getByText('Theo khách hàng')).toBeInTheDocument();
    expect(screen.getByText('Theo tháng')).toBeInTheDocument();
    expect(screen.getByText('Theo chi nhánh')).toBeInTheDocument();

    // Numbered badges 1..3 are visible.
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    // Trailing Enter affordance.
    expect(screen.getAllByText('↵').length).toBeGreaterThanOrEqual(3);

    // Accessible action controls.
    expect(screen.getByPlaceholderText(/Something else/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Skip/i })).toBeInTheDocument();
  });

  it('selects an option on click and reports the option id and label', () => {
    const onSelect = vi.fn();
    render(
      <ClarificationCard
        prompt="Chọn?"
        options={makeOptions()}
        onSelectOption={onSelect}
        onCustomAnswer={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText('Theo tháng'));
    expect(onSelect).toHaveBeenCalledWith('opt_2', 'Theo tháng');
  });

  it('selects an option via keyboard Enter and keeps focus labels accessible', () => {
    const onSelect = vi.fn();
    render(
      <ClarificationCard
        prompt="Chọn?"
        options={makeOptions()}
        onSelectOption={onSelect}
        onCustomAnswer={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    const optionBtn = screen.getByRole('button', { name: /Theo khách hàng/i });
    expect(optionBtn).toHaveAccessibleName(/1/);
    fireEvent.keyDown(optionBtn, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith('opt_1', 'Theo khách hàng');
  });

  it('allows typing into inline Something else input and submits trimmed text on Enter while keeping options visible', () => {
    const onCustom = vi.fn();
    render(
      <ClarificationCard
        prompt="Chọn?"
        options={makeOptions()}
        onSelectOption={vi.fn()}
        onCustomAnswer={onCustom}
        onSkip={vi.fn()}
      />,
    );

    const input = screen.getByLabelText(/Câu trả lời tùy chỉnh/i) as HTMLInputElement;
    expect(screen.getByText('Theo khách hàng')).toBeInTheDocument();
    expect(screen.getByText('Theo tháng')).toBeInTheDocument();

    fireEvent.change(input, { target: { value: '  Theo ngày  ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCustom).toHaveBeenCalledWith('Theo ngày');
    // Options remain visible throughout!
    expect(screen.getByText('Theo khách hàng')).toBeInTheDocument();
  });

  it('clears custom input on Escape without resolving while keeping options visible', () => {
    const onCustom = vi.fn();
    render(
      <ClarificationCard
        prompt="Chọn?"
        options={makeOptions()}
        onSelectOption={vi.fn()}
        onCustomAnswer={onCustom}
        onSkip={vi.fn()}
      />,
    );

    const input = screen.getByLabelText(/Câu trả lời tùy chỉnh/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'bỏ qua nhé' } });
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(onCustom).not.toHaveBeenCalled();
    expect(input.value).toBe('');
    expect(screen.getByText('Theo khách hàng')).toBeInTheDocument();
  });

  it('calls onSkip when Skip is activated', () => {
    const onSkip = vi.fn();
    render(
      <ClarificationCard
        prompt="Chọn?"
        options={makeOptions()}
        onSelectOption={vi.fn()}
        onCustomAnswer={vi.fn()}
        onSkip={onSkip}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Skip/i }));
    expect(onSkip).toHaveBeenCalledTimes(1);
  });

  it('disables every interactive control while a resolve request is pending', () => {
    render(
      <ClarificationCard
        prompt="Chọn?"
        options={makeOptions()}
        pending
        onSelectOption={vi.fn()}
        onCustomAnswer={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /Theo khách hàng/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Theo tháng/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Theo chi nhánh/i })).toBeDisabled();
    expect(screen.getByLabelText(/Câu trả lời tùy chỉnh/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /Skip/i })).toBeDisabled();
  });

  it('renders a resolved option selection as exactly two lines with no controls', () => {
    const resolution: ClarificationResolution = {
      status: 'answered',
      selected_option_id: 'opt_1',
      selected_label: 'Theo khách hàng',
    };
    render(
      <ClarificationCard
        prompt="Bạn muốn xem doanh thu theo chiều nào?"
        options={makeOptions()}
        resolution={resolution}
        onSelectOption={vi.fn()}
        onCustomAnswer={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    expect(screen.getByText('Bạn muốn xem doanh thu theo chiều nào?')).toBeInTheDocument();
    expect(screen.getByText('Theo khách hàng')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Something else/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Skip/i })).not.toBeInTheDocument();
    expect(screen.queryByText('↵')).not.toBeInTheDocument();
  });

  it('renders a resolved custom answer as exactly two lines', () => {
    const resolution: ClarificationResolution = {
      status: 'answered',
      custom_answer: 'Theo ngày tạo đơn',
    };
    render(
      <ClarificationCard
        prompt="Bạn muốn xem theo?"
        options={makeOptions()}
        resolution={resolution}
        onSelectOption={vi.fn()}
        onCustomAnswer={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    expect(screen.getByText('Bạn muốn xem theo?')).toBeInTheDocument();
    expect(screen.getByText('Theo ngày tạo đơn')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders a skipped resolution as Đã bỏ qua with no controls', () => {
    const resolution: ClarificationResolution = { status: 'skipped' };
    render(
      <ClarificationCard
        prompt="Bạn muốn xem theo?"
        options={makeOptions()}
        resolution={resolution}
        onSelectOption={vi.fn()}
        onCustomAnswer={vi.fn()}
        onSkip={vi.fn()}
      />,
    );

    expect(screen.getByText('Đã bỏ qua')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows an error with a retry control that invokes onRetry', () => {
    const onRetry = vi.fn();
    render(
      <ClarificationCard
        prompt="Chọn?"
        options={makeOptions()}
        error="Không thể thực thi lựa chọn"
        onSelectOption={vi.fn()}
        onCustomAnswer={vi.fn()}
        onSkip={vi.fn()}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(/Không thể thực thi lựa chọn/i);
    const retry = screen.getByRole('button', { name: /Thử lại/i });
    expect(retry).toBeInTheDocument();
    fireEvent.click(retry);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('calls onSkip when the close (X) header button is clicked', () => {
    const onSkip = vi.fn();
    render(
      <ClarificationCard
        prompt="Chọn?"
        options={makeOptions()}
        onSelectOption={vi.fn()}
        onCustomAnswer={vi.fn()}
        onSkip={onSkip}
      />,
    );

    const closeBtn = screen.getByRole('button', { name: /Đóng/i });
    expect(closeBtn).toBeInTheDocument();
    fireEvent.click(closeBtn);
    expect(onSkip).toHaveBeenCalledTimes(1);
  });
});
