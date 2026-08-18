'use client';

import {
  AlertCircle,
  ArrowUpRight,
  Bot,
  Calculator,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Columns3,
  Database,
  Edit3,
  Filter,
  HelpCircle,
  Info,
  Lightbulb,
  MessageSquare,
  PlusCircle,
  Send,
  Sparkles,
  Table2,
  User,
  Wand2,
} from 'lucide-react';
import React, { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';

import { ChatSessionItem, MetricSuggestion } from '@/lib/api';
import { ChatSessionSwitcher } from '@/components/studio/ChatSessionSwitcher';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  suggestions?: MetricSuggestion[];
  timestamp: string;
  isError?: boolean;
}

export interface StudioChatStreamProps {
  messages: ChatMessage[];
  onSendMessage: (promptText: string, targetTables: string[]) => Promise<void>;
  isLoading: boolean;
  tableNames: string[];
  onAddMetric?: (suggestion: MetricSuggestion) => Promise<void> | void;
  onEditMetric?: (suggestion: MetricSuggestion) => void;
  onRefineWithAI?: (suggestion: MetricSuggestion) => void;
  activePromptText?: string;
  theme?: 'light' | 'dark';
  sessions?: ChatSessionItem[];
  activeSessionId?: string | null;
  loadingSessions?: boolean;
  onSelectSession?: (sessionId: string) => void;
  onNewChat?: () => void;
  onDeleteSession?: (sessionId: string) => void;
  onRenameSession?: (sessionId: string, newTitle: string) => Promise<void> | void;
}

interface PromptSuggestionItem {
  icon: string;
  title: string;
  prompt: string;
}

const DEFAULT_SUGGESTIONS: PromptSuggestionItem[] = [
  {
    icon: '💰',
    title: 'Doanh thu thuần đơn hàng thành công',
    prompt: 'Tính tổng doanh thu thuần của các đơn hàng có trạng thái thành công (status = "completed" hoặc "delivered")',
  },
  {
    icon: '👥',
    title: 'Số lượng khách hàng mới tháng 1/2025',
    prompt: 'Đếm số lượng khách hàng mới đăng ký trong tháng 1 năm 2025 (created_time từ 2025-01-01 đến 2025-01-31)',
  },
  {
    icon: '📊',
    title: 'Giá trị đơn hàng trung bình (AOV)',
    prompt: 'Tính giá trị trung bình mỗi đơn hàng thành công (Average Order Value - AOV)',
  },
  {
    icon: '📦',
    title: 'Số lượng sản phẩm bán ra',
    prompt: 'Tính tổng số lượng sản phẩm bán ra từ bảng chi tiết đơn hàng (order_items)',
  },
  {
    icon: '🎯',
    title: 'Tỷ lệ đơn hàng hoàn trả / hủy',
    prompt: 'Tính tỷ lệ phần trăm đơn hàng bị hủy hoặc hoàn trả so với tổng số đơn',
  },
  {
    icon: '🏷️',
    title: 'Doanh thu trước thuế tháng 12',
    prompt: 'Tính tổng doanh thu trước thuế của các đơn hàng phát sinh trong tháng 12',
  },
];

