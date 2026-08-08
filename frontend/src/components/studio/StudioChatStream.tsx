'use client';

import React, { useState, useRef, useEffect } from 'react';
import { MetricSuggestion } from '@/lib/api';
import {
  Send,
  Sparkles,
  Bot,
  User,
  AlertCircle,
  Database,
  ArrowUpRight,
  RefreshCw,
  Lightbulb,
} from 'lucide-react';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  suggestions?: MetricSuggestion[];
  timestamp: string;
  isError?: boolean;
}

interface StudioChatStreamProps {
  messages: ChatMessage[];
  onSendMessage: (promptText: string) => Promise<void>;
  isLoading: boolean;
  tableNames: string[];
  onSelectSuggestion: (sugg: MetricSuggestion, sIdx: number) => void;
  activePromptText?: string;
  theme?: 'light' | 'dark';
}

export const StudioChatStream: React.FC<StudioChatStreamProps> = ({
  messages,
  onSendMessage,
  isLoading,
  tableNames,
  onSelectSuggestion,
  activePromptText = '',
  theme = 'light',
}) => {
  const isDark = theme === 'dark';
  const [inputVal, setInputVal] = useState(activePromptText);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (activePromptText) {
      setInputVal(activePromptText);
      textareaRef.current?.focus();
    }
  }, [activePromptText]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputVal.trim();
    if (!trimmed || isLoading) return;

    let finalPrompt = trimmed;
    if (selectedTables.length > 0) {
      const tags = selectedTables.map((t) => `@${t}`).join(' ');
      if (!trimmed.includes('@')) {
        finalPrompt = `[Context: ${tags}] ${trimmed}`;
      }
    }

    setInputVal('');
    await onSendMessage(finalPrompt);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleTableTag = (tbl: string) => {
    setSelectedTables((prev) =>
      prev.includes(tbl) ? prev.filter((t) => t !== tbl) : [...prev, tbl]
    );
  };

  const sampleSuggestions = [
    'Tổng doanh thu theo từng tháng',
    'Tỷ lệ khách hàng mua lại sau 30 ngày',
    'Top 5 sản phẩm có doanh số cao nhất',
    'Giá trị đơn hàng trung bình (AOV)',
  ];

  return (
    <div
      className={`h-full flex flex-col rounded-2xl border overflow-hidden transition-colors ${
        isDark
          ? 'bg-[#0E1526] border-slate-800 text-slate-200 shadow-md'
          : 'bg-[#FAF9F6] border-slate-200 text-slate-800 shadow-xs'
      }`}
    >
      {/* Top Scope & Context Bar */}
      <div
        className={`p-3 border-b space-y-2 transition-colors ${
          isDark ? 'bg-[#131B2E] border-slate-800' : 'bg-white border-slate-200/80'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-bold">
            <Bot className="w-4 h-4 text-indigo-500" />
            <span className={isDark ? 'text-white' : 'text-slate-800'}>AI Metric Copilot</span>
          </div>
          <span
            className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
              isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-500'
            }`}
          >
            Vietnamese Natural Language
          </span>
        </div>

        {/* Database Table Scope Tag Filters */}
        {tableNames.length > 0 && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
            <span className="text-[11px] font-medium text-slate-400 shrink-0 flex items-center gap-1">
              <Database className="w-3 h-3 text-slate-400" /> Bảng:
            </span>
            {tableNames.map((tbl) => {
              const isSelected = selectedTables.includes(tbl);
              return (
                <button
                  key={tbl}
                  type="button"
                  onClick={() => toggleTableTag(tbl)}
                  className={`text-[11px] font-mono px-2 py-0.5 rounded-md transition-all cursor-pointer shrink-0 border ${
                    isSelected
                      ? isDark
                        ? 'bg-indigo-950/80 border-indigo-500 text-indigo-300 font-semibold'
                        : 'bg-indigo-50 border-indigo-300 text-indigo-700 font-semibold'
                      : isDark
                      ? 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  @{tbl}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Message History Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.sender === 'user' ? 'items-end' : 'items-start'
            } animate-in fade-in duration-200`}
          >
            <div className="flex items-center gap-1.5 mb-1 px-1">
              {msg.sender === 'user' ? (
                <>
                  <span className="text-[11px] font-semibold text-slate-400">Bạn</span>
                  <div
                    className={`w-4 h-4 rounded-full flex items-center justify-center ${
                      isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    <User className="w-2.5 h-2.5" />
                  </div>
                </>
              ) : (
                <>
                  <div className="w-4 h-4 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                    <Sparkles className="w-2.5 h-2.5" />
                  </div>
                  <span className={`text-[11px] font-semibold ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                    Trợ lý AI
                  </span>
                </>
              )}
              <span className="text-[10px] text-slate-500">{msg.timestamp}</span>
            </div>

            {/* Bubble Content */}
            <div
              className={`max-w-[92%] p-3.5 rounded-2xl text-xs leading-relaxed shadow-xs ${
                msg.sender === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-xs'
                  : msg.isError
                  ? isDark
                    ? 'bg-red-950/50 text-red-200 border border-red-800 rounded-bl-xs'
                    : 'bg-red-50 text-red-700 border border-red-200 rounded-bl-xs'
                  : isDark
                  ? 'bg-[#162036] text-slate-100 border border-slate-750 rounded-bl-xs'
                  : 'bg-white text-slate-800 border border-slate-200/90 rounded-bl-xs'
              }`}
            >
              {msg.isError && (
                <div className="flex items-center gap-1.5 font-bold mb-1 text-red-400">
                  <AlertCircle className="w-3.5 h-3.5 text-red-400" />
                  <span>Có lỗi xảy ra</span>
                </div>
              )}
              <p className="whitespace-pre-wrap">{msg.text}</p>

              {/* Suggestions Cards embedded in Assistant Message */}
              {msg.suggestions && msg.suggestions.length > 0 && (
                <div
                  className={`mt-3 pt-2.5 border-t space-y-2 ${
                    isDark ? 'border-slate-700/60' : 'border-slate-100'
                  }`}
                >
                  <div
                    className={`text-[11px] font-bold flex items-center gap-1 ${
                      isDark ? 'text-indigo-300' : 'text-slate-600'
                    }`}
                  >
                    <Sparkles className="w-3 h-3 text-indigo-400" />
                    <span>Đã tạo {msg.suggestions.length} chỉ số đề xuất:</span>
                  </div>
                  <div className="space-y-1.5">
                    {msg.suggestions.map((sugg, sIdx) => (
                      <div
                        key={sIdx}
                        onClick={() => onSelectSuggestion(sugg, sIdx)}
                        className={`p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-2 group ${
                          isDark
                            ? 'bg-[#101827] hover:bg-indigo-950/60 border-slate-800 hover:border-indigo-500/60'
                            : 'bg-slate-50 hover:bg-indigo-50/60 border-slate-200 hover:border-indigo-300'
                        }`}
                      >
                        <div className="min-w-0">
                          <div
                            className={`font-semibold truncate ${
                              isDark
                                ? 'text-slate-100 group-hover:text-indigo-300'
                                : 'text-slate-800 group-hover:text-indigo-700'
                            }`}
                          >
                            {sugg.name}
                          </div>
                          <div className="text-[10px] text-slate-400 truncate mt-0.5">
                            {sugg.description}
                          </div>
                        </div>
                        <ArrowUpRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-400 shrink-0" />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading Bubble */}
        {isLoading && (
          <div className="flex flex-col items-start animate-in fade-in">
            <div className="flex items-center gap-1.5 mb-1 px-1">
              <div className="w-4 h-4 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                <Sparkles className="w-2.5 h-2.5 animate-spin" />
              </div>
              <span className={`text-[11px] font-semibold ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                Trợ lý AI
              </span>
            </div>
            <div
              className={`p-3.5 rounded-2xl border text-xs flex items-center gap-2.5 shadow-xs ${
                isDark
                  ? 'bg-[#162036] border-slate-800 text-slate-300'
                  : 'bg-white border-slate-200/90 text-slate-600'
              }`}
            >
              <RefreshCw className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
              <span>Đang đọc schema và sinh công thức chỉ số an toàn...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion Pills */}
      <div
        className={`px-3 pt-2 pb-1 border-t transition-colors ${
          isDark ? 'bg-[#131B2E] border-slate-800' : 'bg-white border-slate-200'
        }`}
      >
        <div className="flex items-center gap-1 text-[11px] text-slate-400 mb-1.5">
          <Lightbulb className="w-3 h-3 text-amber-400" />
          <span>Gợi ý câu hỏi nhanh:</span>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {sampleSuggestions.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setInputVal(item)}
              className={`text-[11px] border px-2.5 py-1 rounded-lg transition-all cursor-pointer whitespace-nowrap shrink-0 ${
                isDark
                  ? 'bg-slate-900/90 hover:bg-indigo-950/80 text-slate-300 hover:text-indigo-300 border-slate-750'
                  : 'bg-slate-100 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border-slate-200/80'
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Input Bar */}
      <form
        onSubmit={handleSend}
        className={`p-3 border-t transition-colors ${
          isDark ? 'bg-[#131B2E] border-slate-800' : 'bg-white border-slate-200/80'
        }`}
      >
        <div
          className={`relative rounded-xl border focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all ${
            isDark
              ? 'bg-slate-950 border-slate-700 focus-within:border-indigo-500'
              : 'bg-white border-slate-300 focus-within:border-indigo-500'
          }`}
        >
          <textarea
            ref={textareaRef}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ví dụ: Tính tỷ lệ đơn hàng hoàn thành trong 30 ngày qua..."
            rows={2}
            maxLength={2000}
            className={`w-full p-2.5 pr-10 text-xs focus:outline-none resize-none bg-transparent ${
              isDark ? 'text-slate-100 placeholder-slate-500' : 'text-slate-800 placeholder-slate-400'
            }`}
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={isLoading || !inputVal.trim()}
            className="absolute right-2 bottom-2 p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-30 disabled:cursor-not-allowed text-white transition-all cursor-pointer shadow-xs"
            title="Gửi câu hỏi (Enter)"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex items-center justify-between mt-1.5 px-1 text-[10px] text-slate-400">
          <span>Nhấn <b>Enter</b> để gửi, <b>Shift + Enter</b> để xuống dòng</span>
          <span>{inputVal.length}/2000</span>
        </div>
      </form>
    </div>
  );
};
