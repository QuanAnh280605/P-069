'use client';

import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Edit3,
  PlusCircle,
  Send,
  Sparkles,
  User,
} from 'lucide-react';
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';

import { MetricSuggestion } from '@/lib/api';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';

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
  onSendMessage: (promptText: string, targetTables: string[]) => Promise<void>;
  isLoading: boolean;
  tableNames: string[];
  onAddMetric?: (suggestion: MetricSuggestion) => Promise<void> | void;
  onEditMetric?: (suggestion: MetricSuggestion) => void;
  onRefineWithAI?: (suggestion: MetricSuggestion) => void;
  activePromptText?: string;
  theme?: 'light' | 'dark';
}

export function StudioChatStream(props: StudioChatStreamProps) {
  const [input, setInput] = useState(props.activePromptText || '');
  const [saved, setSaved] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => setInput(props.activePromptText || ''), [props.activePromptText]);
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

  const save = async (suggestion: MetricSuggestion) => {
    await props.onAddMetric?.(suggestion);
    setSaved((current) => [...current, suggestion.definition.metric.name]);
  };

  return (
    <div className='mx-auto flex h-full w-full max-w-4xl flex-col overflow-hidden'>
      {/* Messages Stream */}
      <div className='flex-1 space-y-4 overflow-y-auto px-1 py-2'>
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
          <div className='flex items-center gap-2 text-xs text-indigo-500 py-2'>
            <Bot className='h-4 w-4 animate-pulse' /> AI đang phân tích toàn bộ semantic schema & tạo Metric Definition...
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Modern Minimal Input Area */}
      <div className='space-y-1.5 border-t border-slate-200 pt-3 dark:border-slate-800'>
        <form
          onSubmit={send}
          className='flex gap-2 rounded-2xl border border-slate-300 bg-white p-2.5 shadow-sm transition-all focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900'
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
            placeholder='Mô tả chỉ số bạn muốn tạo (ví dụ: Tính tổng doanh thu theo đơn hàng, Số lượng khách hàng mới)...'
            className='flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-slate-400 dark:placeholder:text-slate-500'
          />
          <button
            type='submit'
            disabled={!input.trim() || props.isLoading}
            className='self-end rounded-xl bg-indigo-600 p-2.5 text-white shadow transition-all hover:bg-indigo-700 active:scale-95 disabled:opacity-40'
            title='Gửi yêu cầu (Enter)'
          >
            <Send className='h-4 w-4' />
          </button>
        </form>
        <div className='flex items-center justify-between px-2 text-[11px] text-slate-400'>
          <span>💡 AI tự động tìm kiếm trên toàn bộ dữ liệu</span>
          <span>Nhấn <strong>Enter</strong> để gửi, <strong>Shift + Enter</strong> để xuống dòng</span>
        </div>
      </div>
    </div>
  );
}

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
      <div className='mb-1 flex items-center gap-1.5 px-1 text-[11px] text-slate-500'>
        {user ? <User className='h-3 w-3' /> : <Sparkles className='h-3 w-3 text-indigo-500' />}
        {user ? 'Bạn' : 'AI Semantic Agent'} · {message.timestamp}
      </div>
      <div
        className={`w-full max-w-3xl rounded-2xl p-4 text-xs ${
          user
            ? 'max-w-xl bg-indigo-600 text-white'
            : message.isError
            ? 'border border-red-200 bg-red-50 text-red-700 dark:bg-red-950/40'
            : 'border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
        }`}
      >
        {message.isError && (
          <p className='mb-2 flex items-center gap-1 font-bold'>
            <AlertCircle className='h-4 w-4' /> Có lỗi xảy ra
          </p>
        )}
        <p className='whitespace-pre-wrap leading-relaxed'>{message.text}</p>
        {message.suggestions?.map((suggestion, index) => (
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
    </div>
  );
}

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
  return (
    <article className='mt-4 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-950/40'>
      <div className='flex items-center justify-between gap-2'>
        <div>
          <h4 className='text-sm font-bold text-slate-800 dark:text-slate-100'>{metric.name}</h4>
          <p className='mt-1 font-mono text-[11px] text-indigo-600 dark:text-indigo-400'>
            {metric.formula.function}({metric.formula.expression}) · Thực thể: <strong>{metric.base_entity}</strong>
          </p>
        </div>
        <span className='rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-bold text-amber-700 dark:bg-amber-950 dark:text-amber-300'>
          {metric.status}
        </span>
      </div>

      {metric.excluded_notes && (
        <p className='text-xs text-slate-600 dark:text-slate-400'>
          <strong>Lưu ý:</strong> {metric.excluded_notes}
        </p>
      )}

      <YamlCodeViewer yaml={suggestion.yaml_preview} title='Định nghĩa chỉ số (YAML preview)' />

      <div className='flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-3 dark:border-slate-800'>
        <div className='flex gap-2'>
          <button
            type='button'
            onClick={() => onRefine?.(suggestion)}
            className='rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
          >
            <Sparkles className='mr-1 inline h-3 w-3 text-indigo-500' />
            Nhờ AI tinh chỉnh
          </button>
          <button
            type='button'
            onClick={() => onEdit?.(suggestion)}
            className='rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-medium text-slate-700 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
          >
            <Edit3 className='mr-1 inline h-3 w-3' />
            Chỉnh sửa thủ công
          </button>
        </div>

        <button
          type='button'
          disabled={saved}
          onClick={() => void onSave(suggestion)}
          className={`rounded-xl px-4 py-1.5 text-xs font-bold text-white shadow transition-all ${
            saved
              ? 'bg-emerald-600 opacity-90 cursor-default'
              : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95'
          }`}
        >
          {saved ? (
            <>
              <CheckCircle2 className='mr-1 inline h-3.5 w-3.5' />
              Đã lưu vào Semantic Layer
            </>
          ) : (
            <>
              <PlusCircle className='mr-1 inline h-3.5 w-3.5' />
              Lưu vào Semantic Layer
            </>
          )}
        </button>
      </div>
    </article>
  );
}
