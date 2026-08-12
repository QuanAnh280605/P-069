'use client';

import React, { useState, useEffect } from 'react';
import {
  generateCustomMetricsApi,
  createMetricApi,
  MetricSuggestion,
  SemanticLayerData,
} from '@/lib/api';
import { StudioChatStream, ChatMessage } from '@/components/studio/StudioChatStream';
import { CheckCircle2, Bot, Layers, Info } from 'lucide-react';

interface AIStudioViewProps {
  layer: SemanticLayerData;
  theme: 'light' | 'dark';
  onMetricAddedToLibrary: (newMetric: MetricSuggestion) => void;
  onEditMetricRequest: (metric: MetricSuggestion) => void;
}

export const AIStudioView: React.FC<AIStudioViewProps> = ({
  layer,
  theme,
  onMetricAddedToLibrary,
  onEditMetricRequest,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [activePromptText, setActivePromptText] = useState<string>('');

  const tableNames = layer?.tables?.map((t) => t.table_name) || [];

  // Initialize initial message
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          id: 'welcome_studio',
          sender: 'assistant',
          text: `Xin chào! Tôi là **AI Semantic Agent** của cơ sở dữ liệu **${layer.db_name}**.\n\nHãy mô tả chỉ số bạn muốn thiết lập (ví dụ: *Doanh thu theo từng tháng*, *Tỷ lệ khách hàng mua lại*) để tôi xây dựng **Semantic Metric Specification** vào Semantic Layer. Khi truy vấn, trình biên dịch \`SemanticQueryCompiler\` sẽ tự động mapping thành câu lệnh SQL an toàn cho bạn.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  }, [layer.db_name, messages.length]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleSendMessage = async (promptText: string) => {
    const userMsgId = `user_${Math.random().toString(36).slice(2, 9)}`;
    const newMessages: ChatMessage[] = [
      ...messages,
      {
        id: userMsgId,
        sender: 'user',
        text: promptText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ];
    setMessages(newMessages);
    setIsLoading(true);

    try {
      const result = await generateCustomMetricsApi(layer.id, promptText);
      const suggestions = result.suggestions || [];

      if (suggestions.length > 0) {
        setMessages((prev) => [
          ...prev,
          {
            id: `bot_${Math.random().toString(36).slice(2, 9)}`,
            sender: 'assistant',
            text: `Tôi đã phân tích cấu trúc cơ sở dữ liệu (${tableNames.length} bảng) và đề xuất ${suggestions.length} Semantic Metric Specification (định nghĩa thuộc tính ngữ nghĩa) vào Semantic Layer bên dưới:`,
            suggestions,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `bot_${Math.random().toString(36).slice(2, 9)}`,
            sender: 'assistant',
            text: 'Không tìm thấy hoặc không sinh được chỉ số phù hợp với yêu cầu này. Vui lòng thử diễn đạt lại yêu cầu kinh doanh cụ thể hơn.',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isError: true,
          },
        ]);
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Lỗi kết nối hoặc xử lý từ LLM Backend';
      setMessages((prev) => [
        ...prev,
        {
          id: `bot_${Math.random().toString(36).slice(2, 9)}`,
          sender: 'assistant',
          text: `Đã xảy ra lỗi khi gọi AI sinh metric: ${errMsg}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isError: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddMetricToLibrary = async (metric: MetricSuggestion) => {
    try {
      await createMetricApi(layer.id, {
        name: metric.name,
        description: metric.description,
        sql_template: metric.sql_template,
        source: 'ai',
      });

      onMetricAddedToLibrary(metric);
      showToast(`✅ Đã lưu thành công "${metric.name}" vào Semantic Layer!`);
    } catch {
      showToast('❌ Không thể lưu chỉ số vào cơ sở dữ liệu. Vui lòng thử lại.');
    }
  };

  const handleRefineWithAI = (metric: MetricSuggestion) => {
    setActivePromptText(`Hãy điều chỉnh chỉ số "${metric.name}": `);
  };

  return (
    <div className="space-y-4 animate-in fade-in h-full flex flex-col">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-60 bg-slate-900 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-xl border border-slate-700 animate-in slide-in-from-top flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Main Single-Column ChatGPT Workspace Stream */}
      <div className="flex-1 min-h-[560px] lg:h-[calc(100vh-120px)]">
        <StudioChatStream
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          tableNames={tableNames}
          dbName={layer.db_name}
          dbType={layer.db_type}
          onAddMetric={handleAddMetricToLibrary}
          onEditMetric={onEditMetricRequest}
          onRefineWithAI={handleRefineWithAI}
          activePromptText={activePromptText}
          theme={theme}
        />
      </div>
    </div>
  );
};
