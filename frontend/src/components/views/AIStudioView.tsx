'use client';

import { useEffect, useState } from 'react';

import {
  createMetricApi,
  generateCustomMetricsApi,
  MetricSuggestion,
  SemanticLayerData,
  sendChatOrchestratorApi,
} from '@/lib/api';
import { ChatMessage, StudioChatStream } from '@/components/studio/StudioChatStream';
import { ViewHeader } from '@/components/workspace/ViewHeader';

interface AIStudioViewProps {
  layer: SemanticLayerData;
  theme: 'light' | 'dark';
  onMetricsChanged: () => Promise<void> | void;
  onEditMetricRequest: (metric: MetricSuggestion) => void;
  onOpenCatalog?: () => void;
}

export function AIStudioView({
  layer,
  theme,
  onMetricsChanged,
  onEditMetricRequest,
  onOpenCatalog,
}: AIStudioViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [activePrompt, setActivePrompt] = useState('');
  const semanticDbId = layer.semantic_db_id;

  useEffect(() => {
    setMessages([
      {
        id: 'welcome',
        sender: 'assistant',
        text: `Xin chào! Tôi đã quét schema cho database ${layer.db_name} (${layer.tables.length} bảng). Bạn có thể hỏi bất kỳ câu hỏi nào để tôi tự động đề xuất và định nghĩa các chỉ số kinh doanh (Business Metrics).`,
        timestamp: now(),
      },
    ]);
  }, [layer.db_name, layer.tables.length, semanticDbId]);

  const send = async (prompt: string, _targetTables: string[]) => {
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), sender: 'user', text: prompt, timestamp: now() },
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
      try {
        const response = await sendChatOrchestratorApi(String(semanticDbId), prompt);
        if (response.intent === 'chitchat') {
          setMessages((current) => [
            ...current,
            {
              id: crypto.randomUUID(),
              sender: 'assistant',
              text: response.chat_response || 'Xin chào! Tôi có thể giúp gì cho bạn?',
              timestamp: now(),
            },
          ]);
          return;
        }
        suggestions = response.suggestions || [];
      } catch {
        const res = await generateCustomMetricsApi(String(semanticDbId), prompt, _targetTables);
        suggestions = res.suggestions || [];
      }
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          sender: 'assistant',
          text: suggestions.length
            ? `Dựa trên schema của bạn, tôi đề xuất ${suggestions.length} Metric Definition dưới đây. Bạn có thể xem trước YAML và lưu vào catalog để duyệt:`
            : 'Không sinh được metric phù hợp từ schema.',
          suggestions,
          timestamp: now(),
        },
      ]);
    } catch (error) {
      appendError(setMessages, error instanceof Error ? error.message : 'Không thể xử lý yêu cầu');
    } finally {
      setLoading(false);
    }
  };

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
      appendError(
        setMessages,
        `Không thể lưu chỉ số "${suggestion.definition.metric.name}": ${
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
        eyebrow="Generate"
        title="AI Studio"
        description="Chat with the assistant to explore your schema and auto-generate business metric definitions."
        database={dbProp}
      />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
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
          onOpenCatalog={onOpenCatalog}
        />
      </div>
    </div>
  );
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
