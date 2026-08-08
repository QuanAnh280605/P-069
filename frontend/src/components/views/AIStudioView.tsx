'use client';

import React, { useState, useEffect } from 'react';
import {
  generateCustomMetricsApi,
  createMetricApi,
  MetricSuggestion,
  SemanticLayerData,
} from '@/lib/api';
import { StudioChatStream, ChatMessage } from '@/components/studio/StudioChatStream';
import { StudioLiveCanvas } from '@/components/studio/StudioLiveCanvas';
import { Sparkles, CheckCircle2, Bot, Layers, Info } from 'lucide-react';

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
  const [activeSuggestions, setActiveSuggestions] = useState<MetricSuggestion[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
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
          text: `Xin chào! Tôi là **AI Semantic Copilot** của cơ sở dữ liệu **${layer.db_name}**.\n\nHãy mô tả chỉ số bạn muốn tính toán (ví dụ: *Doanh thu theo từng tháng*, *Tỷ lệ khách hàng mua lại*, *Top sản phẩm bán chạy*) để tôi phân tích cấu trúc bảng và sinh công thức chuẩn cho bạn.`,
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
        setActiveSuggestions(suggestions);
        setSelectedIndex(0);

        setMessages((prev) => [
          ...prev,
          {
            id: `bot_${Math.random().toString(36).slice(2, 9)}`,
            sender: 'assistant',
            text: `Tôi đã phân tích các bảng (${tableNames.join(', ')}) và đề xuất ${suggestions.length} chỉ số kinh doanh kèm SQL template an toàn:\n\n` +
              suggestions.map((s, i) => `${i + 1}. **${s.name}**: ${s.description}`).join('\n\n') +
              `\n\nBạn có thể xem chi tiết công thức trên bảng **Live Metric Canvas** bên phải và bấm *"Lưu vào Semantic Layer"* để thêm chính thức.`,
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

  const handleSelectSuggestion = (sugg: MetricSuggestion, sIdx: number) => {
    if (!activeSuggestions.some((s) => s.name === sugg.name)) {
      setActiveSuggestions((prev) => [sugg, ...prev]);
      setSelectedIndex(0);
    } else {
      const foundIdx = activeSuggestions.findIndex((s) => s.name === sugg.name);
      setSelectedIndex(foundIdx >= 0 ? foundIdx : sIdx);
    }
  };

  const handleAddMetricToLibrary = async (metric: MetricSuggestion, sIdx: number) => {
    setIsAdding(true);
    try {
      await createMetricApi(layer.id, {
        name: metric.name,
        description: metric.description,
        sql_template: metric.sql_template,
        source: 'ai',
      });

      onMetricAddedToLibrary(metric);
      showToast(`✅ Đã lưu thành công "${metric.name}" vào Semantic Layer!`);
      setActiveSuggestions((prev) => prev.filter((_, idx) => idx !== sIdx));
      setSelectedIndex(0);
    } catch {
      showToast('❌ Không thể lưu chỉ số vào cơ sở dữ liệu. Vui lòng thử lại.');
    } finally {
      setIsAdding(false);
    }
  };

  const handleRefineWithAI = (metric: MetricSuggestion) => {
    setActivePromptText(`Hãy điều chỉnh chỉ số "${metric.name}": `);
  };

  const currentActiveMetric =
    activeSuggestions.length > 0 && selectedIndex < activeSuggestions.length
      ? activeSuggestions[selectedIndex]
      : null;

  return (
    <div className="space-y-4 animate-in fade-in">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-60 bg-slate-900 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-xl border border-slate-700 animate-in slide-in-from-top flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Banner Info */}
      <div
        className={`p-4 rounded-2xl border transition-colors flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
          theme === 'light'
            ? 'bg-white border-slate-200 shadow-2xs'
            : 'bg-slate-900/60 border-slate-800 shadow-lg'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-tight">AI Metric Studio & Interactive Copilot</h2>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30">
                Split Canvas Active
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Hội thoại đa lượt bằng tiếng Việt để tinh chỉnh và kiểm định công thức chỉ số an toàn
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1">
            <Layers className="w-3.5 h-3.5 text-indigo-500" /> Bảng: <b>{tableNames.length}</b>
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Info className="w-3.5 h-3.5 text-emerald-500" /> Dialect: <b>PostgreSQL</b>
          </span>
        </div>
      </div>

      {/* Main Split Layout: Chat on Left, Canvas on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 w-full flex-1 min-h-[620px] lg:min-h-0 lg:h-[calc(100vh-170px)] items-stretch">
        {/* Left Column: Chat Stream (5 cols) */}
        <div className="lg:col-span-5 flex flex-col h-full overflow-hidden">
          <StudioChatStream
            messages={messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            tableNames={tableNames}
            onSelectSuggestion={handleSelectSuggestion}
            activePromptText={activePromptText}
            theme={theme}
          />
        </div>

        {/* Right Column: Live Canvas & Inspector (7 cols) */}
        <div className="lg:col-span-7 flex flex-col h-full overflow-hidden">
          <StudioLiveCanvas
            metric={currentActiveMetric}
            allSuggestions={activeSuggestions}
            selectedIndex={selectedIndex}
            onSelectSuggestion={(idx) => setSelectedIndex(idx)}
            onAddMetric={handleAddMetricToLibrary}
            onEditMetric={(metric) => onEditMetricRequest(metric)}
            onRefineWithAI={handleRefineWithAI}
            isAdding={isAdding}
            theme={theme}
          />
        </div>
      </div>
    </div>
  );
};
