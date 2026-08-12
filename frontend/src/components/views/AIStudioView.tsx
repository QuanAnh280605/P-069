'use client';

import { useEffect, useState } from 'react';

import { createMetricApi, generateCustomMetricsApi, MetricSuggestion, SemanticLayerData } from '@/lib/api';
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
    setMessages([{ id: 'welcome', sender: 'assistant', text: `Hãy mô tả chỉ số cần tạo cho ${layer.db_name}. AI sẽ trả về Metric Definition và YAML preview để bạn review trước khi lưu.`, timestamp: now() }]);
  }, [layer.db_name, semanticDbId]);

  const send = async (prompt: string, targetTables: string[]) => {
    setMessages((current) => [...current, { id: crypto.randomUUID(), sender: 'user', text: prompt, timestamp: now() }]);
    if (!semanticDbId) return appendError(setMessages, 'Semantic Layer đang được khởi tạo. Vui lòng tải lại sau khi enrichment hoàn tất.');
    setLoading(true);
    try {
      const response = await generateCustomMetricsApi(String(semanticDbId), prompt, targetTables);
      setMessages((current) => [...current, { id: crypto.randomUUID(), sender: 'assistant', text: `Đã tạo ${response.suggestions.length} Metric Definition để review:`, suggestions: response.suggestions, timestamp: now() }]);
    } catch (error) {
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể sinh metric');
    } finally {
      setLoading(false);
    }
  };

  const save = async (suggestion: MetricSuggestion) => {
    if (!semanticDbId) throw new Error('Semantic database chưa sẵn sàng');
    await createMetricApi(String(semanticDbId), { definition: suggestion.definition, source: 'ai' });
    await onMetricsChanged();
  };

  return <div className='h-full min-h-[560px]'><StudioChatStream messages={messages} onSendMessage={send} isLoading={loading} tableNames={layer.tables.map((table) => table.table_name)} onAddMetric={save} onEditMetric={onEditMetricRequest} onRefineWithAI={(suggestion) => setActivePrompt(`Hãy điều chỉnh chỉ số ${suggestion.definition.metric.name}: `)} activePromptText={activePrompt} theme={theme} /></div>;
}

function appendError(setter: React.Dispatch<React.SetStateAction<ChatMessage[]>>, text: string): void {
  setter((current) => [...current, { id: crypto.randomUUID(), sender: 'assistant', text, timestamp: now(), isError: true }]);
}

function now(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
