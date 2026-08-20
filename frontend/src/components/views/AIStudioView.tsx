'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { MessageSquare, Plus } from 'lucide-react';

import {
  ChatMessageItem,
  ChatSessionItem,
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
import { applySuggestedName } from '@/lib/metrics';

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
}: AIStudioViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [activePrompt, setActivePrompt] = useState('');
  const [metricRequests, setMetricRequests] = useState<MetricRequest[]>([]);
  const semanticDbId = layer.semantic_db_id;
  const canGenerateMetrics = mode === 'metric_studio';
  const requestVersion = useRef(0);

  const submittedRequestKeys = useMemo(
    () =>
      new Set(
        metricRequests
          .filter((item) => item.status === 'pending')
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
  }, [canGenerateMetrics, semanticDbId]);

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
    const request = await submitMetricRequestApi(String(semanticDbId), assistantMessageId, suggestionIndex);
    setMetricRequests((current) => [request, ...current]);
    onNotify?.('Đã gửi yêu cầu cho Data Lead xem xét.');
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
          onSubmitMetricRequest={!canGenerateMetrics ? submitRequest : undefined}
          submittedRequestKeys={submittedRequestKeys}
          savedMetricNames={layer.metrics.map((metric) => metric.name)}
        />
      </div>
    </div>
  );
}

function toChatMessage(message: ChatMessageItem): ChatMessage {
  return {
    id: message.id,
    sender: message.sender === 'user' ? 'user' : 'assistant',
    text: message.content,
    suggestions: message.metadata_json?.suggestions,
    duplicates: message.metadata_json?.duplicates,
    dedupeSkipped: message.metadata_json?.dedupe_performed === false,
    suggestionAction: message.metadata_json?.suggestion_action,
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
