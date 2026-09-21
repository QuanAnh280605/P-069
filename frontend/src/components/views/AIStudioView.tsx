'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { MessageSquare, Plus } from 'lucide-react';

import {
  ChatMessageItem,
  ChatSessionItem,
  ClarificationResolution,
  createMetricApi,
  getChatSessionDetailApi,
  MetricSuggestion,
  MetricRequest,
  METRIC_WRITE_PERMISSION_MESSAGE,
  SemanticLayerData,
  isPermissionDenied,
  sendChatOrchestratorApi,
  listMetricRequestsApi,
  submitMetricRequestApi,
} from '@/lib/api';
import { ChatMessage, metricRequestKey, StudioChatStream } from '@/components/studio/StudioChatStream';
import { ViewHeader } from '@/components/workspace/ViewHeader';
import { applySuggestedName, metricName } from '@/lib/metrics';

interface AIStudioViewProps {
  layer: SemanticLayerData;
  theme: 'light' | 'dark';
  sessions?: ChatSessionItem[];
  setSessions?: React.Dispatch<React.SetStateAction<ChatSessionItem[]>>;
  activeSessionId?: string | null;
  setActiveSessionId?: React.Dispatch<React.SetStateAction<string | null>>;
  loadingSessions?: boolean;
  onSelectSession?: (id: string) => void;
  onNewChat?: () => void;
  onMetricsChanged: () => Promise<void> | void;
  onEditMetricRequest?: (metric: MetricSuggestion) => void;
  onOpenCatalog?: () => void;
  onNotify?: (message: string) => void;
  mode?: 'data_assistant' | 'metric_studio';
  refreshKey?: number;
  canSubmitMetric?: boolean;
}

