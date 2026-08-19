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
    expect(screen.getByText(/GỢI Ý CÂU HỎI VỀ DỮ LIỆU/i)).toBeInTheDocument();
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

  it('renders suggested question chips and populates the input when clicked', async () => {
    const { fireEvent } = await import('@testing-library/react');
    render(
      <StudioChatStream
        messages={[]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={['orders', 'customers']}
      />
    );

    // Verify suggested questions header
    expect(screen.getByText(/GỢI Ý CÂU HỎI TẠO METRIC/i)).toBeInTheDocument();

    // Verify sample suggestions
    const suggestionChip = screen.getByText('Doanh thu thuần đơn hàng thành công');
    expect(suggestionChip).toBeInTheDocument();

    // Click suggestion chip
    fireEvent.click(suggestionChip);

    // Verify input textarea is populated
    const textarea = screen.getByPlaceholderText(/Mô tả chỉ số bạn muốn tạo/i) as HTMLTextAreaElement;
    expect(textarea.value).toContain('Tính tổng doanh thu thuần của các đơn hàng');
  });

  it('allows user to toggle off/on suggested questions via checkbox', async () => {
    const { fireEvent } = await import('@testing-library/react');
    render(
      <StudioChatStream
        messages={[]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={['orders']}
      />
    );

    // Should initially show suggestions
    expect(screen.getByText('Doanh thu thuần đơn hàng thành công')).toBeInTheDocument();

    // Checkbox is checked
    const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
    expect(checkbox.checked).toBe(true);

    // Click checkbox to turn off
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);

    // Suggestion chips should now be hidden
    expect(screen.queryByText('Doanh thu thuần đơn hàng thành công')).not.toBeInTheDocument();
    expect(screen.getByText(/Đã ẩn \(Tick để hiện\)/i)).toBeInTheDocument();

    // Click again to turn back on
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);
    expect(screen.getByText('Doanh thu thuần đơn hàng thành công')).toBeInTheDocument();
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


