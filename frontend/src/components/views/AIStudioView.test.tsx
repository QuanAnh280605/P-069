import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    submitMetricRequestApi: vi.fn(),
    createMetricApi: vi.fn(),
  };
});

// Capture the props AIStudioView forwards to StudioChatStream so the role-based
// capability wiring (save vs submit) can be asserted without coupling to
// StudioChatStream's internal DOM. The real component still renders, so the
// existing clarification/query tests keep working.
let lastStudioChatStreamProps: any = null;
vi.mock('@/components/studio/StudioChatStream', async () => {
  const actual = await vi.importActual<typeof import('@/components/studio/StudioChatStream')>(
    '@/components/studio/StudioChatStream',
  );
  return {
    ...actual,
    StudioChatStream: (props: any) => {
      lastStudioChatStreamProps = props;
      const Real = (actual as any).StudioChatStream;
      return Real ? <Real {...props} /> : null;
    },
  };
});

const mockLayer: api.SemanticLayerData = {
  id: 'layer-1',
  db_name: 'ecom_live',
  db_type: 'postgresql',
  status: 'Saved',
  updated_at: '2024-01-01T00:00:00Z',
  source_type: 'live',
  semantic_db_id: 101,
  tables: [{ table_name: 'orders', business_name: 'Đơn hàng', description: 'Bảng đơn hàng', columns: [] }],
  metrics: [],
};

const clarificationResponse = (overrides: Partial<api.ChatOrchestratorResponse> = {}) =>
  ({
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
    ...overrides,
  }) as api.ChatOrchestratorResponse;

const sendAndAwaitClarification = async () => {
  const textarea = screen.getByPlaceholderText(/Hỏi về schema/i);
  fireEvent.change(textarea, { target: { value: 'Doanh thu' } });
  fireEvent.click(screen.getByRole('button', { name: /Send message/i }));

  await waitFor(() => expect(screen.getByTestId('clarification-card')).toBeInTheDocument());
};

