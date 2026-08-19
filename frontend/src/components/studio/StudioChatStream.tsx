'use client';

import {
  AlertCircle,
  ArrowUp,
  Bot,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Edit3,
  Lightbulb,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  User,
  Wand2,
} from 'lucide-react';
import React, { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { MetricSuggestion } from '@/lib/api';
import { cn } from '@/lib/utils';
import { YamlCodeViewer } from '@/components/studio/YamlCodeViewer';
import { SectionLabel, StatusPill } from '@/components/workspace/shared';

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
  onOpenCatalog?: () => void;
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
      'Tính tổng doanh thu thuần của các đơn hàng có trạng thái thành công (status = "completed" hoặc "delivered")',
  },
  {
    icon: '👥',
    title: 'Số lượng khách hàng mới tháng 1/2025',
    prompt:
      'Đếm số lượng khách hàng mới đăng ký trong tháng 1 năm 2025 (created_time từ 2025-01-01 đến 2025-01-31)',
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
    await props.onSendMessage(prompt, []);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
  };

  const handleSelectSuggestion = (promptText: string) => {
    setInput(promptText);
  };

  const save = async (suggestion: MetricSuggestion) => {
    try {
      await props.onAddMetric?.(suggestion);
      setSaved((current) => [...current, suggestion.definition.metric.name]);
    } catch {
      // Error is handled in callback
    }
  };

  const contextualSuggestions = useMemo(() => {
    const list: PromptSuggestionItem[] = [...DEFAULT_SUGGESTIONS];
    const lowerTables = props.tableNames.map((t) => t.toLowerCase());

    if (
      lowerTables.some((t) => t.includes('customer') || t.includes('khach_hang') || t.includes('user'))
    ) {
      list.push({
        icon: '🌟',
        title: 'Khách hàng VIP mua trên 5 đơn',
        prompt: 'Đếm số lượng khách hàng thân thiết có từ 5 đơn hàng thành công trở lên',
      });
    }
    if (
      lowerTables.some((t) => t.includes('product') || t.includes('san_pham') || t.includes('item'))
    ) {
      list.push({
        icon: '🏷️',
        title: 'Top sản phẩm bán chạy',
        prompt: 'Tính tổng doanh số và số lượng bán theo từng danh mục sản phẩm',
      });
    }
    return list;
  }, [props.tableNames]);

  return (
    <div className="flex h-full w-full flex-1 flex-col overflow-hidden bg-background text-foreground">
      {/* 💬 Messages Stream */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-8">
          {props.messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              saved={saved}
              onSave={save}
              onEdit={props.onEditMetric}
              onRefine={props.onRefineWithAI}
              onOpenCatalog={props.onOpenCatalog}
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
                  <span>AI đang phân tích cấu trúc Schema & quan hệ...</span>
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
                  GỢI Ý CÂU HỎI TẠO METRIC
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
              <div className="flex flex-wrap gap-1.5 pt-1">
                {contextualSuggestions.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSelectSuggestion(item.prompt)}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/60 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-foreground/30 hover:bg-secondary hover:text-foreground cursor-pointer"
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
              placeholder="Mô tả chỉ số bạn muốn tạo hoặc đặt câu hỏi về schema..."
              className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
            <Button
              size="icon"
              className="h-9 w-9 shrink-0 rounded-lg"
              onClick={() => void send()}
              disabled={!input.trim() || props.isLoading}
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          </div>
          <p className="text-center font-mono text-[10px] text-muted-foreground">
            AI can make mistakes. Every generated metric requires human approval before use.
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
}: {
  message: ChatMessage;
  saved: string[];
  onSave: (suggestion: MetricSuggestion) => Promise<void>;
  onEdit?: (suggestion: MetricSuggestion) => void;
  onRefine?: (suggestion: MetricSuggestion) => void;
  onOpenCatalog?: () => void;
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

        <div
          className={cn(
            'inline-block max-w-full rounded-lg px-4 py-3 text-sm leading-relaxed shadow-2xs',
            isUser
              ? 'bg-secondary text-secondary-foreground'
              : 'border border-border bg-card text-card-foreground',
            message.isError && 'border-destructive/30 bg-destructive/10 text-destructive',
          )}
        >
          {message.text}
        </div>

        {message.suggestions && message.suggestions.length > 0 && (
          <div className="w-full space-y-4 pt-1">
            {message.suggestions.map((sug, idx) => (
              <SuggestionCard
                key={idx}
                suggestion={sug}
                isSaved={saved.includes(sug.definition.metric.name)}
                onSave={() => onSave(sug)}
                onEdit={() => onEdit?.(sug)}
                onRefine={() => onRefine?.(sug)}
                onOpenCatalog={onOpenCatalog}
              />
            ))}
          </div>
        )}
      </div>
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
}: {
  suggestion: MetricSuggestion;
  isSaved: boolean;
  onSave: () => Promise<void>;
  onEdit?: () => void;
  onRefine?: () => void;
  onOpenCatalog?: () => void;
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
            className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setShowYaml(!showYaml)}
          >
            <Code2 className="h-3.5 w-3.5" />
            {showYaml ? 'Ẩn mã YAML' : 'Hiển thị mã YAML'}
          </Button>
          {onRefine && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
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
              className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
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

        {/* YAML Preview */}
        {showYaml && (
          <div className="mt-3 overflow-hidden rounded-md border border-border bg-secondary/20">
            <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
              <span className="font-mono text-[11px] text-muted-foreground">YAML preview</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 gap-1 text-[11px]"
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
          Pending status · Phê duyệt trong catalog trước khi truy vấn
        </span>

        {isSaved ? (
          <Button
            size="sm"
            variant="secondary"
            className="h-8 gap-1.5 text-xs text-emerald-600 dark:text-emerald-400"
            onClick={onOpenCatalog}
          >
            <Check className="h-3.5 w-3.5" />
            Đã lưu — mở catalog
          </Button>
        ) : (
          <Button
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => void handleSave()}
            disabled={saving}
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? 'Đang lưu...' : 'Lưu vào Semantic Layer'}
          </Button>
        )}
      </div>
    </div>
  );
}