export function StudioChatStream(props: StudioChatStreamProps) {
  const [input, setInput] = useState(props.activePromptText || '');
  const [saved, setSaved] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const savedPref = localStorage.getItem('studio_show_prompt_suggestions');
      return savedPref !== null ? savedPref === 'true' : true;
    }
    return true;
  });
  const endRef = useRef<HTMLDivElement>(null);

  const toggleShowSuggestions = () => {
    setShowSuggestions((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('studio_show_prompt_suggestions', String(next));
      } catch {}
      return next;
    });
  };

  useEffect(() => {
    if (props.activePromptText) {
      setInput(props.activePromptText);
    }
  }, [props.activePromptText]);

  useEffect(() => {
    if (typeof endRef.current?.scrollIntoView === 'function') {
      endRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [props.messages, props.isLoading]);

  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!input.trim() || props.isLoading) return;
    const prompt = input.trim();
    setInput('');
    // Automatically search across all semantic schema tables
    await props.onSendMessage(prompt, []);
  };

  const handleSelectSuggestion = (promptText: string) => {
    setInput(promptText);
  };

  const save = async (suggestion: MetricSuggestion) => {
    try {
      await props.onAddMetric?.(suggestion);
      setSaved((current) => [...current, suggestion.definition.metric.name]);
    } catch {
      // Error is surfaced and handled in onAddMetric callback
    }
  };

  // Generate dynamic contextual suggestions based on schema table names
  const contextualSuggestions = useMemo(() => {
    const list: PromptSuggestionItem[] = [...DEFAULT_SUGGESTIONS];
    const lowerTables = props.tableNames.map((t) => t.toLowerCase());

    if (lowerTables.some((t) => t.includes('customer') || t.includes('khach_hang') || t.includes('user'))) {
      list.push({
        icon: '🌟',
        title: 'Khách hàng VIP mua trên 5 đơn',
        prompt: 'Đếm số lượng khách hàng thân thiết có từ 5 đơn hàng thành công trở lên',
      });
    }
    if (lowerTables.some((t) => t.includes('product') || t.includes('san_pham') || t.includes('item'))) {
      list.push({
        icon: '🏷️',
        title: 'Top sản phẩm bán chạy',
        prompt: 'Tính tổng doanh số và số lượng bán theo từng danh mục sản phẩm',
      });
    }
    return list;
  }, [props.tableNames]);

  const hasUserSentMessage = useMemo(
    () => props.messages.some((m) => m.sender === 'user'),
    [props.messages]
  );

  return (
    <div className="flex h-full w-full flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs dark:border-slate-800 dark:bg-slate-900">
      {/* 🌟 Chat Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/80 bg-slate-50/70 px-6 py-3.5 dark:border-slate-800 dark:bg-slate-900/90">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white shadow-sm shadow-indigo-500/20 shrink-0">
            <Sparkles className="h-4.5 w-4.5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 flex-wrap">
              AI Semantic Studio Copilot
              <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                ● Live Schema Ready
              </span>
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Mô tả chỉ số bằng ngôn ngữ tự nhiên để AI tự động trích xuất Metric Definition & YAML
            </p>
          </div>
        </div>

        {/* 💬 Header Chat Session Switcher & New Chat */}
        {props.sessions && props.onSelectSession && props.onNewChat && (
          <ChatSessionSwitcher
            sessions={props.sessions}
            activeSessionId={props.activeSessionId ?? null}
            loadingSessions={Boolean(props.loadingSessions)}
            onSelectSession={props.onSelectSession}
            onNewChat={props.onNewChat}
            onDeleteSession={props.onDeleteSession || (() => {})}
            onRenameSession={props.onRenameSession || (() => {})}
          />
        )}
      </div>

      {/* 💬 Messages Stream */}
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
        {props.messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            saved={saved}
            onSave={save}
            onEdit={props.onEditMetric}
            onRefine={props.onRefineWithAI}
          />
        ))}

        {props.isLoading && (
          <div className="flex items-center gap-3 rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4 text-xs text-indigo-700 dark:border-indigo-900/40 dark:bg-indigo-950/30 dark:text-indigo-300 max-w-5xl">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white animate-spin">
              <Sparkles className="h-3.5 w-3.5" />
            </div>
            <div>
              <p className="font-semibold">AI đang phân tích cấu trúc Schema & quan hệ quan trọng...</p>
              <p className="text-[11px] text-indigo-500 dark:text-indigo-400">
                Đang chuẩn bị công thức tính toán, bộ lọc điều kiện và bản xem trước YAML chuẩn xác.
              </p>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* ✍️ Bottom Input Area */}
      <div className="space-y-2 border-t border-slate-200/80 bg-slate-50/50 p-4 md:p-5 dark:border-slate-800 dark:bg-slate-900/60">
        {/* 🌟 1 Single Horizontal Row of Suggestion Pills (Ngay bên trên phần nhập chat, chỉ hiển thị trước khi gửi query đầu tiên) */}
        {!hasUserSentMessage && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs select-none">
            <span className="shrink-0 text-[11px] font-semibold text-slate-400 dark:text-slate-500 flex items-center gap-1">
              <Sparkles className="h-3 w-3 text-indigo-500" />
              <span>Gợi ý:</span>
            </span>
            {contextualSuggestions.map((item, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelectSuggestion(item.prompt)}
                className="group shrink-0 inline-flex items-center gap-1.5 rounded-full border border-slate-200/90 bg-white/90 px-3 py-1 text-xs font-medium text-slate-700 shadow-2xs hover:border-indigo-400 hover:bg-indigo-50/80 hover:text-indigo-900 transition-all active:scale-95 dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-300 dark:hover:border-indigo-600 dark:hover:bg-indigo-950/60 dark:hover:text-indigo-200 cursor-pointer whitespace-nowrap"
                title={item.prompt}
              >
                <span>{item.icon}</span>
                <span>{item.title}</span>
                <ArrowUpRight className="h-3 w-3 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors opacity-60 group-hover:opacity-100" />
              </button>
            ))}
          </div>
        )}

        {/* ✍️ Form Input Box */}
        <form
          onSubmit={send}
          className="flex items-end gap-2.5 rounded-2xl border border-slate-300 bg-white p-2.5 shadow-xs transition-all focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-950 dark:focus-within:border-indigo-500"
        >
          <textarea
            rows={2}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void send();
              }
            }}
            placeholder="Mô tả chỉ số bạn muốn tạo (ví dụ: Tính tổng doanh thu thuần theo đơn hàng thành công, Số lượng khách hàng mới)..."
            className="flex-1 resize-none bg-transparent px-3 py-1.5 text-xs sm:text-sm outline-none placeholder:text-slate-400 dark:placeholder:text-slate-500"
          />
          <button
            type="submit"
            disabled={!input.trim() || props.isLoading}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-500/20 transition-all hover:from-indigo-500 hover:to-indigo-600 active:scale-95 disabled:opacity-40 cursor-pointer"
            title="Gửi yêu cầu (Enter)"
          >
            <span>Gửi</span>
            <Send className="h-3.5 w-3.5" />
          </button>
        </form>

        <div className="flex items-center justify-between px-1 text-[11px] text-slate-400">
          <span className="flex items-center gap-1">
            <Wand2 className="h-3 w-3 text-indigo-500" />
            AI tự động dò quét toàn bộ bảng và quan hệ Foreign Key
          </span>
          <span>
            Nhấn <kbd className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[10px] dark:bg-slate-800">Enter</kbd> để gửi, <kbd className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[10px] dark:bg-slate-800">Shift + Enter</kbd> xuống dòng
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 🗨️ Message Bubble
// ---------------------------------------------------------------------------

