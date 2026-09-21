'use client';

import { CornerDownLeft, Loader2, Pencil, X } from 'lucide-react';
import { KeyboardEvent, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { ChatClarificationOption, ClarificationResolution } from '@/lib/api';
import { cn } from '@/lib/utils';

export interface ClarificationCardProps {
  prompt: string;
  options: ChatClarificationOption[];
  /** Persisted resolution; when present the card collapses to its resolved state. */
  resolution?: ClarificationResolution | null;
  /** True while a resolve request is in flight; disables every interactive control. */
  pending?: boolean;
  /** Error message from a failed resolve attempt; renders a retry control when set. */
  error?: string | null;
  /** When true and resolved, omits the prompt header if message bubble already displays it */
  hidePrompt?: boolean;
  className?: string;
  onSelectOption: (optionId: string, label: string) => void;
  onCustomAnswer: (text: string) => void;
  onSkip: () => void;
  onRetry?: () => void;
}

export function resolveAnswer(resolution: ClarificationResolution): string {
  if (resolution.status === 'skipped') return 'Đã bỏ qua';
  return (resolution.custom_answer?.trim() || resolution.selected_label || '').trim();
}

export function ClarificationCard({
  prompt,
  options,
  resolution,
  pending = false,
  error = null,
  hidePrompt = false,
  className,
  onSelectOption,
  onCustomAnswer,
  onSkip,
  onRetry,
}: ClarificationCardProps) {
  const [customText, setCustomText] = useState('');
  const customInputRef = useRef<HTMLInputElement>(null);

  const isResolved = !!resolution;
  const disabled = pending || isResolved;

  if (isResolved) {
    return (
      <div
        className={cn(
          'w-full space-y-1 rounded-xl border border-border/50 bg-secondary/20 p-3.5 text-sm transition-all dark:border-zinc-800/60 dark:bg-zinc-900/40',
          className,
        )}
        data-testid="clarification-resolved"
      >
        {!hidePrompt && (
          <p className="text-xs font-medium text-muted-foreground dark:text-zinc-400">{prompt}</p>
        )}
        <p className="text-sm font-semibold text-foreground dark:text-zinc-100">
          {resolveAnswer(resolution!)}
        </p>
      </div>
    );
  }

  const submitCustom = () => {
    const text = customText.trim();
    if (!text) return;
    onCustomAnswer(text);
  };

  const handleCustomKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      submitCustom();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setCustomText('');
      customInputRef.current?.blur();
    }
  };

  return (
    <div
      className={cn(
        'w-full overflow-hidden rounded-2xl border border-border/70 bg-card/95 text-card-foreground shadow-lg backdrop-blur-xs transition-all dark:border-zinc-800 dark:bg-zinc-900/95 dark:shadow-2xl',
        className,
      )}
      data-testid="clarification-card"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-border/40 px-4 py-3 sm:px-5 sm:py-3.5 dark:border-zinc-800/80">
        <h3 className="text-sm font-semibold leading-snug text-foreground dark:text-zinc-100">
          {prompt}
        </h3>
        <button
          type="button"
          onClick={onSkip}
          disabled={disabled}
          aria-label="Đóng"
          title="Bỏ qua"
          className="shrink-0 -mr-1 -mt-0.5 rounded-lg p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 cursor-pointer"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {error ? (
        <div
          role="alert"
          className="m-3 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive"
        >
          <p className="font-medium">{error}</p>
          {onRetry && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="mt-2 text-xs"
              onClick={onRetry}
              disabled={pending}
            >
              Thử lại
            </Button>
          )}
        </div>
      ) : null}

      <div className="flex flex-col">
        {/* Options list: Always visible */}
        <div className="divide-y divide-border/30 px-2 py-1.5 dark:divide-zinc-800/70">
          {options.map((opt, idx) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => onSelectOption(opt.id, opt.label)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  onSelectOption(opt.id, opt.label);
                }
              }}
              disabled={disabled}
              className="group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-foreground transition-colors hover:bg-accent/60 focus-visible:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 dark:text-zinc-200 dark:hover:bg-zinc-800/70 cursor-pointer"
            >
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-border/60 bg-muted text-[11px] font-semibold text-muted-foreground transition-colors group-hover:border-primary/40 group-hover:text-foreground dark:border-zinc-700/50 dark:bg-zinc-800 dark:text-zinc-400 dark:group-hover:text-zinc-200">
                {idx + 1}
              </span>
              <span className="flex-1 font-normal leading-snug">{opt.label}</span>
              <span
                aria-hidden="true"
                className="text-xs text-muted-foreground/60 transition-opacity group-hover:text-foreground group-hover:opacity-100 dark:text-zinc-500 dark:group-hover:text-zinc-300"
              >
                ↵
              </span>
            </button>
          ))}
        </div>

        {/* Footer Actions: Something else inline input + Skip button */}
        <div className="flex items-center justify-between gap-3 border-t border-border/40 px-3 py-2 sm:px-4 dark:border-zinc-800/80">
          <div className="relative flex min-w-0 flex-1 items-center">
            <Pencil className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-muted-foreground/70 dark:text-zinc-400" />
            <input
              ref={customInputRef}
              type="text"
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              onKeyDown={handleCustomKeyDown}
              placeholder="Something else"
              aria-label="Câu trả lời tùy chỉnh"
              disabled={disabled}
              className="w-full rounded-lg border border-transparent bg-transparent py-1.5 pl-8 pr-7 text-xs text-foreground placeholder:text-muted-foreground/80 outline-none transition-all hover:bg-muted/40 focus:border-border/60 focus:bg-background/80 dark:text-zinc-200 dark:placeholder:text-zinc-500 dark:hover:bg-zinc-800/60 dark:focus:border-zinc-700 dark:focus:bg-zinc-800/80"
            />
            {customText.trim() ? (
              <button
                type="button"
                onClick={submitCustom}
                disabled={disabled}
                aria-label="Gửi"
                title="Gửi câu trả lời"
                className="absolute right-2 flex h-4 w-4 items-center justify-center text-xs font-semibold text-primary transition-opacity hover:opacity-80 cursor-pointer"
              >
                ↵
              </button>
            ) : null}
          </div>

          <button
            type="button"
            onClick={onSkip}
            disabled={disabled}
            className="inline-flex shrink-0 items-center justify-center rounded-lg border border-border/60 bg-secondary/80 px-3.5 py-1 text-xs font-medium text-secondary-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:pointer-events-none disabled:opacity-50 dark:border-zinc-700/60 dark:bg-zinc-800/90 dark:text-zinc-300 dark:hover:bg-zinc-700 dark:hover:text-white cursor-pointer"
          >
            Skip
          </button>
        </div>
      </div>

      {pending && (
        <div
          className="flex items-center gap-2 border-t border-border/40 px-4 py-2 text-xs text-muted-foreground dark:border-zinc-800/80"
          role="status"
        >
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          <span>Đang xử lý...</span>
        </div>
      )}
    </div>
  );
}


