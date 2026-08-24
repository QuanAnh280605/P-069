'use client';

import {
  ArrowUp,
  Bot,
  Check,
  Code2,
  Copy,
  Edit3,
  Lightbulb,
  RefreshCw,
  Save,
  Sparkles,
  User,
} from 'lucide-react';
import React, { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Button } from '@/components/ui/button';
import { MetricSuggestion } from '@/lib/api';
import { cn } from '@/lib/utils';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { StatusPill } from '@/components/workspace/shared';
import {
  ChatDuplicateNotice,
  ConflictWarningStrip,
  DuplicateNoticeCard,
} from '@/components/studio/DedupeWarnings';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  suggestions?: MetricSuggestion[];
  duplicates?: ChatDuplicateNotice[];
  dedupeSkipped?: boolean;
  suggestionAction?: 'save_metric' | 'submit_metric_request' | null;
  timestamp: string;
  isError?: boolean;
}

/** Dedupe-related message actions, addressed by (messageId, suggestion index). */
type SuggestionIndexHandler = (messageId: string, index: number) => void;

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
  onOpenCatalog?: () => void;
  mode?: 'data_assistant' | 'metric_studio';
  savedMetricNames?: string[];
  submittedRequestKeys?: ReadonlySet<string>;
  approvedRequestKeys?: ReadonlySet<string>;
  onRenameSuggestion?: SuggestionIndexHandler;
  onDiscardSuggestion?: SuggestionIndexHandler;
  onDismissDuplicate?: SuggestionIndexHandler;
  onUseExistingDuplicate?: SuggestionIndexHandler;
  onSubmitMetricRequest?: (messageId: string, suggestionIndex: number) => Promise<void>;
}

export function metricRequestKey(messageId: string, suggestionIndex: number): string {
  return `${messageId}:${suggestionIndex}`;
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
    prompt:
      'Tính tổng doanh thu thuần của các đơn hàng có trạng thái hoàn thành (Net Revenue)',
  },
  {
    icon: '📦',
    title: 'Tổng số lượng đơn đặt hàng',
    prompt: 'Tính tổng số lượng đơn đặt hàng phát sinh trong toàn hệ thống',
  },
  {
    icon: '🎫',
    title: 'Giá trị trung bình mỗi đơn (AOV)',
    prompt: 'Tính giá trị trung bình trên mỗi đơn hàng (Average Order Value - AOV)',
  },
];

const DATA_ASSISTANT_SUGGESTIONS: PromptSuggestionItem[] = [
  {
    icon: '🔎',
    title: 'Tìm metric doanh thu đã duyệt',
    prompt: 'Có những metric doanh thu nào đã được phê duyệt? Giải thích ngắn gọn từng metric.',
  },
  {
    icon: '🧭',
    title: 'Tìm bảng khách hàng',
    prompt: 'Bảng hoặc cột nào liên quan đến khách hàng trong semantic layer này?',
  },
  {
    icon: '🧩',
    title: 'Hướng dẫn chọn dữ liệu',
    prompt: 'Nếu muốn xem doanh thu theo tháng và cửa hàng, tôi nên chọn metric và dimension nào?',
  },
  {
    icon: '📖',
    title: 'Giải thích metric',
    prompt: 'Giải thích công thức và phạm vi dữ liệu của metric doanh thu đã được duyệt.',
  },
];