export function AIStudioView({
  layer,
  theme,
  sessions = [],
  setSessions,
  activeSessionId = null,
  setActiveSessionId,
  loadingSessions = false,
  onNewChat,
  onMetricsChanged,
  onEditMetricRequest,
  onOpenCatalog,
  onNotify,
  mode = 'metric_studio',
  refreshKey = 0,
  canSubmitMetric = false,
}: AIStudioViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [activePrompt, setActivePrompt] = useState('');
  const [metricRequests, setMetricRequests] = useState<MetricRequest[]>([]);
  const semanticDbId = layer.semantic_db_id;
  const canGenerateMetrics = mode === 'metric_studio';
  const requestVersion = useRef(0);
  const pendingResolutionRef = useRef<Record<string, import('@/lib/api').ChatClarificationSelection>>({});
  const inFlightRef = useRef<Set<string>>(new Set());

  const submittedRequestKeys = useMemo(
    () =>
      new Set(
        metricRequests
          .filter((item) => item.status === 'pending')
          .map((item) => metricRequestKey(item.assistant_message_id, item.suggestion_index)),
      ),
    [metricRequests],
  );

  const approvedRequestKeys = useMemo(
    () =>
      new Set(
        metricRequests
          .filter((item) => item.status === 'approved')
          .map((item) => metricRequestKey(item.assistant_message_id, item.suggestion_index)),
      ),
    [metricRequests],
  );

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId) || null,
    [sessions, activeSessionId],
  );

  const showWelcome = (error?: string) => {
    setMessages([
      {
        id: 'welcome',
        sender: 'assistant',
        text:
          error ||
          (canGenerateMetrics
            ? `Xin chào! Tôi đã quét schema cho database ${layer.db_name} (${layer.tables.length} bảng). Bạn có thể hỏi để tôi đề xuất và định nghĩa Business Metrics.`
            : `Xin chào! Tôi có thể giúp bạn tìm hiểu schema, metric đã phê duyệt và cách chọn dữ liệu trong ${layer.db_name}.`),
        timestamp: now(),
        isError: Boolean(error),
      },
    ]);
  };

  useEffect(() => {
    const version = ++requestVersion.current;
    if (!semanticDbId || layer.source_type !== 'live') {
      showWelcome();
      return;
    }

    if (!activeSessionId) {
      showWelcome();
      return;
    }

    const loadDetail = async () => {
      try {
        const detail = await getChatSessionDetailApi(String(semanticDbId), activeSessionId);
        if (version !== requestVersion.current) return;
        setMessages(detail.messages.filter((item) => item.sender !== 'system').map(toChatMessage));
      } catch (error) {
        if (version === requestVersion.current) {
          appendError(
            setMessages,
            error instanceof Error ? error.message : 'Không thể tải lịch sử cuộc trò chuyện.',
          );
        }
      }
    };

    void loadDetail();
  }, [activeSessionId, layer.db_name, layer.source_type, semanticDbId]);

  useEffect(() => {
    if (!semanticDbId || canGenerateMetrics) return;
    void listMetricRequestsApi(String(semanticDbId)).then(setMetricRequests).catch(() => setMetricRequests([]));
  }, [canGenerateMetrics, semanticDbId, refreshKey]);

  const send = async (prompt: string, _targetTables: string[]) => {
    const clientMessageId = crypto.randomUUID();
    const requestSessionId = activeSessionId;

    setMessages((current) => [
      ...current,
      { id: clientMessageId, sender: 'user', text: prompt, timestamp: now() },
    ]);
    if (!semanticDbId) {
      return appendError(
        setMessages,
        'Semantic Layer đang được khởi tạo. Vui lòng tải lại sau khi enrichment hoàn tất.',
      );
    }
    setLoading(true);
    try {
      const response = await sendChatOrchestratorApi(
        String(semanticDbId),
        prompt,
        requestSessionId,
        clientMessageId,
      );
      if (requestSessionId && activeSessionId !== requestSessionId) return;
      if (response.session_id) {
        setActiveSessionId?.(response.session_id);
        if (typeof window !== 'undefined') {
          const url = new URL(window.location.href);
          url.searchParams.set('chat', response.session_id);
          window.history.replaceState({}, '', url);
        }
      }
      if (response.session) {
        setSessions?.((current) => [
          response.session!,
          ...current.filter((item) => item.id !== response.session!.id),
        ]);
      }
      if (response.intent === 'semantic_query') {
        setMessages((current) => [
          ...current,
          {
            id: response.assistant_message_id || crypto.randomUUID(),
            sender: 'assistant',
            text: response.chat_response || '',
            queryResult: response.semantic_query_result,
            clarification: response.clarification,
            timestamp: now(),
          },
        ]);
        return;
      }
      if (response.intent === 'chitchat' || response.intent === 'data_question' || response.intent === 'out_of_scope') {
        setMessages((current) => [
          ...current,
          {
            id: response.assistant_message_id || crypto.randomUUID(),
            sender: 'assistant',
            text: response.chat_response || 'Xin chào! Tôi có thể giúp gì cho bạn?',
            timestamp: now(),
          },
        ]);
        return;
      }
      const suggestions = response.suggestions || [];
      setMessages((current) => [
        ...current,
        {
          id: response.assistant_message_id || crypto.randomUUID(),
          sender: 'assistant',
          text:
            response.chat_response ||
            (suggestions.length
              ? `Dựa trên schema của bạn, tôi đề xuất ${suggestions.length} Metric Definition dưới đây. Bạn có thể xem trước YAML và lưu vào catalog để duyệt:`
              : 'Không sinh được metric phù hợp từ schema.'),
          suggestions,
          duplicates: response.duplicates,
          dedupeSkipped: response.dedupe_performed === false,
          suggestionAction: response.suggestion_action,
          timestamp: now(),
        },
      ]);
    } catch (error) {
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể xử lý yêu cầu');
    } finally {
      setLoading(false);
    }
  };

  const reloadSessionMessages = async (sessionId: string | null | undefined): Promise<void> => {
    if (!semanticDbId || !sessionId) return;
    try {
      const detail = await getChatSessionDetailApi(String(semanticDbId), sessionId);
      setMessages(detail.messages.filter((item) => item.sender !== 'system').map(toChatMessage));
    } catch {
      // Keep current optimistic state if the reload fails.
    }
  };

  const buildResolution = (
    resolution: import('@/lib/api').ChatClarificationSelection,
    message: ChatMessage,
  ): ClarificationResolution => {
    if (resolution.skipped) return { status: 'skipped' };
    if (resolution.custom_answer) {
      return { status: 'answered', custom_answer: resolution.custom_answer };
    }
    const option = message.clarification?.options?.find((opt) => opt.id === resolution.option_id);
    return {
      status: 'answered',
      selected_option_id: resolution.option_id ?? null,
      selected_label: option?.label ?? null,
    };
  };

  const resolveClarification = async (
    assistantMessageId: string,
    resolution: { option_id?: string | null; custom_answer?: string | null; skipped?: boolean },
  ): Promise<void> => {
    if (!semanticDbId) return;
    // Synchronous guard: block duplicate in-flight requests even before React re-renders.
    if (inFlightRef.current.has(assistantMessageId)) return;

    const selection: import('@/lib/api').ChatClarificationSelection = {
      assistant_message_id: assistantMessageId,
      option_id: resolution.option_id ?? null,
      custom_answer: resolution.custom_answer ?? null,
      skipped: Boolean(resolution.skipped),
    };
    pendingResolutionRef.current[assistantMessageId] = selection;
    inFlightRef.current.add(assistantMessageId);

    const clientMessageId = crypto.randomUUID();
    const requestSessionId = activeSessionId;

    // Optimistically mark the original card pending, in place (no user bubble).
    updateMessage(assistantMessageId, (message) => ({
      ...message,
      clarificationPending: true,
      clarificationError: null,
    }));
    setLoading(true);
    try {
      const response = await sendChatOrchestratorApi(
        String(semanticDbId),
        resolution.custom_answer ?? resolution.option_id ?? (selection.skipped ? 'Bỏ qua' : 'Làm rõ'),
        requestSessionId,
        clientMessageId,
        selection,
      );
      if (requestSessionId && activeSessionId !== requestSessionId) return;
      if (response.session_id) {
        setActiveSessionId?.(response.session_id);
      }
      if (response.session) {
        setSessions?.((current) => [
          response.session!,
          ...current.filter((item) => item.id !== response.session!.id),
        ]);
      }

      // Merge canonical resolution into the original card (resolved in place).
      updateMessage(assistantMessageId, (message) => ({
        ...message,
        clarificationPending: false,
        clarificationError: null,
        clarificationResolution: response.clarification_resolution
          ? response.clarification_resolution
          : buildResolution(selection, message),
      }));
      delete pendingResolutionRef.current[assistantMessageId];

      // Skip persists and stops: no continuation, no user bubble.
      if (response.intent === 'clarification_skipped') return;

      // Custom input appends exactly one trimmed user bubble before the AI continuation.
      if (resolution.custom_answer) {
        setMessages((current) => [
          ...current,
          { id: clientMessageId, sender: 'user', text: resolution.custom_answer!, timestamp: now() },
        ]);
      }
      const suggestions = response.suggestions || [];
      setMessages((current) => [
        ...current,
        {
          id: response.assistant_message_id || crypto.randomUUID(),
          sender: 'assistant',
          text:
            response.chat_response ||
            (suggestions.length
              ? `Dựa trên schema của bạn, tôi đề xuất ${suggestions.length} Metric Definition dưới đây. Bạn có thể xem trước YAML và lưu vào catalog để duyệt:`
              : ''),
          suggestions: response.suggestions ?? undefined,
          duplicates: response.duplicates,
          dedupeSkipped: response.dedupe_performed === false,
          suggestionAction: response.suggestion_action,
          queryResult: response.semantic_query_result,
          clarification: response.clarification,
          timestamp: now(),
        },
      ]);
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'Không thể thực thi lựa chọn';
      // Backend already resolved this card: reload canonical state instead of executing again.
      if (detail === 'clarification_already_resolved') {
        delete pendingResolutionRef.current[assistantMessageId];
        await reloadSessionMessages(requestSessionId);
        return;
      }
      // Restore interactive state and surface one localized inline error (keep selection for retry).
      updateMessage(assistantMessageId, (message) => ({
        ...message,
        clarificationPending: false,
        clarificationError: detail.includes('AI phản hồi quá lâu')
          ? detail
          : 'Không thể lưu lựa chọn. Vui lòng thử lại.',
      }));
    } finally {
      inFlightRef.current.delete(assistantMessageId);
      setLoading(false);
    }
  };

  const retryClarification = (assistantMessageId: string): void => {
    const stored = pendingResolutionRef.current[assistantMessageId];
    if (!stored) return;
    void resolveClarification(assistantMessageId, {
      option_id: stored.option_id ?? undefined,
      custom_answer: stored.custom_answer ?? undefined,
      skipped: stored.skipped,
    });
  };

  const updateMessage = (messageId: string, updater: (message: ChatMessage) => ChatMessage): void => {
    setMessages((current) => current.map((message) => (message.id === messageId ? updater(message) : message)));
  };

  const renameSuggestion = (messageId: string, index: number): void =>
    updateMessage(messageId, (message) => ({
      ...message,
      suggestions: message.suggestions?.map((item, itemIndex) =>
        itemIndex === index ? applySuggestedName(item) : item,
      ),
    }));

  const discardSuggestion = (messageId: string, index: number): void =>
    updateMessage(messageId, (message) => ({
      ...message,
      suggestions: message.suggestions?.filter((_, itemIndex) => itemIndex !== index),
    }));

  const dismissDuplicate = (messageId: string, index: number): void =>
    updateMessage(messageId, (message) => ({
      ...message,
      duplicates: message.duplicates?.filter((_, itemIndex) => itemIndex !== index),
    }));

  const useExistingDuplicate = (messageId: string, index: number): void =>
    updateMessage(messageId, (message) => {
      if (!message.duplicates?.[index]) return message;
      const duplicates = message.duplicates.map((item, itemIndex) =>
        itemIndex === index ? { ...item, resolved: true } : item,
      );
      return { ...message, duplicates };
    });

  const save = async (suggestion: MetricSuggestion) => {
    if (!semanticDbId) {
      appendError(
        setMessages,
        'Semantic database chưa sẵn sàng hoặc đã bị xóa. Vui lòng tải lại trang.',
      );
      return;
    }
    try {
      await createMetricApi(String(semanticDbId), {
        definition: suggestion.definition,
        source: 'ai',
      });
      await onMetricsChanged();
    } catch (error) {
      if (isPermissionDenied(error)) onNotify?.(METRIC_WRITE_PERMISSION_MESSAGE);
      appendError(
        setMessages,
        isPermissionDenied(error)
          ? METRIC_WRITE_PERMISSION_MESSAGE
          : `Không thể lưu chỉ số "${suggestion.definition.metric.name}": ${
              error instanceof Error ? error.message : 'Lỗi không xác định'
            }`,
      );
      throw error;
    }
  };

  const submitRequest = async (assistantMessageId: string, suggestionIndex: number) => {
    if (!semanticDbId) throw new Error('Semantic database chưa sẵn sàng.');
    try {
      const request = await submitMetricRequestApi(String(semanticDbId), assistantMessageId, suggestionIndex);
      setMetricRequests((current) => [request, ...current]);
      onNotify?.('Đã gửi yêu cầu cho Data Lead xem xét.');
      await onMetricsChanged?.();
    } catch (error) {
      // The server refuses duplicate submissions — surface it instead of failing silently.
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể gửi yêu cầu.');
    }
  };

  const dbProp = {
    id: layer.id,
    name: layer.db_name,
    engine: layer.db_type === 'auto' ? ('dump' as const) : layer.db_type,
    status: 'connected' as const,
    tables: layer.tables.length,
  };

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <ViewHeader
        eyebrow={canGenerateMetrics ? 'Generate' : 'Explore'}
        title={canGenerateMetrics ? 'Metric Studio' : 'Data Assistant'}
        description={
          canGenerateMetrics
            ? 'Chat with the assistant to explore your schema and generate business metric definitions.'
            : 'Hỏi về schema, metric đã duyệt và cách khai thác dữ liệu an toàn.'
        }
        database={dbProp}
        actions={
          activeSession ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary px-3 py-1 font-sans text-xs text-secondary-foreground">
                <MessageSquare className="h-3.5 w-3.5 text-primary" />
                <span className="max-w-[200px] truncate">{activeSession.title}</span>
              </span>
              {onNewChat && (
                <button
                  type="button"
                  onClick={onNewChat}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2.5 py-1 font-sans text-xs font-medium text-foreground transition-colors hover:bg-accent cursor-pointer"
                  title="Tạo cuộc trò chuyện mới"
                >
                  <Plus className="h-3 w-3" />
                  <span>Đoạn chat mới</span>
                </button>
              )}
            </div>
          ) : onNewChat && layer.source_type === 'live' && semanticDbId ? (
            <button
              type="button"
              onClick={onNewChat}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2.5 py-1 font-sans text-xs font-medium text-foreground transition-colors hover:bg-accent cursor-pointer"
              title="Tạo cuộc trò chuyện mới"
            >
              <Plus className="h-3 w-3" />
              <span>Đoạn chat mới</span>
            </button>
          ) : undefined
        }
      />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {!canGenerateMetrics && metricRequests.length > 0 && (
          <div className="border-b border-border px-6 py-2 text-xs text-muted-foreground">
            Yêu cầu của bạn: {metricRequests.filter((item) => item.status === 'pending').length} chờ xử lý · {metricRequests.filter((item) => item.status === 'approved').length} đã duyệt.
          </div>
        )}
        <StudioChatStream
          messages={messages}
          onSendMessage={send}
          isLoading={loading || loadingSessions}
          tableNames={layer.tables.map((table) => table.table_name)}
          onAddMetric={canGenerateMetrics ? save : undefined}
          onEditMetric={canGenerateMetrics ? onEditMetricRequest : undefined}
          onRefineWithAI={
            canGenerateMetrics
              ? (suggestion) =>
                  setActivePrompt(`Hãy điều chỉnh chỉ số ${suggestion.definition.metric.name}: `)
              : undefined
          }
          activePromptText={activePrompt}
          theme={theme}
          mode={mode}
          onOpenCatalog={onOpenCatalog}
          onRenameSuggestion={renameSuggestion}
          onDiscardSuggestion={discardSuggestion}
          onDismissDuplicate={dismissDuplicate}
          onUseExistingDuplicate={useExistingDuplicate}
          onSubmitMetricRequest={canSubmitMetric ? submitRequest : undefined}
          onSelectClarification={(assistantMessageId, optionId) =>
            void resolveClarification(assistantMessageId, { option_id: optionId })
          }
          onCustomClarification={(assistantMessageId, text) =>
            void resolveClarification(assistantMessageId, { custom_answer: text })
          }
          onSkipClarification={(assistantMessageId) =>
            void resolveClarification(assistantMessageId, { skipped: true })
          }
          onRetryClarification={retryClarification}
          showSuggestionAuthoringTools={canGenerateMetrics}
          submittedRequestKeys={submittedRequestKeys}
          approvedRequestKeys={approvedRequestKeys}
          savedMetricNames={layer.metrics.map((metric) => metricName(metric))}
        />
      </div>
    </div>
  );
}

