'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { MessageSquare, Plus } from 'lucide-react';

import {
  ChatMessageItem,
  ChatSessionItem,
  createMetricApi,
  DuplicateMetricNotice,
  generateCustomMetricsApi,
  getChatSessionDetailApi,
  MetricSuggestion,
  METRIC_WRITE_PERMISSION_MESSAGE,
  SemanticLayerData,
  isPermissionDenied,
  sendChatOrchestratorApi,
} from '@/lib/api';
import { ChatMessage, StudioChatStream } from '@/components/studio/StudioChatStream';
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
  const semanticDbId = layer.semantic_db_id;
  const canGenerateMetrics = mode === 'metric_studio';
  const requestVersion = useRef(0);

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

  const appendDedupeWarning = (dedupeSkipped: boolean) => {
    if (!dedupeSkipped) return;
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        sender: 'assistant',
        text: '⚠️ Không kiểm tra được trùng lặp (dedupe unavailable) — danh sách chưa so với metric đã lưu.',
        timestamp: now(),
      },
    ]);
  };

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
      let suggestions: MetricSuggestion[] = [];
      let duplicates: DuplicateMetricNotice[] = [];
      let dedupeSkipped = false;
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
        if (response.intent === 'chitchat' || response.intent === 'data_question') {
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
        suggestions = response.suggestions || [];
        duplicates = response.duplicates ?? [];
        dedupeSkipped = response.dedupe_performed === false;
        setMessages((current) => [
          ...current,
          {
            id: response.assistant_message_id || crypto.randomUUID(),
            sender: 'assistant',
            text:
              response.chat_response ||
              (suggestions.length
                ? `Dựa trên schema của bạn, tôi đề xuất ${suggestions.length} Metric Definition dưới đây. Bạn có thể xem trước YAML và lưu vào catalog để duyệt:`
                : duplicates.length
                  ? 'Không có metric mới — các chỉ số đề xuất đã tồn tại trong hệ thống:'
                  : 'Không sinh được metric phù hợp từ schema.'),
            suggestions,
            duplicates,
            timestamp: now(),
          },
        ]);
      } catch (error) {
        if (!canGenerateMetrics) throw error;
        const res = await generateCustomMetricsApi(String(semanticDbId), prompt, _targetTables);
        suggestions = res.suggestions || [];
        duplicates = res.duplicates ?? [];
        dedupeSkipped = res.dedupe_performed === false;
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            sender: 'assistant',
            text: suggestions.length
              ? `Dựa trên schema của bạn, tôi đề xuất ${suggestions.length} Metric Definition dưới đây. Bạn có thể xem trước YAML và lưu vào catalog để duyệt:`
              : duplicates.length
                ? 'Không có metric mới — các chỉ số đề xuất đã tồn tại trong hệ thống:'
                : 'Không sinh được metric phù hợp từ schema.',
            suggestions,
            duplicates,
            timestamp: now(),
          },
        ]);
      }
      appendDedupeWarning(dedupeSkipped);
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
      suggestions: message.suggestions?.map((item, i) => (i === index ? applySuggestedName(item) : item)),
    }));

  const discardSuggestion = (messageId: string, index: number): void =>
    updateMessage(messageId, (message) => ({
      ...message,
      suggestions: message.suggestions?.filter((_, i) => i !== index),
    }));

  const dismissDuplicate = (messageId: string, index: number): void =>
    updateMessage(messageId, (message) => ({
      ...message,
      duplicates: message.duplicates?.filter((_, i) => i !== index),
    }));

  const useExistingDuplicate = (messageId: string, index: number): void =>
    updateMessage(messageId, (message) => {
      if (!message.duplicates?.[index]) return message;
      const duplicates = message.duplicates.map((item, i) => (i === index ? { ...item, resolved: true } : item));
      const allSettled = duplicates.length > 0 && duplicates.every((item) => item.resolved);
      const hasSuggestions = (message.suggestions?.length ?? 0) > 0;
      // Description line is stale once every notice is resolved and nothing else shows.
      return { ...message, duplicates, text: allSettled && !hasSuggestions ? '' : message.text };
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
        <StudioChatStream
          messages={messages}
          onSendMessage={send}
          isLoading={loading || loadingSessions}
          tableNames={layer.tables.map((table) => table.table_name)}
          onAddMetric={canGenerateMetrics ? save : undefined}
          onEditMetric={canGenerateMetrics ? onEditMetricRequest : undefined}
          onRenameSuggestion={renameSuggestion}
          onDiscardSuggestion={discardSuggestion}
          onDismissDuplicate={dismissDuplicate}
          onUseExistingDuplicate={useExistingDuplicate}
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
