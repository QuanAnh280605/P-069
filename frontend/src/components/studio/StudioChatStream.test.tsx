import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StudioChatStream } from '@/components/studio/StudioChatStream';

describe('StudioChatStream', () => {
  beforeEach(() => {
    cleanup();
  });

  it('shows the server YAML preview and visual property rows for AI suggestion', () => {
    render(
      <StudioChatStream
        messages={[
          {
            id: '1',
            sender: 'assistant',
            text: 'Gợi ý',
            timestamp: '10:00',
            suggestions: [
              {
                definition: {
                  metric: {
                    name: 'Doanh thu',
                    formula: { function: 'SUM', expression: 'quantity * unit_price' },
                    base_entity: 'OrderItem',
                    filters: [],
                    status: 'pending_approval',
                    confidence: 'high',
                    excluded_notes: '',
                  },
                },
                yaml_preview: 'metric:\n  name: Doanh thu\n',
              },
            ],
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
      />
    );
    // Visual properties check
    expect(screen.getByText(/Công thức tính/i)).toBeInTheDocument();
    expect(screen.getByText(/Dựa vào bảng gốc/i)).toBeInTheDocument();
    expect(screen.getByText(/Cột dữ liệu sử dụng/i)).toBeInTheDocument();
    expect(screen.getByText(/Bộ lọc điều kiện/i)).toBeInTheDocument();

    // YAML preview check
    expect(screen.getAllByText(/YAML preview/i).length).toBeGreaterThanOrEqual(1);
    const toggleYamlBtn = screen.getByRole('button', { name: /Hiển thị mã YAML/i });
    fireEvent.click(toggleYamlBtn);
    expect(screen.getByText(/name: Doanh thu/)).toBeInTheDocument();
    expect(screen.queryByText(/SQL Compiled/)).not.toBeInTheDocument();
  });

  it('shows unresolved business assumptions on a low-confidence proposal', () => {
    render(
      <StudioChatStream
        messages={[{
          id: 'assumption', sender: 'assistant', text: 'Gợi ý', timestamp: '10:00',
          suggestions: [{ definition: { metric: { name: 'Doanh thu', formula: { function: 'SUM', expression: 'amount' }, base_entity: 'orders', filters: [], status: 'pending_approval', confidence: 'low', excluded_notes: 'Giả định cần xác nhận: Chưa nêu cách xử lý hoàn tiền' } }, yaml_preview: '' }],
        }]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
      />,
    );

    expect(screen.getByText('Giả định cần xác nhận', { exact: true })).toBeInTheDocument();
    expect(screen.getByText(/Chưa nêu cách xử lý hoàn tiền/i)).toBeInTheDocument();
  });

  it('renders assistant Markdown with lists, inline code, and GFM tables', () => {
    render(
      <StudioChatStream
        messages={[
          {
            id: 'markdown',
            sender: 'assistant',
            text: '**Metric doanh thu**\n\n- Chọn `revenue`\n- Nhóm theo `created_at`\n\n| Metric | Dimension |\n| --- | --- |\n| Revenue | Month |',
            timestamp: '10:00',
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
      />,
    );

    expect(screen.getByText('Metric doanh thu')).toBeInTheDocument();
    expect(screen.getByText('revenue')).toHaveClass('text-primary');
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Month')).toBeInTheDocument();
  });

  it('renders assistant message with icon container and AI agent label', () => {
    render(
      <StudioChatStream
        messages={[
          {
            id: '1',
            sender: 'assistant',
            text: 'Tôi đã phân tích schema',
            timestamp: '10:00',
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
      />
    );
    // Assistant message should have AI agent label
    expect(screen.getByText('AI Semantic Agent')).toBeInTheDocument();
    expect(screen.getByText('Tôi đã phân tích schema')).toBeInTheDocument();
  });

  it('shows read-only permission notice in Data Assistant mode', () => {
    render(
      <StudioChatStream
        messages={[]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
        mode="data_assistant"
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent(/không có quyền tạo, sửa hoặc lưu metric/i);
    expect(screen.getByTestId('prompt-suggestion-strip')).toBeInTheDocument();
    expect(screen.getByText('Tìm metric doanh thu đã duyệt')).toBeInTheDocument();
  });

  it('lets a Member submit a generated metric request instead of saving it', () => {
    const submit = vi.fn().mockResolvedValue(undefined);
    render(
      <StudioChatStream
        messages={[{
          id: 'assistant-message', sender: 'assistant', text: 'Gợi ý', timestamp: '10:00',
          suggestionAction: 'submit_metric_request',
          suggestions: [{ definition: { metric: { name: 'Doanh thu trước thuế', formula: { function: 'SUM', expression: 'amount' }, base_entity: 'orders', filters: [], status: 'pending_approval', confidence: 'high', excluded_notes: '' } }, yaml_preview: '' }],
        }]}
        onSendMessage={vi.fn()}
        onSubmitMetricRequest={submit}
        isLoading={false}
        tableNames={[]}
        mode="data_assistant"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Gửi Data Lead xem xét/i }));
    expect(submit).toHaveBeenCalledWith('assistant-message', 0);
    expect(screen.queryByRole('button', { name: /Lưu vào Semantic Layer/i })).not.toBeInTheDocument();
  });

  it('renders user message with user label', () => {
    render(
      <StudioChatStream
        messages={[
          {
            id: '1',
            sender: 'user',
            text: 'Tạo metric doanh thu',
            timestamp: '09:55',
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
      />
    );
    expect(screen.getByText('Bạn')).toBeInTheDocument();
    expect(screen.getByText('Tạo metric doanh thu')).toBeInTheDocument();
  });

  it('renders suggestion card with metric header, status badge, and YAML toggle', () => {
    render(
      <StudioChatStream
        messages={[
          {
            id: '1',
            sender: 'assistant',
            text: 'Gợi ý',
            timestamp: '10:00',
            suggestions: [
              {
                definition: {
                  metric: {
                    name: 'Doanh thu thuần',
                    formula: { function: 'SUM', expression: 'price' },
                    base_entity: 'orders',
                    filters: [],
                    status: 'pending_approval',
                    confidence: 'high',
                    excluded_notes: '',
                  },
                },
                yaml_preview: 'metric:\n  name: Doanh thu thuần\n',
              },
            ],
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
      />
    );
    // Metric name heading
    expect(screen.getByText('Doanh thu thuần')).toBeInTheDocument();
    // Status badge
    expect(screen.getByText(/Chờ phê duyệt/)).toBeInTheDocument();
    // Confidence badge
    expect(screen.getByText(/Độ tin cậy: Cao/)).toBeInTheDocument();
    // YAML toggle button
    expect(screen.getByRole('button', { name: /Hiển thị mã YAML/i })).toBeInTheDocument();
    // Save button
    expect(screen.getByText(/Lưu vào Semantic Layer/)).toBeInTheDocument();
  });

  it('shows saved state after clicking save button', async () => {
    const onAddMetric = vi.fn().mockResolvedValue(undefined);
    render(
      <StudioChatStream
        messages={[
          {
            id: '1',
            sender: 'assistant',
            text: 'Gợi ý',
            timestamp: '10:00',
            suggestions: [
              {
                definition: {
                  metric: {
                    name: 'Doanh thu thuần',
                    formula: { function: 'SUM', expression: 'price' },
                    base_entity: 'orders',
                    filters: [],
                    status: 'pending_approval',
                    confidence: 'high',
                    excluded_notes: '',
                  },
                },
                yaml_preview: 'metric:\n  name: Doanh thu\n',
              },
            ],
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
        onAddMetric={onAddMetric}
      />
    );
    const saveBtn = screen.getByRole('button', { name: /Lưu vào Semantic Layer/ });
    fireEvent.click(saveBtn);
    // Should call onAddMetric
    expect(onAddMetric).toHaveBeenCalled();
  });

  it('restores saved state from the catalog after returning to AI Studio', () => {
    render(
      <StudioChatStream
        messages={[{
          id: 'saved', sender: 'assistant', text: 'Gợi ý', timestamp: '10:00',
          suggestions: [{ definition: { metric: { name: 'Doanh thu thuần', formula: { function: 'SUM', expression: 'price' }, base_entity: 'orders', filters: [], status: 'pending_approval', confidence: 'high', excluded_notes: '' } }, yaml_preview: '' }],
        }]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
        savedMetricNames={['Doanh thu thuần']}
      />,
    );

    expect(screen.getByRole('button', { name: /Đã lưu/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Lưu vào Semantic Layer/i })).not.toBeInTheDocument();
  });

  it('prefills the input with a suggested prompt when clicked', () => {
    const onSendMessage = vi.fn().mockResolvedValue(undefined);
    render(
      <StudioChatStream
        messages={[]}
        onSendMessage={onSendMessage}
        isLoading={false}
        tableNames={['orders', 'customers']}
      />
    );

    const strip = screen.getByTestId('prompt-suggestion-strip');
    expect(strip).toHaveClass('overflow-x-auto');
    expect(strip).toHaveClass('whitespace-nowrap');
    const suggestionChip = screen.getByText('Doanh thu thuần đơn hàng thành công');
    expect(suggestionChip).toBeInTheDocument();
    expect(screen.queryByText('Số khách hàng active')).not.toBeInTheDocument();

    fireEvent.click(suggestionChip);

    const textarea = screen.getByPlaceholderText(/Mô tả chỉ số bạn muốn tạo/i) as HTMLTextAreaElement;
    expect(onSendMessage).not.toHaveBeenCalled();
    expect(textarea.value).toBe(
      'Tính tổng doanh thu thuần của các đơn hàng có trạng thái hoàn thành (Net Revenue)',
    );
  });

  it('prefills the input when a click has slight pointer movement', () => {
    render(
      <StudioChatStream
        messages={[]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={['orders']}
      />,
    );

    const strip = screen.getByTestId('prompt-suggestion-strip');
    fireEvent.pointerDown(strip, { pointerId: 1, clientX: 100, isPrimary: true });
    fireEvent.pointerMove(strip, { pointerId: 1, clientX: 106, isPrimary: true });
    fireEvent.pointerUp(strip, { pointerId: 1, clientX: 106, isPrimary: true });
    fireEvent.click(screen.getByText('Doanh thu thuần đơn hàng thành công'));

    const textarea = screen.getByPlaceholderText(/Mô tả chỉ số bạn muốn tạo/i) as HTMLTextAreaElement;
    expect(textarea.value).toContain('Tính tổng doanh thu thuần của các đơn hàng');
  });

  it('allows selecting a prompt after dragging the suggestion strip', async () => {
    render(
      <StudioChatStream
        messages={[{ id: 'user-1', sender: 'user', text: 'Xin chào', timestamp: '10:00' }]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={['orders']}
      />
    );

    const strip = screen.getByTestId('prompt-suggestion-strip');
    Object.defineProperty(strip, 'clientWidth', { configurable: true, value: 240 });
    Object.defineProperty(strip, 'scrollWidth', { configurable: true, value: 720 });
    fireEvent.pointerDown(strip, { pointerId: 1, clientX: 200, isPrimary: true });
    fireEvent.pointerMove(strip, { pointerId: 1, clientX: 80, isPrimary: true });
    fireEvent.pointerUp(strip, { pointerId: 1, clientX: 80, isPrimary: true });

    expect(strip.scrollLeft).toBe(120);
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    fireEvent.click(screen.getByText('Doanh thu thuần đơn hàng thành công'));

    const textarea = screen.getByPlaceholderText(/Mô tả chỉ số bạn muốn tạo/i) as HTMLTextAreaElement;
    expect(textarea.value).toBe(
      'Tính tổng doanh thu thuần của các đơn hàng có trạng thái hoàn thành (Net Revenue)',
    );
  });

  it('renders formula display with function and expression parts', () => {
    render(
      <StudioChatStream
        messages={[
          {
            id: '1',
            sender: 'assistant',
            text: 'Gợi ý',
            timestamp: '10:00',
            suggestions: [
              {
                definition: {
                  metric: {
                    name: 'AOV',
                    formula: { function: 'AVG', expression: 'total_amount' },
                    base_entity: 'orders',
                    filters: [],
                    status: 'pending_approval',
                    confidence: 'medium',
                    excluded_notes: '',
                  },
                },
                yaml_preview: 'metric:\n  name: AOV\n',
              },
            ],
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
      />
    );
    // Formula should show function and expression
    expect(screen.getByText('AVG')).toBeInTheDocument();
    expect(screen.getAllByText('total_amount').length).toBeGreaterThanOrEqual(1);
  });

  it('renders refine and edit buttons on suggestion cards', () => {
    render(
      <StudioChatStream
        messages={[
          {
            id: '1',
            sender: 'assistant',
            text: 'Gợi ý',
            timestamp: '10:00',
            suggestions: [
              {
                definition: {
                  metric: {
                    name: 'Doanh thu',
                    formula: { function: 'SUM', expression: 'price' },
                    base_entity: 'orders',
                    filters: [],
                    status: 'pending_approval',
                    confidence: 'high',
                    excluded_notes: '',
                  },
                },
                yaml_preview: 'metric:\n  name: Doanh thu\n',
              },
            ],
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={[]}
      />
    );
    // Refine with AI button
    expect(screen.getByRole('button', { name: /Nhờ AI tinh chỉnh/i })).toBeInTheDocument();
    // Edit manually button
    expect(screen.getByRole('button', { name: /Chỉnh sửa thủ công/i })).toBeInTheDocument();
  });

  it('shows loading state with analysis message', () => {
    render(
      <StudioChatStream
        messages={[]}
        onSendMessage={vi.fn()}
        isLoading={true}
        tableNames={[]}
      />
    );
    expect(screen.getByText(/AI đang phân tích/i)).toBeInTheDocument();
  });
});


