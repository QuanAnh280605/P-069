import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AIStudioView } from './AIStudioView';
import * as api from '@/lib/api';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    sendChatOrchestratorApi: vi.fn(),
    getChatSessionDetailApi: vi.fn(),
    listMetricRequestsApi: vi.fn().mockResolvedValue([]),
    createMetricApi: vi.fn(),
  };
});

describe('AIStudioView', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const mockLayer: api.SemanticLayerData = {
    db_name: 'ecom_live',
    source_type: 'live',
    semantic_db_id: 101,
    tables: [{ table_name: 'orders', business_name: 'Đơn hàng', columns: [] }],
    metrics: [],
  };

  it('renders Data Assistant view header and welcome message for Member', () => {
    render(
      <AIStudioView
        layer={mockLayer}
        theme="light"
        mode="data_assistant"
        onMetricsChanged={vi.fn()}
      />
    );

    expect(screen.getByText('Data Assistant')).toBeInTheDocument();
    expect(screen.getByText(/Hỏi về schema, metric đã duyệt/i)).toBeInTheDocument();
  });

  it('renders semantic query result table when response has intent semantic_query', async () => {
    vi.mocked(api.sendChatOrchestratorApi).mockResolvedValueOnce({
      intent: 'semantic_query',
      chat_response: 'Doanh thu theo khách hàng',
      semantic_query_result: {
        spec: { metric_ids: [1], dimensions: [{ column_id: 10 }], filters: [], limit: 100 },
        columns: ['customer_name', 'total_revenue'],
        rows: [['Khách hàng Alpha', 5000000]],
        row_count: 1,
        explanation: 'Tính từ metric Doanh thu',
      },
      session_id: 'sess-1',
      user_message_id: 'u-1',
      assistant_message_id: 'a-1',
    });

    render(
      <AIStudioView
        layer={mockLayer}
        theme="light"
        mode="data_assistant"
        onMetricsChanged={vi.fn()}
      />
    );

    const textarea = screen.getByPlaceholderText(/Hỏi về schema/i);
    fireEvent.change(textarea, { target: { value: 'Tổng doanh thu theo khách hàng' } });
    const sendBtn = screen.getByRole('button', { name: /Send message/i });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.getByText('Khách hàng Alpha')).toBeInTheDocument();
      expect(screen.getByText('5,000,000')).toBeInTheDocument();
    });
  });

  it('handles clarification selection click by sending option payload', async () => {
    vi.mocked(api.sendChatOrchestratorApi)
      .mockResolvedValueOnce({
        intent: 'semantic_query',
        chat_response: 'Vui lòng làm rõ câu hỏi',
        clarification: {
          prompt: 'Bạn muốn xem theo?',
          options: [
            {
              id: 'opt_1',
              label: 'Theo khách hàng',
              spec: { metric_ids: [1], dimensions: [{ column_id: 10 }] },
            },
          ],
        },
        session_id: 'sess-1',
        user_message_id: 'u-1',
        assistant_message_id: 'a-1',
      })
      .mockResolvedValueOnce({
        intent: 'semantic_query',
        chat_response: 'Kết quả theo khách hàng',
        semantic_query_result: {
          spec: { metric_ids: [1], dimensions: [{ column_id: 10 }], filters: [], limit: 100 },
          columns: ['customer_name', 'revenue'],
          rows: [['Alpha', 1000000]],
          row_count: 1,
          explanation: 'Doanh thu khách hàng',
        },
        session_id: 'sess-1',
        user_message_id: 'u-2',
        assistant_message_id: 'a-2',
      });

    render(
      <AIStudioView
        layer={mockLayer}
        theme="light"
        mode="data_assistant"
        onMetricsChanged={vi.fn()}
      />
    );

    const textarea = screen.getByPlaceholderText(/Hỏi về schema/i);
    fireEvent.change(textarea, { target: { value: 'Doanh thu' } });
    fireEvent.click(screen.getByRole('button', { name: /Send message/i }));

    await waitFor(() => {
      expect(screen.getByText(/👉 Theo khách hàng/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/👉 Theo khách hàng/i));

    await waitFor(() => {
      expect(api.sendChatOrchestratorApi).toHaveBeenCalledWith(
        '101',
        'Theo khách hàng',
        null,
        expect.any(String),
        { assistant_message_id: 'a-1', option_id: 'opt_1' }
      );
      expect(screen.getByText('Alpha')).toBeInTheDocument();
      expect(screen.getByText('1,000,000')).toBeInTheDocument();
    });
  });
});
