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
    expect(screen.getByText(/Gợi ý/i)).toBeInTheDocument();

    // Verify sample suggestions
    const suggestionChip = screen.getByText('Doanh thu thuần đơn hàng thành công');
    expect(suggestionChip).toBeInTheDocument();

    // Click suggestion chip
    fireEvent.click(suggestionChip);

    // Verify input textarea is populated
    const textarea = screen.getByPlaceholderText(/Mô tả chỉ số bạn muốn tạo/i) as HTMLTextAreaElement;
    expect(textarea.value).toContain('Tính tổng doanh thu thuần của các đơn hàng');
  });

  it('hides suggested questions after the user sends the first query', () => {
    render(
      <StudioChatStream
        messages={[
          {
            id: 'u1',
            sender: 'user',
            text: 'Tính tổng doanh thu',
            timestamp: '10:00',
          },
        ]}
        onSendMessage={vi.fn()}
        isLoading={false}
        tableNames={['orders']}
      />
    );

    expect(screen.queryByText(/Gợi ý câu hỏi tạo Metric/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Doanh thu thuần đơn hàng thành công')).not.toBeInTheDocument();
  });
});