function toChatMessage(message: ChatMessageItem): ChatMessage {
  const clar = message.metadata_json?.clarification;
  const resolution: ClarificationResolution | null =
    clar && clar.resolved_at
      ? {
          status: clar.resolution_kind === 'skip' ? 'skipped' : 'answered',
          selected_option_id: clar.selected_option_id ?? null,
          selected_label: clar.selected_label ?? null,
          custom_answer: clar.custom_answer ?? null,
        }
      : null;
  return {
    id: message.id,
    sender: message.sender === 'user' ? 'user' : 'assistant',
    text: message.content,
    suggestions: message.metadata_json?.suggestions,
    duplicates: message.metadata_json?.duplicates,
    dedupeSkipped: message.metadata_json?.dedupe_performed === false,
    suggestionAction: message.metadata_json?.suggestion_action,
    queryResult: message.metadata_json?.semantic_query_result,
    clarification: clar ?? null,
    clarificationResolution: resolution,
    timestamp: new Date(message.created_at).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    }),
    isError: message.metadata_json?.status === 'error',
  };
}

function appendError(
  setter: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  text: string,
): void {
  setter((current) => [
    ...current,
    { id: crypto.randomUUID(), sender: 'assistant', text, timestamp: now(), isError: true },
  ]);
}

function now(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
