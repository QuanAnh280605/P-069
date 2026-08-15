'use client';

import { useEffect, useState } from 'react';

import { createMetricApi, generateCustomMetricsApi, MetricSuggestion, SemanticLayerData, sendChatOrchestratorApi } from '@/lib/api';
import { ChatMessage, StudioChatStream } from '@/components/studio/StudioChatStream';

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

  const send = async (prompt: string, _targetTables: string[]) => {
    setMessages((current) => [...current, { id: crypto.randomUUID(), sender: 'user', text: prompt, timestamp: now() }]);
    if (!semanticDbId) return appendError(setMessages, 'Semantic Layer đang được khởi tạo. Vui lòng tải lại sau khi enrichment hoàn tất.');
    setLoading(true);
    try {
      let suggestions: MetricSuggestion[] = [];
      try {
        const response = await sendChatOrchestratorApi(String(semanticDbId), prompt);
        if (response.intent === 'chitchat') {
          setMessages((current) => [...current, { id: crypto.randomUUID(), sender: 'assistant', text: response.chat_response || 'Xin chào! Tôi có thể giúp gì cho bạn?', timestamp: now() }]);
          return;
        }
        suggestions = response.suggestions || [];
      } catch {
        const res = await generateCustomMetricsApi(String(semanticDbId), prompt, _targetTables);
        suggestions = res.suggestions || [];
      }
      setMessages((current) => [...current, { id: crypto.randomUUID(), sender: 'assistant', text: suggestions.length ? `Đã đề xuất ${suggestions.length} Metric Definition:` : 'Không sinh được metric phù hợp từ schema.', suggestions, timestamp: now() }]);
    } catch (error) {
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể xử lý yêu cầu');
    } finally {
      setLoading(false);
    }
  };

  const save = async (suggestion: MetricSuggestion) => {
    if (!semanticDbId) throw new Error('Semantic database chưa sẵn sàng');
    await createMetricApi(String(semanticDbId), { definition: suggestion.definition, source: 'ai' });
    await onMetricsChanged();
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

function now(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
