'use client';

import React, { useState, useRef, useEffect } from 'react';
import { MetricSuggestion } from '@/lib/api';
import { SqlCodeViewer } from './SqlCodeViewer';
import {
  Send,
  Sparkles,
  Bot,
  User,
  AlertCircle,
  Database,
  RefreshCw,
  Lightbulb,
  ShieldCheck,
  PlusCircle,
  Edit3,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Code,
  Layers,
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
  dbName?: string;
  dbType?: string;
  onSelectSuggestion?: (sugg: MetricSuggestion, sIdx: number) => void;
  onAddMetric?: (sugg: MetricSuggestion, sIdx: number) => void;
  onEditMetric?: (sugg: MetricSuggestion) => void;
  onRefineWithAI?: (sugg: MetricSuggestion) => void;
  activePromptText?: string;
  theme?: 'light' | 'dark';
}

export const StudioChatStream: React.FC<StudioChatStreamProps> = ({
  messages,
  onSendMessage,
  isLoading,
  tableNames,
  dbName,
  dbType,
  onAddMetric,
  onEditMetric,
  onRefineWithAI,
  activePromptText = '',
  theme = 'light',
}) => {
  const isDark = theme === 'dark';
  const [inputVal, setInputVal] = useState(activePromptText);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [savedMetricNames, setSavedMetricNames] = useState<string[]>([]);
  const [expandedSqlKeys, setExpandedSqlKeys] = useState<Record<string, boolean>>({});
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

  const handleSaveMetricClick = (sugg: MetricSuggestion, sIdx: number) => {
    if (onAddMetric) {
      onAddMetric(sugg, sIdx);
      setSavedMetricNames((prev) => [...prev, sugg.name]);
    }
  };

  const sampleSuggestions = [
    'Tổng doanh thu theo từng tháng',
    'Tỷ lệ khách hàng mua lại sau 30 ngày',
    'Top 5 sản phẩm có doanh số cao nhất',
    'Giá trị đơn hàng trung bình (AOV)',
  ];

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col h-full overflow-hidden">


      {/* Chat Messages Feed */}
      <div className="flex-1 overflow-y-auto px-1 py-2 space-y-4">
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
                  <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">Bạn</span>
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center ${
                      isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    <User className="w-3 h-3" />
                  </div>
                </>
              ) : (
                <>
                  <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-500 dark:text-indigo-400 flex items-center justify-center">
                    <Sparkles className="w-3 h-3" />
                  </div>
                  <span className={`text-[11px] font-semibold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                    AI Agent
                  </span>
                </>
              )}
              <span className="text-[10px] text-slate-400 dark:text-slate-500">{msg.timestamp}</span>
            </div>

            {/* Bubble Content */}
            <div
              className={`w-full max-w-3xl p-4 rounded-2xl text-xs leading-relaxed shadow-xs ${
                msg.sender === 'user'
                  ? 'bg-indigo-600 text-white rounded-tr-xs ml-auto max-w-xl'
                  : msg.isError
                  ? isDark
                    ? 'bg-red-950/50 text-red-200 border border-red-800 rounded-tl-xs'
                    : 'bg-red-50 text-red-700 border border-red-200 rounded-tl-xs'
                  : isDark
                  ? 'bg-[#0E1526] text-slate-100 border border-slate-800 rounded-tl-xs'
                  : 'bg-white text-slate-900 border border-slate-200 rounded-tl-xs'
              }`}
            >
              {msg.isError && (
                <div className="flex items-center gap-1.5 font-bold mb-1 text-red-500 dark:text-red-400">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Có lỗi xảy ra</span>
                </div>
              )}
              <p className="whitespace-pre-wrap">{msg.text}</p>

              {/* Embedded Metric Cards inside Assistant Messages */}
              {msg.suggestions && msg.suggestions.length > 0 && (
                <div className="mt-4 space-y-4">
                  {msg.suggestions.map((sugg, sIdx) => {
                    const isSaved = savedMetricNames.includes(sugg.name);
                    return (
                      <div
                        key={sIdx}
                        className={`p-4 rounded-xl border space-y-3 transition-colors ${
                          isDark
                            ? 'bg-[#141C2E] border-slate-750'
                            : 'bg-slate-50/90 border-slate-200'
                        }`}
                      >
                        {/* Header & Badges */}
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                              isDark
                                ? 'bg-indigo-950/80 text-indigo-300 border-indigo-800'
                                : 'bg-indigo-100/80 text-indigo-800 border-indigo-200'
                            }`}
                          >
                            <Layers className="w-3 h-3 text-indigo-500" /> Semantic Metric Spec #{sIdx + 1}
                          </span>

                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${
                              isDark
                                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800'
                                : 'bg-emerald-50 text-emerald-800 border-emerald-200'
                            }`}
                          >
                            <ShieldCheck className="w-3 h-3 text-emerald-600 dark:text-emerald-500" /> Semantic Spec Ready
                          </span>
                        </div>

                        {/* Title & Description */}
                        <div>
                          <h4 className={`text-sm font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                            {sugg.name}
                          </h4>
                          <p className={`text-xs mt-0.5 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                            {sugg.description}
                          </p>
                        </div>

                        {/* Semantic Layer Specification Grid */}
                        <div className={`p-3 rounded-xl border grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] ${
                          isDark ? 'bg-slate-900/80 border-slate-800' : 'bg-white border-slate-200 shadow-2xs'
                        }`}>
                          <div>
                            <span className="text-slate-500 dark:text-slate-400 block font-medium">Bảng Target</span>
                            <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
                              {sugg.target_table || (tableNames[0] || 'orders')}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 dark:text-slate-400 block font-medium">Phép Gom Nhóm</span>
                            <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 uppercase">
                              {sugg.measure_type || 'SUM'}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 dark:text-slate-400 block font-medium">Cột Tính Toán</span>
                            <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                              {sugg.target_column || 'total_amount'}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 dark:text-slate-400 block font-medium">Điều Kiện Lọc</span>
                            <span className="font-mono text-slate-600 dark:text-slate-400 truncate block" title={sugg.filter_condition || 'Nghiệp vụ chuẩn'}>
                              {sugg.filter_condition || 'Nghiệp vụ chuẩn'}
                            </span>
                          </div>
                        </div>

                        {/* Collapsible Compiled SQL Preview */}
                        {(() => {
                          const cardKey = `${msg.id}_${sIdx}`;
                          const isExpanded = !!expandedSqlKeys[cardKey];
                          return (
                            <div>
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedSqlKeys((prev) => ({
                                    ...prev,
                                    [cardKey]: !prev[cardKey],
                                  }))
                                }
                                className={`w-full py-1.5 px-3 text-[11px] font-medium rounded-lg border flex items-center justify-between transition-colors cursor-pointer ${
                                  isDark
                                    ? 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                                    : 'bg-slate-100 border-slate-200 text-slate-600 hover:text-slate-900'
                                }`}
                              >
                                <span className="flex items-center gap-1.5">
                                  <Code className="w-3.5 h-3.5 text-indigo-500" />
                                  <span>Xem SQL Compiled Mẫu (SemanticQueryCompiler Preview)</span>
                                </span>
                                {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                              </button>

                              {isExpanded && (
                                <div className="mt-2 animate-in fade-in">
                                  <SqlCodeViewer sql={sugg.sql_template} title="SQL Compiled bởi SemanticQueryCompiler" theme={theme} />
                                </div>
                              )}
                            </div>
                          );
                        })()}

                        {/* Inline Actions */}
                        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                          <div className="flex items-center gap-2">
                            {onRefineWithAI && (
                              <button
                                type="button"
                                onClick={() => onRefineWithAI(sugg)}
                                className={`px-2.5 py-1.5 text-[11px] font-medium rounded-lg border transition-all cursor-pointer inline-flex items-center gap-1 ${
                                  isDark
                                    ? 'bg-slate-900 text-slate-300 hover:text-white border-slate-700'
                                    : 'bg-white text-slate-700 hover:text-slate-900 border-slate-200 shadow-2xs'
                                }`}
                              >
                                <Sparkles className="w-3 h-3 text-indigo-500" /> Nhờ AI tinh chỉnh
                              </button>
                            )}

                            {onEditMetric && (
                              <button
                                type="button"
                                onClick={() => onEditMetric(sugg)}
                                className={`px-2.5 py-1.5 text-[11px] font-medium rounded-lg border transition-all cursor-pointer inline-flex items-center gap-1 ${
                                  isDark
                                    ? 'bg-slate-900 text-slate-300 hover:text-white border-slate-700'
                                    : 'bg-white text-slate-700 hover:text-slate-900 border-slate-200 shadow-2xs'
                                }`}
                              >
                                <Edit3 className="w-3 h-3 text-slate-400" /> Chỉnh sửa
                              </button>
                            )}
                          </div>

                          <button
                            type="button"
                            onClick={() => handleSaveMetricClick(sugg, sIdx)}
                            disabled={isSaved}
                            className={`px-3.5 py-1.5 text-xs font-bold rounded-xl transition-all cursor-pointer inline-flex items-center gap-1.5 shadow-xs ${
                              isSaved
                                ? 'bg-emerald-600 text-white cursor-default'
                                : 'gradient-btn text-white'
                            }`}
                          >
                            {isSaved ? (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>Đã lưu vào Semantic Layer</span>
                              </>
                            ) : (
                              <>
                                <PlusCircle className="w-3.5 h-3.5" />
                                <span>Lưu vào Semantic Layer</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex flex-col items-start animate-in fade-in">
            <div className="flex items-center gap-1.5 mb-1 px-1">
              <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-500 dark:text-indigo-400 flex items-center justify-center">
                <Sparkles className="w-3 h-3 animate-spin" />
              </div>
              <span className={`text-[11px] font-semibold ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                AI Agent
              </span>
            </div>
            <div
              className={`p-3.5 rounded-2xl border text-xs flex items-center gap-2.5 shadow-xs ${
                isDark
                  ? 'bg-[#0E1526] border-slate-800 text-slate-300'
                  : 'bg-white border-slate-200 text-slate-700'
              }`}
            >
              <RefreshCw className="w-3.5 h-3.5 text-indigo-500 animate-spin" />
              <span>Đang phân tích schema metadata và sinh công thức chỉ số an toàn...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion Quick Pills */}
      <div
        className={`px-3 pt-2 pb-1 border-t rounded-t-2xl transition-colors ${
          isDark ? 'bg-[#0E1526] border-slate-800' : 'bg-white border-slate-200'
        }`}
      >
        <div className="flex items-center gap-1 text-[11px] text-slate-600 dark:text-slate-400 mb-1.5 font-semibold">
          <Lightbulb className="w-3 h-3 text-amber-500" />
          <span>Gợi ý câu hỏi nhanh:</span>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {sampleSuggestions.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setInputVal(item)}
              className={`text-[11px] border px-2.5 py-1 rounded-lg transition-all cursor-pointer whitespace-nowrap shrink-0 font-medium ${
                isDark
                  ? 'bg-slate-900 hover:bg-indigo-950 text-slate-300 hover:text-indigo-300 border-slate-800'
                  : 'bg-slate-100 hover:bg-indigo-50 text-slate-800 hover:text-indigo-700 border-slate-200 shadow-2xs'
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form Bar */}
      <form
        onSubmit={handleSend}
        className={`p-3 border-t rounded-b-2xl transition-colors ${
          isDark ? 'bg-[#0E1526] border-slate-800' : 'bg-white border-slate-200'
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
            placeholder="Mô tả chỉ số bạn muốn tính toán bằng tiếng Việt (ví dụ: Tính doanh thu theo từng tháng)..."
            rows={2}
            maxLength={2000}
            className={`w-full p-3 pr-12 text-xs focus:outline-none resize-none bg-transparent ${
              isDark ? 'text-slate-100 placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'
            }`}
          />

          <button
            type="submit"
            disabled={isLoading || !inputVal.trim()}
            className="absolute right-2.5 bottom-2.5 p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-30 disabled:cursor-not-allowed text-white transition-all cursor-pointer shadow-md"
            title="Gửi yêu cầu (Enter)"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex items-center justify-between mt-1 px-1 text-[10px] text-slate-500 dark:text-slate-400">
          <span>Bấm <b>Enter</b> để gửi câu hỏi cho Trợ lý AI</span>
          <span>{inputVal.length}/2000</span>
        </div>
      </form>
    </div>
  );
};
