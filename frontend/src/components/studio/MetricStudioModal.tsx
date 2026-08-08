'use client';

import React, { useState, useEffect } from 'react';
import {
  generateCustomMetricsApi,
  createMetricApi,
  MetricSuggestion,
  SemanticLayerData,
} from '@/lib/api';
import { StudioChatStream, ChatMessage } from './StudioChatStream';
import { StudioLiveCanvas } from './StudioLiveCanvas';
import { X, Sparkles, CheckCircle2 } from 'lucide-react';

interface MetricStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  layer: SemanticLayerData;
  onMetricAddedToLibrary: (newMetric: MetricSuggestion) => void;
  onEditMetricRequest: (metric: MetricSuggestion) => void;
}

export const MetricStudioModal: React.FC<MetricStudioModalProps> = ({
  isOpen,
  onClose,
  layer,
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

  // Extract table names from current layer
  const tableNames = layer?.tables?.map((t) => t.table_name) || [];

  // Initialize initial welcome message
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        {
          id: 'welcome',
          sender: 'assistant',
          text: `Xin chào! Tôi là Trợ lý AI Sinh Chỉ Số Doanh Nghiệp (Semantic Copilot) cho cơ sở dữ liệu **${layer.db_name}**.\n\nHãy mô tả chỉ số bạn muốn tính toán (ví dụ: *Doanh thu theo tháng*, *Tỷ lệ hoàn trả*, *Top khách hàng VIP*) hoặc chọn các gợi ý bên dưới để tôi phân tích schema và sinh công thức chuẩn cho bạn.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  }, [isOpen, layer.db_name, messages.length]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleSendMessage = async (promptText: string) => {
    const userMsgId = `user_${Date.now()}`;
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
            id: `bot_${Date.now()}`,
            sender: 'assistant',
            text: `Tôi đã phân tích cấu trúc các bảng (${tableNames.join(', ')}) và đề xuất ${suggestions.length} chỉ số kinh doanh kèm SQL template an toàn:\n\n` +
              suggestions.map((s, i) => `${i + 1}. **${s.name}**: ${s.description}`).join('\n\n') +
              `\n\nBạn có thể kiểm tra chi tiết công thức trên bảng **Live Canvas** bên phải và bấm *"Lưu vào Semantic Layer"* để thêm chính thức.`,
            suggestions,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `bot_${Date.now()}`,
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
          id: `bot_${Date.now()}`,
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
    // If not in active list, add it
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

      // Filter out added metric from active list
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-60 bg-slate-900 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-xl border border-slate-700 animate-in slide-in-from-top flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Main Studio Card Container */}
      <div className="w-full max-w-6xl h-[92vh] max-h-[860px] bg-[#FAF9F6] rounded-2xl border border-slate-300 shadow-2xl flex flex-col overflow-hidden">
        {/* Studio Top Navigation Bar */}
        <div className="px-5 py-3.5 bg-white border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-indigo-600" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-bold text-slate-900 tracking-tight">
                  AI SEMANTIC METRIC STUDIO
                </h1>
                <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700">
                  {layer.db_name}
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live Copilot
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Mô tả yêu cầu bằng ngôn ngữ tự nhiên để AI phân tích cấu trúc bảng và sinh công thức chỉ số
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-all cursor-pointer"
              title="Đóng Studio (ESC)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Studio Split Layout (Chat Stream + Live Canvas) */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 p-4 overflow-hidden bg-[#FAF9F6]">
          {/* Left Column: Chat Stream (5 cols) */}
          <div className="lg:col-span-5 h-full overflow-hidden flex flex-col">
            <StudioChatStream
              messages={messages}
              onSendMessage={handleSendMessage}
              isLoading={isLoading}
              tableNames={tableNames}
              onSelectSuggestion={handleSelectSuggestion}
              activePromptText={activePromptText}
            />
          </div>

          {/* Right Column: Live Metric Canvas & Inspector (7 cols) */}
          <div className="lg:col-span-7 h-full overflow-hidden flex flex-col">
            <StudioLiveCanvas
              metric={currentActiveMetric}
              allSuggestions={activeSuggestions}
              selectedIndex={selectedIndex}
              onSelectSuggestion={(idx) => setSelectedIndex(idx)}
              onAddMetric={handleAddMetricToLibrary}
              onEditMetric={(metric) => onEditMetricRequest(metric)}
              onRefineWithAI={handleRefineWithAI}
              isAdding={isAdding}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