describe('AIStudioView', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    lastStudioChatStreamProps = null;
  });

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

  it('resolves an option in place without a duplicate user bubble', async () => {
    vi.mocked(api.sendChatOrchestratorApi)
      .mockResolvedValueOnce(clarificationResponse())
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

    await sendAndAwaitClarification();
    fireEvent.click(within(screen.getByTestId('clarification-card')).getByText(/Theo khách hàng/i));

    await waitFor(() => {
      const msgs = lastStudioChatStreamProps.messages;
      expect(msgs.filter((m: any) => m.sender === 'user').length).toBe(1);
      const resolved = msgs.find((m: any) => m.id === 'a-1');
      expect(resolved?.clarificationResolution?.status).toBe('answered');
      expect(resolved?.clarificationResolution?.selected_option_id).toBe('opt_1');
      expect(msgs.find((m: any) => m.id === 'a-2')).toBeTruthy();
      expect(screen.getByText('Alpha')).toBeInTheDocument();
      expect(screen.getByText('1,000,000')).toBeInTheDocument();
    });
  });

  it('creates exactly one user bubble for a custom answer then the AI continuation', async () => {
    vi.mocked(api.sendChatOrchestratorApi)
      .mockResolvedValueOnce(clarificationResponse())
      .mockResolvedValueOnce({
        intent: 'chitchat',
        chat_response: 'Cảm ơn, tôi đã hiểu ý bạn.',
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

    await sendAndAwaitClarification();
    const input = screen.getByLabelText(/Câu trả lời tùy chỉnh/i);
    fireEvent.change(input, { target: { value: '  Theo khu vực  ' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      const msgs = lastStudioChatStreamProps.messages;
      expect(msgs.filter((m: any) => m.sender === 'user').length).toBe(2);
      const customUser = msgs.find((m: any) => m.sender === 'user' && m.text === 'Theo khu vực');
      expect(customUser).toBeTruthy();
      const resolved = msgs.find((m: any) => m.id === 'a-1');
      expect(resolved?.clarificationResolution?.status).toBe('answered');
      expect(resolved?.clarificationResolution?.custom_answer).toBe('Theo khu vực');
      expect(msgs.find((m: any) => m.id === 'a-2')).toBeTruthy();
    });
  });

  it('skips without a user bubble or continuation', async () => {
    vi.mocked(api.sendChatOrchestratorApi)
      .mockResolvedValueOnce(clarificationResponse())
      .mockResolvedValueOnce({
        intent: 'clarification_skipped',
        chat_response: 'Đã bỏ qua',
        session_id: 'sess-1',
        user_message_id: 'a-1',
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

    await sendAndAwaitClarification();
    fireEvent.click(within(screen.getByTestId('clarification-card')).getByText(/Skip/i));

    await waitFor(() => {
      const msgs = lastStudioChatStreamProps.messages;
      expect(msgs.filter((m: any) => m.sender === 'user').length).toBe(1);
      const resolved = msgs.find((m: any) => m.id === 'a-1');
      expect(resolved?.clarificationResolution?.status).toBe('skipped');
      expect(msgs.some((m: any) => m.id === 'a-2')).toBe(false);
    });
  });

  it('shows one inline error on failure and retries successfully', async () => {
    vi.mocked(api.sendChatOrchestratorApi)
      .mockResolvedValueOnce(clarificationResponse())
      .mockRejectedValueOnce(new Error('Lỗi mạng'))
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

    await sendAndAwaitClarification();
    fireEvent.click(within(screen.getByTestId('clarification-card')).getByText(/Theo khách hàng/i));

    await waitFor(() => {
      expect(lastStudioChatStreamProps.messages.find((m: any) => m.id === 'a-1')?.clarificationError).toBeTruthy();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Thử lại/i }));

    await waitFor(() => {
      expect(
        lastStudioChatStreamProps.messages.find((m: any) => m.id === 'a-1')?.clarificationResolution?.status,
      ).toBe('answered');
    });
  });

  it('rehydrates a resolved clarification as non-interactive with prompt and label', async () => {
    vi.mocked(api.getChatSessionDetailApi).mockResolvedValueOnce({
      id: 'sess-1',
      db_id: 101,
      title: 'Cuộc trò chuyện',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      message_count: 2,
      messages: [
        {
          id: 'a-0',
          session_id: 'sess-1',
          sequence_no: 1,
          sender: 'user',
          content: 'Doanh thu',
          intent: null,
          metadata_json: null,
          created_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'a-1',
          session_id: 'sess-1',
          sequence_no: 2,
          sender: 'assistant',
          content: 'Bạn muốn xem theo?',
          intent: null,
          metadata_json: {
            clarification: {
              prompt: 'Bạn muốn xem theo?',
              options: [
                { id: 'opt_1', label: 'Theo khách hàng', spec: { metric_ids: [1], dimensions: [] } },
              ],
              selected_option_id: 'opt_1',
              selected_label: 'Theo khách hàng',
              resolution_kind: 'option',
              resolved_at: '2024-01-01T00:00:01Z',
            },
          },
          created_at: '2024-01-01T00:00:00Z',
        },
      ],
    });

    render(
      <AIStudioView
        layer={mockLayer}
        theme="light"
        mode="data_assistant"
        activeSessionId="sess-1"
        onMetricsChanged={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('clarification-resolved')).toBeInTheDocument();
      expect(within(screen.getByTestId('clarification-resolved')).getByText('Theo khách hàng')).toBeInTheDocument();
    });
    expect(screen.queryByText(/Something else/i)).not.toBeInTheDocument();
  });

  it('produces a single API call on rapid double-click', async () => {
    let release!: () => void;
    const blocker = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.mocked(api.sendChatOrchestratorApi)
      .mockResolvedValueOnce(clarificationResponse())
      .mockImplementationOnce(async () => {
        await blocker;
        return {
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
        } as api.ChatOrchestratorResponse;
      });

    render(
      <AIStudioView
        layer={mockLayer}
        theme="light"
        mode="data_assistant"
        onMetricsChanged={vi.fn()}
      />
    );

    await sendAndAwaitClarification();
    const optionButton = within(screen.getByTestId('clarification-card')).getByText(/Theo khách hàng/i);
    fireEvent.click(optionButton);
    fireEvent.click(optionButton);

    await waitFor(() => expect(api.sendChatOrchestratorApi).toHaveBeenCalledTimes(2));
    release();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.sendChatOrchestratorApi).toHaveBeenCalledTimes(2);
  });
});

