'use client';

import { useEffect, useState } from 'react';

import { createMetricApi, DuplicateMetricNotice, generateCustomMetricsApi, MetricSuggestion, SemanticLayerData, sendChatOrchestratorApi } from '@/lib/api';
import { ChatMessage, StudioChatStream } from '@/components/studio/StudioChatStream';
import { applySuggestedName } from '@/lib/metrics';

interface AIStudioViewProps {
  layer: SemanticLayerData;
  theme: 'light' | 'dark';
  onMetricsChanged: () => Promise<void> | void;
  onEditMetricRequest: (metric: MetricSuggestion) => void;
}

export function AIStudioView({ layer, theme, onMetricsChanged, onEditMetricRequest }: AIStudioViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [activePrompt, setActivePrompt] = useState('');
  const semanticDbId = layer.semantic_db_id;

  useEffect(() => {
    setMessages([{ id: 'welcome', sender: 'assistant', text: `Xin chào! Tôi có thể trả lời thắc mắc hoặc giúp bạn sinh chỉ số (Business Metrics) cho ${layer.db_name}.`, timestamp: now() }]);
  }, [layer.db_name, semanticDbId]);

  const appendResults = (
    suggestions: MetricSuggestion[],
    duplicates: DuplicateMetricNotice[],
    dedupeSkipped: boolean
  ) => {
    const text = suggestions.length
      ? `Đã đề xuất ${suggestions.length} Metric Definition:`
      : duplicates.length
        ? 'Không có metric mới — các chỉ số đề xuất đã tồn tại trong hệ thống:'
        : 'Không sinh được metric phù hợp từ schema.';
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), sender: 'assistant', text, suggestions, duplicates, dedupeSkipped, timestamp: now() },
    ]);
  };

  const send = async (prompt: string, _targetTables: string[]) => {
    setMessages((current) => [...current, { id: crypto.randomUUID(), sender: 'user', text: prompt, timestamp: now() }]);
    if (!semanticDbId) return appendError(setMessages, 'Semantic Layer đang được khởi tạo. Vui lòng tải lại sau khi enrichment hoàn tất.');
    setLoading(true);
    try {
      let suggestions: MetricSuggestion[] = [];
      let duplicates: DuplicateMetricNotice[] = [];
      let dedupeSkipped = false;
      try {
        const response = await sendChatOrchestratorApi(String(semanticDbId), prompt);
        if (response.intent === 'chitchat') {
          setMessages((current) => [...current, { id: crypto.randomUUID(), sender: 'assistant', text: response.chat_response || 'Xin chào! Tôi có thể giúp gì cho bạn?', timestamp: now() }]);
          return;
        }
        suggestions = response.suggestions || [];
        duplicates = response.duplicates ?? [];
        dedupeSkipped = response.dedupe_performed === false;
      } catch {
        const res = await generateCustomMetricsApi(String(semanticDbId), prompt, _targetTables);
        suggestions = res.suggestions;
        duplicates = res.duplicates;
        dedupeSkipped = res.dedupe_performed === false;
      }
      appendResults(suggestions, duplicates, dedupeSkipped);
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

  const keepName = (messageId: string, index: number): void =>
    updateMessage(messageId, (message) => ({
      ...message,
      suggestions: message.suggestions?.map((item, i) => (i === index ? stripConflict(item) : item)),
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
    <div className="flex h-[calc(100vh-130px)] min-h-[620px] w-full flex-col">
      <StudioChatStream
        messages={messages}
        onSendMessage={send}
        isLoading={loading}
        tableNames={layer.tables.map((table) => table.table_name)}
        onAddMetric={save}
        onEditMetric={onEditMetricRequest}
        onRenameSuggestion={renameSuggestion}
        onDiscardSuggestion={discardSuggestion}
        onKeepName={keepName}
        onDismissDuplicate={dismissDuplicate}
        onUseExistingDuplicate={useExistingDuplicate}
        onRefineWithAI={(suggestion) =>
          setActivePrompt(`Hãy điều chỉnh chỉ số ${suggestion.definition.metric.name}: `)
        }
        activePromptText={activePrompt}
        theme={theme}
      />
    </div>
  );
}

function appendError(setter: React.Dispatch<React.SetStateAction<ChatMessage[]>>, text: string): void {
  setter((current) => [...current, { id: crypto.randomUUID(), sender: 'assistant', text, timestamp: now(), isError: true }]);
}

function stripConflict(suggestion: MetricSuggestion): MetricSuggestion {
  const { conflict: _resolved, ...rest } = suggestion;
  return rest;
}

function now(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