function MessageBubble({
  message,
  saved,
  onSave,
  onEdit,
  onRefine,
}: {
  message: ChatMessage;
  saved: string[];
  onSave: (item: MetricSuggestion) => Promise<void>;
  onEdit?: (item: MetricSuggestion) => void;
  onRefine?: (item: MetricSuggestion) => void;
}) {
  const user = message.sender === 'user';
  return (
    <div className={`flex flex-col ${user ? 'items-end' : 'items-start'}`}>
      <div className="mb-1 flex items-center gap-1.5 px-1 text-[11px] text-slate-500">
        {user ? (
          <>
            <User className="h-3 w-3 text-slate-400" />
            <span>Bạn</span>
          </>
        ) : (
          <>
            <Sparkles className="h-3 w-3 text-indigo-500" />
            <span className="font-semibold text-indigo-600 dark:text-indigo-400">AI Semantic Agent</span>
          </>
        )}
        <span>·</span>
        <span>{message.timestamp}</span>
      </div>

      <div
        className={`w-full rounded-2xl p-4.5 text-xs shadow-xs transition-all ${user
            ? 'max-w-2xl bg-gradient-to-r from-indigo-600 to-indigo-700 text-white shadow-indigo-500/10'
            : message.isError
              ? 'max-w-5xl border border-red-200 bg-red-50 text-red-700 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-300'
              : 'max-w-5xl border border-slate-200/90 bg-white text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100'
          }`}
      >
        {message.isError && (
          <p className="mb-2 flex items-center gap-1.5 font-bold text-red-600 dark:text-red-400">
            <AlertCircle className="h-4 w-4" /> Có lỗi xảy ra trong quá trình xử lý:
          </p>
        )}

        <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>

        {message.suggestions && message.suggestions.length > 0 && (
          <div className="mt-3.5 space-y-3.5">
            {message.suggestions.map((suggestion, index) => (
              <SuggestionCard
                key={`${message.id}-${index}`}
                suggestion={suggestion}
                saved={saved.includes(suggestion.definition.metric.name)}
                onSave={onSave}
                onEdit={onEdit}
                onRefine={onRefine}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 📦 Suggestion Card
// ---------------------------------------------------------------------------

function SuggestionCard({
  suggestion,
  saved,
  onSave,
  onEdit,
  onRefine,
}: {
  suggestion: MetricSuggestion;
  saved: boolean;
  onSave: (item: MetricSuggestion) => Promise<void>;
  onEdit?: (item: MetricSuggestion) => void;
  onRefine?: (item: MetricSuggestion) => void;
}) {
  const metric = suggestion.definition.metric;
  const [showYaml, setShowYaml] = useState(false);

  // Extract columns used in expression & filters
  const usedColumns = useMemo(() => {
    const cols = new Set<string>();
    const sqlKeywords = new Set([
      'SUM',
      'COUNT',
      'AVG',
      'MIN',
      'MAX',
      'CASE',
      'WHEN',
      'THEN',
      'ELSE',
      'END',
      'AND',
      'OR',
      'NOT',
      'NULL',
      'IS',
      'IN',
      'LIKE',
      'BETWEEN',
      'DISTINCT',
      'AS',
      'CAST',
      'COALESCE',
      'IFNULL',
      'NVL',
      'ROUND',
      'FLOOR',
      'CEIL',
      'ABS',
    ]);
    const matches = metric.formula.expression.match(/\b[a-zA-Z_][a-zA-Z0-9_]*\b/g);
    if (matches) {
      for (const m of matches) {
        if (!sqlKeywords.has(m.toUpperCase())) {
          cols.add(m);
        }
      }
    }
    if (metric.filters && Array.isArray(metric.filters)) {
      for (const f of metric.filters) {
        if (f.field) cols.add(f.field);
      }
    }
    return Array.from(cols);
  }, [metric.formula.expression, metric.filters]);

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4.5 shadow-sm dark:border-slate-800 dark:bg-slate-950/60 space-y-4">
      {/* 🌟 1. Metric Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-3 dark:border-slate-800/80">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-950/80 dark:text-indigo-400">
              <Sparkles className="h-4 w-4" />
            </span>
            <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              {metric.name}
            </h4>
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Chỉ số phân tích ngữ nghĩa được AI tính toán và chuẩn hóa
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold text-amber-700 dark:bg-amber-950 dark:text-amber-300">
            Chờ phê duyệt ({metric.status})
          </span>
          <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
            Độ tin cậy: {metric.confidence === 'high' ? 'Cao (High)' : metric.confidence === 'medium' ? 'Trung bình' : 'Khá'}
          </span>
        </div>
      </div>

      {/* 📊 2. Visual Metric Properties (Công thức, Bảng cơ sở, Cột sử dụng, Điều kiện lọc) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Box 1: Công thức tính toán */}
        <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-900/50">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            <Calculator className="h-3.5 w-3.5 text-indigo-500" />
            <span>Công thức tính (Formula):</span>
          </div>
          <div className="mt-1.5 font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50/80 dark:bg-indigo-950/60 p-2 rounded-lg border border-indigo-100 dark:border-indigo-900/40 break-all">
            <span className="text-purple-600 dark:text-purple-400">{metric.formula.function}</span>
            <span>(</span>
            <span className="text-indigo-700 dark:text-indigo-300">{metric.formula.expression}</span>
            <span>)</span>
          </div>
        </div>

        {/* Box 2: Dựa vào bảng nào */}
        <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-900/50">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            <Table2 className="h-3.5 w-3.5 text-emerald-500" />
            <span>Dựa vào bảng gốc (Base Table):</span>
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-xs font-bold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-900/40">
              <Database className="h-3.5 w-3.5" />
              {metric.base_entity}
            </span>
          </div>
        </div>

        {/* Box 3: Cột dữ liệu sử dụng */}
        <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-900/50">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            <Columns3 className="h-3.5 w-3.5 text-blue-500" />
            <span>Cột dữ liệu sử dụng:</span>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {usedColumns.length > 0 ? (
              usedColumns.map((col, idx) => (
                <span
                  key={idx}
                  className="rounded-md border border-slate-200 bg-white px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                >
                  {col}
                </span>
              ))
            ) : (
              <span className="text-[11px] text-slate-400 italic">Tất cả bản ghi trong bảng</span>
            )}
          </div>
        </div>

        {/* Box 4: Bộ lọc điều kiện (Filters) */}
        <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-900/50">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            <Filter className="h-3.5 w-3.5 text-amber-500" />
            <span>Bộ lọc điều kiện (Filters):</span>
          </div>
          <div className="mt-1.5">
            {metric.filters && metric.filters.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {metric.filters.map((f, idx) => (
                  <span
                    key={idx}
                    className="rounded-md border border-amber-200 bg-amber-50/80 px-2 py-0.5 text-[11px] font-mono font-medium text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/60 dark:text-amber-300"
                  >
                    {f.field} {f.operator} {String(f.value)}
                  </span>
                ))}
              </div>
            ) : (
              <span className="text-[11px] text-slate-400 italic">
                Không có bộ lọc (Tính trên toàn bộ bản ghi)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 💡 3. Notes if any */}
      {metric.excluded_notes && (
        <div className="rounded-xl bg-amber-50/70 p-3 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-300 border border-amber-200/80 dark:border-amber-900/50 flex items-start gap-2">
          <Info className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <strong>Lưu ý nghiệp vụ:</strong> {metric.excluded_notes}
          </div>
        </div>
      )}

      {/* 📄 4. Options cho người dùng chọn hiển thị YAML Preview */}
      <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-2.5 dark:border-slate-800 dark:bg-slate-900/40">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setShowYaml(!showYaml)}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-slate-800 cursor-pointer transition-all"
          >
            <Code2 className="h-3.5 w-3.5 text-indigo-500" />
            <span>{showYaml ? 'Ẩn mã YAML (YAML preview)' : 'Hiển thị mã YAML (YAML preview)'}</span>
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform ${showYaml ? 'rotate-180' : ''}`}
            />
          </button>

          <span className="text-[10px] text-slate-400">
            {showYaml ? 'Click để thu gọn YAML' : 'Click để xem chi tiết định nghĩa YAML'}
          </span>
        </div>

        {showYaml && (
          <div className="mt-2">
            <YamlCodeViewer yaml={suggestion.yaml_preview} title="Định nghĩa chỉ số (YAML preview)" />
          </div>
        )}
      </div>

      {/* ⚡ 5. Actions */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200/80 pt-3 dark:border-slate-800">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onRefine?.(suggestion)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-2xs hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 cursor-pointer"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
            Nhờ AI tinh chỉnh
          </button>
          <button
            type="button"
            onClick={() => onEdit?.(suggestion)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-2xs hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 cursor-pointer"
          >
            <Edit3 className="h-3.5 w-3.5" />
            Chỉnh sửa thủ công
          </button>
        </div>

        <button
          type="button"
          disabled={saved}
          onClick={() => void onSave(suggestion)}
          className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold text-white shadow-xs transition-all ${
            saved
              ? 'bg-emerald-600 opacity-90 cursor-default'
              : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95 cursor-pointer shadow-indigo-500/20'
          }`}
        >
          {saved ? (
            <>
              <CheckCircle2 className="h-4 w-4" />
              Đã lưu vào Semantic Layer
            </>
          ) : (
            <>
              <PlusCircle className="h-4 w-4" />
              Lưu vào Semantic Layer
            </>
          )}
        </button>
      </div>
    </article>
  );
}