describe('AIStudioView role capability matrix', () => {
  const matrixLayer: api.SemanticLayerData = {
    id: 'layer-1',
    db_name: 'ecom_live',
    db_type: 'postgresql',
    status: 'Saved',
    updated_at: '2024-01-01T00:00:00Z',
    source_type: 'live',
    semantic_db_id: 101,
    tables: [{ table_name: 'orders', business_name: 'Đơn hàng', description: 'Bảng đơn hàng', columns: [] }],
    metrics: [],
  };

  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    lastStudioChatStreamProps = null;
  });

  it('Data Lead (metric_studio) exposes direct save, not submit request', () => {
    render(
      <AIStudioView
        layer={matrixLayer}
        theme="light"
        mode="metric_studio"
        canSubmitMetric={false}
        onMetricsChanged={vi.fn()}
      />
    );

    expect(lastStudioChatStreamProps.onAddMetric).toBeTypeOf('function');
    expect(lastStudioChatStreamProps.onSubmitMetricRequest).toBeUndefined();
  });

  it('Member (data_assistant + canSubmitMetric) exposes submit request, not direct save', () => {
    render(
      <AIStudioView
        layer={matrixLayer}
        theme="light"
        mode="data_assistant"
        canSubmitMetric
        onMetricsChanged={vi.fn()}
      />
    );

    expect(lastStudioChatStreamProps.onSubmitMetricRequest).toBeTypeOf('function');
    expect(lastStudioChatStreamProps.onAddMetric).toBeUndefined();
    expect(lastStudioChatStreamProps.showSuggestionAuthoringTools).toBe(false);
  });

  it('invokes submitMetricRequestApi, notifies user and triggers onMetricsChanged when submitting request', async () => {
    const onNotify = vi.fn();
    const onMetricsChanged = vi.fn();
    vi.mocked(api.submitMetricRequestApi).mockResolvedValueOnce({
      id: 99,
      db_id: 1,
      requester_id: 10,
      assistant_message_id: 'msg-123',
      suggestion_index: 0,
      definition: {} as any,
      status: 'pending',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    render(
      <AIStudioView
        layer={matrixLayer}
        theme="light"
        mode="data_assistant"
        canSubmitMetric
        onNotify={onNotify}
        onMetricsChanged={onMetricsChanged}
      />
    );

    expect(lastStudioChatStreamProps.onSubmitMetricRequest).toBeTypeOf('function');
    await lastStudioChatStreamProps.onSubmitMetricRequest('msg-123', 0);

    expect(api.submitMetricRequestApi).toHaveBeenCalledWith('101', 'msg-123', 0);
    expect(onNotify).toHaveBeenCalledWith('Đã gửi yêu cầu cho Data Lead xem xét.');
    expect(onMetricsChanged).toHaveBeenCalled();
  });

  it('Admin (data_assistant, no canSubmitMetric) exposes neither save nor submit, but chat remains', () => {
    render(
      <AIStudioView
        layer={matrixLayer}
        theme="light"
        mode="data_assistant"
        canSubmitMetric={false}
        onMetricsChanged={vi.fn()}
      />
    );

    expect(lastStudioChatStreamProps.onAddMetric).toBeUndefined();
    expect(lastStudioChatStreamProps.onSubmitMetricRequest).toBeUndefined();
    // Ordinary AI Chat / Data Assistant remains available for Admin.
    expect(
      screen.getAllByText(/Xin chào! Tôi có thể giúp bạn tìm hiểu schema/i).length,
    ).toBeGreaterThan(0);
  });

  it('renders metric suggestions immediately when clarification resolves with generated metrics', async () => {
    const mockMetricSuggestion = {
      name: 'Doanh thu trung bình',
      definition: {
        metric: { name: 'avg_order_value', type: 'average' },
        formula: { function: 'AVG', expression: 'price' },
      },
    };
    vi.mocked(api.sendChatOrchestratorApi)
      .mockResolvedValueOnce(clarificationResponse())
      .mockResolvedValueOnce({
        intent: 'metric_query',
        chat_response: 'Đã đề xuất 1 Metric Definition.',
        suggestions: [mockMetricSuggestion as any],
        session_id: 'sess-1',
        user_message_id: null,
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

    await sendAndAwaitClarification();
    fireEvent.click(within(screen.getByTestId('clarification-card')).getByText(/Theo khách hàng/i));

    await waitFor(() => {
      const msgs = lastStudioChatStreamProps.messages;
      const continuation = msgs.find((m: any) => m.id === 'a-2');
      expect(continuation).toBeTruthy();
      expect(continuation?.suggestions?.length).toBe(1);
      expect(continuation?.text).toContain('Đã đề xuất 1 Metric Definition.');
    });
  });
});