export function StudioChatStream(props: StudioChatStreamProps) {
  const mode = props.mode || 'metric_studio';
  const canGenerateMetrics = mode === 'metric_studio';
  const [input, setInput] = useState(props.activePromptText || '');
  const [saved, setSaved] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ startX: number; scrollLeft: number; isDragging: boolean; moved: boolean }>({
    startX: 0,
    scrollLeft: 0,
    isDragging: false,
    moved: false,
  });

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = stripRef.current;
    if (!el) return;
    dragRef.current = {
      startX: e.clientX,
      scrollLeft: el.scrollLeft,
      isDragging: true,
      moved: false,
    };
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragRef.current.isDragging || !stripRef.current) return;
    const dx = e.clientX - dragRef.current.startX;
    if (Math.abs(dx) > 5) {
      dragRef.current.moved = true;
    }
    stripRef.current.scrollLeft = dragRef.current.scrollLeft - dx;
  };

  const handlePointerUp = () => {
    dragRef.current.isDragging = false;
  };

  const allSavedNames = useMemo(() => {
    const set = new Set<string>();
    (props.savedMetricNames || []).forEach((name) => {
      if (name) set.add(name.trim().toLowerCase());
    });
    saved.forEach((name) => {
      if (name) set.add(name.trim().toLowerCase());
    });
    return set;
  }, [props.savedMetricNames, saved]);

  useEffect(() => {
    if (props.activePromptText) {
      setInput(props.activePromptText);
    }
  }, [props.activePromptText]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [props.messages, props.isLoading]);

  const send = async () => {
    if (!input.trim() || props.isLoading) return;
    const text = input.trim();
    setInput('');
    await props.onSendMessage(text, props.tableNames);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  const save = async (suggestion: MetricSuggestion) => {
    if (props.onAddMetric) {
      await props.onAddMetric(suggestion);
      setSaved((prev) => [...prev, suggestion.definition.metric.name]);
    }
  };

  const handleSelectSuggestion = (promptText: string) => {
    setInput(promptText);
  };

  const toggleShowSuggestions = () => {
    setShowSuggestions((prev) => !prev);
  };

  const contextualSuggestions = useMemo(() => {
    const list = [
      ...(canGenerateMetrics ? DEFAULT_SUGGESTIONS : DATA_ASSISTANT_SUGGESTIONS),
    ];
    const tableStr = props.tableNames.join(' ').toLowerCase();
    if (canGenerateMetrics && (tableStr.includes('order') || tableStr.includes('don_hang'))) {
      list.unshift({
        icon: '📈',
        title: 'Tỷ lệ hủy đơn hàng',
        prompt: 'Định nghĩa chỉ số tỷ lệ đơn hàng bị hủy so với tổng đơn',
      });
    }
    if (canGenerateMetrics && (tableStr.includes('product') || tableStr.includes('san_pham'))) {
      list.push({
        icon: '🏷️',
        title: 'Top sản phẩm bán chạy',
        prompt: 'Tính tổng doanh số và số lượng bán theo từng danh mục sản phẩm',
      });
    }
    return list;
  }, [canGenerateMetrics, props.tableNames]);

  const hasUserSentMessage = useMemo(
    () => props.messages.some((m) => m.sender === 'user'),
    [props.messages],
  );

  return (
    <div className="flex h-full w-full flex-1 flex-col overflow-hidden bg-background text-foreground">
      {/* 💬 Messages Stream */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-8">
          {!canGenerateMetrics && (
            <div role="status" className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-xs text-blue-700 dark:text-blue-300">
              Bạn không có quyền tạo, sửa hoặc lưu metric trực tiếp. Bạn có thể tra cứu dữ liệu qua các metric đã duyệt (chỉ áp dụng cho kết nối Live DB) hoặc yêu cầu AI tạo Business Metric mới. Metric sau khi tạo sẽ được lưu vào Semantic Layer ở trạng thái chờ Data Lead phê duyệt.
            </div>
          )}
          {props.messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              saved={allSavedNames}
              onSave={save}
              onEdit={props.onEditMetric}
              onRefine={props.onRefineWithAI}
              onOpenCatalog={props.onOpenCatalog}
              onSubmitMetricRequest={props.onSubmitMetricRequest}
              submittedKeys={props.submittedRequestKeys || new Set()}
              approvedKeys={props.approvedRequestKeys || new Set()}
              onRenameSuggestion={props.onRenameSuggestion}
              onDiscardSuggestion={props.onDiscardSuggestion}
              onDismissDuplicate={props.onDismissDuplicate}
              onUseExistingDuplicate={props.onUseExistingDuplicate}
            />
          ))}

          {props.isLoading && (
            <div className="flex gap-4">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-primary text-primary-foreground">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex flex-col gap-2 rounded-lg border border-border bg-card px-4 py-3.5 shadow-xs">
                <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                  <Sparkles className="h-3.5 w-3.5 animate-spin text-primary" />
                  <span>
                    {canGenerateMetrics
                      ? 'AI đang phân tích cấu trúc Schema & quan hệ...'
                      : 'AI đang đọc semantic layer và metric đã phê duyệt...'}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 pt-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
                </div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {/* 💡 Suggested Prompts Bar & Composer */}
      <div className="border-t border-border bg-card/40 px-6 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          {/* Suggested Questions Chips */}
          <div className="space-y-2 rounded-lg border border-border bg-card p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-3.5 w-3.5 text-amber-500" />
                <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                  {canGenerateMetrics ? 'GỢI Ý CÂU HỎI TẠO METRIC' : 'GỢI Ý CÂU HỎI VỀ DỮ LIỆU'}
                </span>
                {showSuggestions && (
                  <span className="font-mono text-[10px] text-muted-foreground/70">
                    ({contextualSuggestions.length} mẫu)
                  </span>
                )}
              </div>

              <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showSuggestions}
                  onChange={toggleShowSuggestions}
                  className="h-3.5 w-3.5 rounded border-border accent-primary cursor-pointer"
                />
                <span>{showSuggestions ? 'Hiển thị gợi ý' : 'Đã ẩn (Tick để hiện)'}</span>
              </label>
            </div>

            {showSuggestions && (
              <div
                ref={stripRef}
                data-testid="prompt-suggestion-strip"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className="flex overflow-x-auto whitespace-nowrap gap-1.5 pt-1"
              >
                {contextualSuggestions.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSelectSuggestion(item.prompt)}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/60 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-foreground/30 hover:bg-secondary hover:text-foreground cursor-pointer shrink-0"
                  >
                    <span>{item.icon}</span>
                    <span>{item.title}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Composer Input Box */}
          <div className="flex items-end gap-2 rounded-xl border border-border bg-card p-2 shadow-xs focus-within:border-foreground/30 focus-within:ring-1 focus-within:ring-ring/20">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              placeholder={
                canGenerateMetrics
                  ? 'Mô tả chỉ số bạn muốn tạo hoặc đặt câu hỏi về schema...'
                  : 'Hỏi về schema, metric đã duyệt hoặc cách chọn dữ liệu...'
              }
              className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
            <Button
              size="icon"
              className="h-9 w-9 shrink-0 rounded-lg cursor-pointer"
              onClick={() => void send()}
              disabled={!input.trim() || props.isLoading}
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-center font-mono text-[10px] text-muted-foreground">
            {canGenerateMetrics
              ? 'AI can make mistakes. Every generated metric requires human approval before use.'
              : 'AI chỉ trả lời dựa trên semantic layer và metric đã được cấp quyền.'}
          </p>
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
  onOpenCatalog,
  onSubmitMetricRequest,
  submittedKeys,
  approvedKeys,
  onRenameSuggestion,
  onDiscardSuggestion,
  onDismissDuplicate,
  onUseExistingDuplicate,
}: {
  message: ChatMessage;
  saved: ReadonlySet<string>;
  onSave: (suggestion: MetricSuggestion) => Promise<void>;
  onEdit?: (suggestion: MetricSuggestion) => void;
  onRefine?: (suggestion: MetricSuggestion) => void;
  onOpenCatalog?: () => void;
  onSubmitMetricRequest?: (messageId: string, suggestionIndex: number) => Promise<void>;
  submittedKeys: ReadonlySet<string>;
  approvedKeys: ReadonlySet<string>;
  onRenameSuggestion?: SuggestionIndexHandler;
  onDiscardSuggestion?: SuggestionIndexHandler;
  onDismissDuplicate?: SuggestionIndexHandler;
  onUseExistingDuplicate?: SuggestionIndexHandler;
}) {
  const isUser = message.sender === 'user';

  return (
    <div className={cn('flex gap-4', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-md border',
          isUser
            ? 'border-border bg-secondary text-secondary-foreground'
            : 'border-border bg-primary text-primary-foreground',
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div className={cn('min-w-0 flex-1 space-y-3', isUser && 'flex flex-col items-end')}>
        <div className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
          <span className="font-semibold text-foreground">
            {isUser ? 'Bạn' : 'AI Semantic Agent'}
          </span>
          <span>·</span>
          <span>{message.timestamp}</span>
        </div>

        {/* The description line is hidden once every duplicate notice is settled. */}
        {message.text ? (
          <div
            className={cn(
              'inline-block rounded-xl px-4 py-3 text-sm leading-relaxed shadow-2xs',
              isUser
                ? 'max-w-full bg-secondary text-secondary-foreground'
                : 'max-w-4xl border border-border bg-card text-card-foreground',
              message.isError && 'border-destructive/30 bg-destructive/10 text-destructive',
            )}
          >
            {isUser ? message.text : <AssistantMarkdown content={message.text} />}
          </div>
        ) : null}

        {message.dedupeSkipped && (
          <div
            role="status"
            className="w-full rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 font-mono text-[11px] text-amber-700 dark:text-amber-300"
          >
            ⚠️ Không kiểm tra được trùng lặp (dedupe unavailable) — danh sách chưa so với metric đã lưu.
          </div>
        )}

        {message.suggestions && message.suggestions.length > 0 && (
          <div className="w-full space-y-4 pt-1">
            {message.suggestions.map((sug, idx) => (
              <SuggestionCard
                key={idx}
                suggestion={sug}
                isSaved={saved.has(sug.definition.metric.name.trim().toLowerCase())}
                onSave={() => onSave(sug)}
                onEdit={() => onEdit?.(sug)}
                onRefine={() => onRefine?.(sug)}
                onOpenCatalog={onOpenCatalog}
                action={message.suggestionAction}
                isSubmitted={submittedKeys.has(metricRequestKey(message.id, idx))}
                isApproved={
                  approvedKeys.has(metricRequestKey(message.id, idx)) ||
                  saved.has(sug.definition.metric.name.trim().toLowerCase())
                }
                onSubmitRequest={
                  onSubmitMetricRequest ? () => onSubmitMetricRequest(message.id, idx) : undefined
                }
                onRename={() => onRenameSuggestion?.(message.id, idx)}
                onUseExisting={() => onDiscardSuggestion?.(message.id, idx)}
              />
            ))}
          </div>
        )}

        {message.duplicates && message.duplicates.length > 0 && (
          <div className="w-full space-y-3 pt-1">
            {message.duplicates.map((notice, idx) => (
              <DuplicateNoticeCard
                key={`${message.id}-dup-${idx}`}
                notice={notice}
                onDismiss={() => onDismissDuplicate?.(message.id, idx)}
                onUseExisting={() => onUseExistingDuplicate?.(message.id, idx)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function renderFormattedContent(node: React.ReactNode): React.ReactNode {
  if (typeof node === 'string') {
    if (!/<br\s*\/?>/i.test(node)) {
      return node;
    }
    const parts = node.split(/(<br\s*\/?>)/gi);
    return parts.map((part, i) => {
      if (/<br\s*\/?>/i.test(part)) {
        return <br key={i} className="my-0.5" />;
      }
      return part;
    });
  }
  if (Array.isArray(node)) {
    return React.Children.map(node, renderFormattedContent);
  }
  if (React.isValidElement(node) && (node.props as { children?: React.ReactNode })?.children) {
    return React.cloneElement(
      node,
      undefined,
      renderFormattedContent((node.props as { children?: React.ReactNode }).children),
    );
  }
  return node;
}

function AssistantMarkdown({ content }: { content: string }) {
  return (
    <div className="prose prose-sm max-w-none text-card-foreground prose-headings:font-display prose-headings:text-foreground prose-p:my-2 prose-p:leading-7 prose-strong:text-foreground prose-li:my-1 prose-li:leading-6 prose-a:text-primary prose-a:underline prose-blockquote:border-primary/40 prose-blockquote:text-muted-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h3 className="mb-2 mt-4 text-base font-semibold first:mt-0">{renderFormattedContent(children)}</h3>,
          h2: ({ children }) => <h3 className="mb-2 mt-4 text-base font-semibold first:mt-0">{renderFormattedContent(children)}</h3>,
          h3: ({ children }) => <h4 className="mb-2 mt-3 text-sm font-semibold">{renderFormattedContent(children)}</h4>,
          p: ({ children }) => <p className="my-2 leading-7 first:mt-0 last:mb-0">{renderFormattedContent(children)}</p>,
          strong: ({ children }) => <strong className="font-semibold text-foreground">{renderFormattedContent(children)}</strong>,
          em: ({ children }) => <em className="text-muted-foreground">{renderFormattedContent(children)}</em>,
          ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{renderFormattedContent(children)}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{renderFormattedContent(children)}</ol>,
          li: ({ children }) => <li className="my-1">{renderFormattedContent(children)}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-2 pl-3 italic">{renderFormattedContent(children)}</blockquote>
          ),
          code: ({ className, children, ...props }) => (
            <code
              className={cn(
                className
                  ? 'block overflow-x-auto rounded-md bg-secondary/80 p-3 font-mono text-xs leading-5'
                  : 'rounded bg-secondary px-1.5 py-0.5 font-mono text-[0.85em] text-primary',
              )}
              {...props}
            >
              {children}
            </code>
          ),
          pre: ({ children }) => <pre className="my-3 overflow-x-auto rounded-md">{children}</pre>,
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-lg border border-border bg-card shadow-xs">
              <table className="w-full min-w-[520px] border-collapse text-left text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-secondary/70 font-semibold">{children}</thead>,
          tbody: ({ children }) => <tbody className="divide-y divide-border [&>tr:last-child>td]:border-b-0">{children}</tbody>,
          tr: ({ children }) => <tr className="transition-colors hover:bg-muted/20">{children}</tr>,
          th: ({ children }) => <th className="border-b border-border px-3.5 py-2.5 font-semibold text-foreground">{children}</th>,
          td: ({ children }) => (
            <td className="border-b border-border px-3.5 py-2.5 align-top text-card-foreground leading-relaxed">
              {renderFormattedContent(children)}
            </td>
          ),
          hr: () => <hr className="my-4 border-border" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function SuggestionCard({
  suggestion,
  isSaved,
  onSave,
  onEdit,
  onRefine,
  onOpenCatalog,
  onRename,
  onUseExisting,
  action,
  isSubmitted,
  isApproved,
  onSubmitRequest,
}: {
  suggestion: MetricSuggestion;
  isSaved: boolean;
  onSave: () => Promise<void>;
  onEdit?: () => void;
  onRefine?: () => void;
  onOpenCatalog?: () => void;
  onRename?: () => void;
  onUseExisting?: () => void;
  action?: 'save_metric' | 'submit_metric_request' | null;
  isSubmitted?: boolean;
  isApproved?: boolean;
  onSubmitRequest?: () => Promise<void>;
}) {
  const [showYaml, setShowYaml] = useState(false);
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);

  const def = suggestion.definition.metric;
  const yamlContent = suggestion.yaml_preview || JSON.stringify(suggestion.definition, null, 2);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave();
    } catch {
      // Handled by parent error notification
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitRequest = async () => {
    setSaving(true);
    try {
      await onSubmitRequest?.();
    } catch {
      // Handled by parent error notification
    } finally {
      setSaving(false);
    }
  };

  const copyYaml = () => {
    void navigator.clipboard?.writeText(yamlContent);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="w-full overflow-hidden rounded-lg border border-border bg-card shadow-xs">
      {/* ⚠️ Conflict clarify strip — same name as a saved metric, different formula */}
      {suggestion.conflict && (
        <div className="border-b border-border bg-secondary/20 p-3">
          <ConflictWarningStrip
            conflict={suggestion.conflict}
            onRename={() => onRename?.()}
            onUseExisting={() => onUseExisting?.()}
          />
        </div>
      )}

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-secondary/30 px-4 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-foreground text-sm">{def.name}</h3>
            <StatusPill status={def.status || 'pending_approval'} />
            <span className="font-mono text-[10px] text-muted-foreground">
              Chờ phê duyệt
            </span>
            <span className="rounded bg-secondary px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
              Độ tin cậy: {def.confidence === 'high' ? 'Cao' : def.confidence === 'medium' ? 'Trung bình' : 'Thấp'}
            </span>
          </div>
          <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
            Bảng: <span className="text-foreground">{def.base_entity}</span>
            <span className="ml-2 opacity-60">YAML preview sẵn sàng</span>
          </p>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            onClick={() => setShowYaml(!showYaml)}
          >
            <Code2 className="h-3.5 w-3.5" />
            {showYaml ? 'Ẩn mã YAML' : 'Hiển thị mã YAML'}
          </Button>
          {onRefine && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
              onClick={onRefine}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Nhờ AI tinh chỉnh
            </Button>
          )}
          {onEdit && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
              onClick={onEdit}
            >
              <Edit3 className="h-3.5 w-3.5" />
              Chỉnh sửa thủ công
            </Button>
          )}
        </div>
      </div>

      {/* Visual Properties */}
      <div className="space-y-2 p-4 text-xs">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-secondary/30 p-2.5">
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              Công thức tính
            </span>
            <p className="mt-0.5 font-mono text-xs font-medium text-foreground">
              <span className="text-primary font-bold">{def.formula.function}</span>(
              <span>{def.formula.expression}</span>)
            </p>
          </div>
          <div className="rounded-md border border-border bg-secondary/30 p-2.5">
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              Dựa vào bảng gốc
            </span>
            <p className="mt-0.5 font-mono text-xs font-medium text-foreground">
              {def.base_entity}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-secondary/30 p-2.5">
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              Cột dữ liệu sử dụng
            </span>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">
              {def.formula.expression}
            </p>
          </div>
          <div className="rounded-md border border-border bg-secondary/30 p-2.5">
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              Bộ lọc điều kiện
            </span>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">
              {def.filters && def.filters.length > 0
                ? def.filters.map((f) => `${f.field} ${f.operator} ${f.value ?? ''}`).join(', ')
                : 'Không có bộ lọc'}
            </p>
          </div>
        </div>

        {def.excluded_notes && (
          <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5">
            <span className="font-mono text-[10px] uppercase text-amber-700 dark:text-amber-300 font-semibold">
              Giả định cần xác nhận
            </span>
            <p className="mt-0.5 text-xs text-amber-800 dark:text-amber-200">
              {def.excluded_notes}
            </p>
          </div>
        )}

        {/* YAML Preview */}
        {showYaml && (
          <div className="mt-3 overflow-hidden rounded-md border border-border bg-secondary/20">
            <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
              <span className="font-mono text-[11px] text-muted-foreground">YAML preview</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 gap-1 text-[11px] cursor-pointer"
                onClick={copyYaml}
              >
                {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                {copied ? 'Đã copy' : 'Copy YAML'}
              </Button>
            </div>
            <pre className="overflow-x-auto p-3 font-mono text-xs leading-relaxed text-foreground">
              {yamlContent}
            </pre>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 border-t border-border bg-secondary/20 px-4 py-2.5">
        <span className="font-mono text-[11px] text-muted-foreground">
          {suggestion.conflict
            ? 'Xử lý cảnh báo trùng tên trước khi lưu'
            : 'Pending status · Phê duyệt trong catalog trước khi truy vấn'}
        </span>

        {/* ⛔ No Save/Submit while the conflict strip is unresolved — user must clarify first */}
        {!suggestion.conflict &&
          (action === 'submit_metric_request' ? (
            isApproved || isSaved ? (
              <Button
                size="sm"
                variant="secondary"
                className="h-8 gap-1.5 text-xs text-emerald-600 dark:text-emerald-400"
                disabled
              >
                <Check className="h-3.5 w-3.5" />
                Đã được Data Lead duyệt
              </Button>
            ) : isSubmitted ? (
              <Button
                size="sm"
                variant="secondary"
                className="h-8 gap-1.5 text-xs text-emerald-600 dark:text-emerald-400"
                disabled
              >
                <Check className="h-3.5 w-3.5" />
                Đã gửi cho Data Lead
              </Button>
            ) : (
              <Button
                size="sm"
                className="h-8 gap-1.5 text-xs cursor-pointer"
                onClick={() => void handleSubmitRequest()}
                disabled={saving}
              >
                <Save className="h-3.5 w-3.5" />
                {saving ? 'Đang gửi...' : 'Gửi Data Lead xem xét'}
              </Button>
            )
          ) : isSaved ? (
            <Button
              size="sm"
              variant="secondary"
              className="h-8 gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 cursor-pointer"
              onClick={onOpenCatalog}
            >
              <Check className="h-3.5 w-3.5" />
              Đã lưu — mở catalog
            </Button>
          ) : (
            <Button
              size="sm"
              className="h-8 gap-1.5 text-xs cursor-pointer"
              onClick={() => void handleSave()}
              disabled={saving}
            >
              <Save className="h-3.5 w-3.5" />
              {saving ? 'Đang lưu...' : 'Lưu vào Semantic Layer'}
            </Button>
          ))}
      </div>
    </div>
  );
}
