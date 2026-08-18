'use client';

import { useEffect, useRef, useState } from 'react';

import {
  ChatMessageItem,
  ChatSessionItem,
  createChatSessionApi,
  createMetricApi,
  deleteChatSessionApi,
  getChatSessionDetailApi,
  listChatSessionsApi,
  MetricSuggestion,
  SemanticLayerData,
  sendChatOrchestratorApi,
  updateChatSessionTitleApi,
} from '@/lib/api';
import { ChatMessage, StudioChatStream } from '@/components/studio/StudioChatStream';

interface AIStudioViewProps {
  layer: SemanticLayerData;
  theme: 'light' | 'dark';
  onMetricsChanged: () => Promise<void> | void;
  onEditMetricRequest: (metric: MetricSuggestion) => void;
}

export function AIStudioView({ layer, theme, onMetricsChanged, onEditMetricRequest }: AIStudioViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activePrompt, setActivePrompt] = useState('');
  const semanticDbId = layer.semantic_db_id;
  const requestVersion = useRef(0);

  useEffect(() => {
    requestVersion.current += 1;
    setActiveSessionId(null);
    setMessages([]);
    if (!semanticDbId || layer.source_type !== 'live') return;
    void loadSessions(String(semanticDbId));
  }, [layer.db_name, layer.source_type, semanticDbId]);

  const loadSessions = async (dbId: string) => {
    setLoadingSessions(true);
    try {
      const items = await listChatSessionsApi(dbId);
      setSessions(items);
      const fromUrl = new URLSearchParams(window.location.search).get('chat');
      const selected = items.find((item) => item.id === fromUrl) || items[0];
      if (selected) await selectSession(dbId, selected.id);
      else showWelcome();
    } catch (error) {
      showWelcome(error instanceof Error ? error.message : 'Không thể tải lịch sử chat.');
    } finally {
      setLoadingSessions(false);
    }
  };

  const showWelcome = (error?: string) => {
    setMessages([
      {
        id: 'welcome',
        sender: 'assistant',
        text: error || `Xin chào! Tôi có thể trả lời thắc mắc hoặc giúp bạn sinh chỉ số (Business Metrics) cho ${layer.db_name}.`,
        timestamp: now(),
        isError: Boolean(error),
      },
    ]);
  };

  const updateUrl = (sessionId: string | null) => {
    const url = new URL(window.location.href);
    if (sessionId) url.searchParams.set('chat', sessionId);
    else url.searchParams.delete('chat');
    window.history.replaceState({}, '', url);
  };

  const selectSession = async (dbId: string, sessionId: string) => {
    const version = ++requestVersion.current;
    setActiveSessionId(sessionId);
    updateUrl(sessionId);
    setLoadingSessions(true);
    try {
      const detail = await getChatSessionDetailApi(dbId, sessionId);
      if (version !== requestVersion.current) return;
      setMessages(detail.messages.filter((item) => item.sender !== 'system').map(toChatMessage));
    } catch (error) {
      if (version === requestVersion.current) appendError(setMessages, error instanceof Error ? error.message : 'Không thể tải lịch sử chat.');
    } finally {
      if (version === requestVersion.current) setLoadingSessions(false);
    }
  };

  const newChat = async () => {
    if (!semanticDbId || layer.source_type !== 'live') return;
    try {
      const session = await createChatSessionApi(String(semanticDbId));
      setSessions((current) => [session, ...current]);
      setActiveSessionId(session.id);
      setMessages([]);
      updateUrl(session.id);
    } catch (error) {
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể tạo cuộc trò chuyện mới.');
    }
  };

  const handleRenameSession = async (sessionId: string, newTitle: string) => {
    if (!semanticDbId) return;
    try {
      const updated = await updateChatSessionTitleApi(String(semanticDbId), sessionId, newTitle);
      setSessions((current) =>
        current.map((item) => (item.id === sessionId ? { ...item, title: updated.title } : item))
      );
    } catch (error) {
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể đổi tên cuộc trò chuyện.');
    }
  };

  const removeSession = async (sessionId: string) => {
    if (!semanticDbId) return;
    try {
      await deleteChatSessionApi(String(semanticDbId), sessionId);
      const remaining = sessions.filter((item) => item.id !== sessionId);
      setSessions(remaining);
      if (activeSessionId === sessionId) {
        const next = remaining[0];
        if (next) await selectSession(String(semanticDbId), next.id);
        else {
          setActiveSessionId(null);
          setMessages([]);
          updateUrl(null);
        }
      }
    } catch (error) {
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể xóa cuộc trò chuyện.');
    }
  };

  const send = async (prompt: string, _targetTables: string[]) => {
    const clientMessageId = crypto.randomUUID();
    const requestSessionId = activeSessionId;
    setMessages((current) => [...current, { id: clientMessageId, sender: 'user', text: prompt, timestamp: now() }]);
    if (!semanticDbId) return appendError(setMessages, 'Semantic Layer đang được khởi tạo. Vui lòng tải lại sau khi enrichment hoàn tất.');
    setLoading(true);
    try {
      const response = await sendChatOrchestratorApi(String(semanticDbId), prompt, requestSessionId, clientMessageId);
      if (requestSessionId && activeSessionId !== requestSessionId) return;
      setActiveSessionId(response.session_id);
      updateUrl(response.session_id);
      const suggestions = response.suggestions || [];
      setMessages((current) => [...current, {
        id: response.assistant_message_id,
        sender: 'assistant',
        text: response.chat_response || (suggestions.length ? `Đã đề xuất ${suggestions.length} Metric Definition.` : 'Không sinh được metric phù hợp từ schema.'),
        suggestions,
        timestamp: now(),
      }]);
      if (response.session) {
        setSessions((current) => [response.session!, ...current.filter((item) => item.id !== response.session!.id)]);
      }
    } catch (error) {
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể xử lý yêu cầu');
    } finally {
      setLoading(false);
    }
  };

  const save = async (suggestion: MetricSuggestion) => {
    if (!semanticDbId) {
      appendError(setMessages, 'Semantic database chưa sẵn sàng hoặc đã bị xóa. Vui lòng tải lại trang.');
      return;
    }
    try {
      await createMetricApi(String(semanticDbId), { definition: suggestion.definition, source: 'ai' });
      await onMetricsChanged();
    } catch (error) {
      appendError(
        setMessages,
        `Không thể lưu chỉ số "${suggestion.definition.metric.name}": ${error instanceof Error ? error.message : 'Lỗi không xác định'}`
      );
      throw error;
    }
  };

  return (
    <div className="flex h-[calc(100vh-130px)] min-h-[620px] w-full">
      <div className="min-w-0 flex-1 h-full">
        <StudioChatStream
          messages={messages}
          onSendMessage={send}
          isLoading={loading || loadingSessions}
          tableNames={layer.tables.map((table) => table.table_name)}
          onAddMetric={save}
          onEditMetric={onEditMetricRequest}
          onRefineWithAI={(suggestion) => setActivePrompt(`Hãy điều chỉnh chỉ số ${suggestion.definition.metric.name}: `)}
          activePromptText={activePrompt}
          theme={theme}
          sessions={layer.source_type === 'live' ? sessions : undefined}
          activeSessionId={activeSessionId}
          loadingSessions={loadingSessions}
          onSelectSession={(id) => void selectSession(String(semanticDbId), id)}
          onNewChat={() => void newChat()}
          onDeleteSession={(id) => void removeSession(id)}
          onRenameSession={handleRenameSession}
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
    timestamp: new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    isError: message.metadata_json?.status === 'error',
  };
}

function appendError(setter: React.Dispatch<React.SetStateAction<ChatMessage[]>>, text: string): void {
  setter((current) => [...current, { id: crypto.randomUUID(), sender: 'assistant', text, timestamp: now(), isError: true }]);
}

function now(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
