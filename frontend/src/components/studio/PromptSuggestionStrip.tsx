'use client';

import { PointerEvent, useEffect, useRef, useState } from 'react';

import { cn } from '@/lib/utils';

export interface PromptSuggestionItem {
  icon?: string;
  title: string;
  prompt: string;
}

interface PromptSuggestionStripProps {
  items: PromptSuggestionItem[];
  onSelect: (prompt: string) => void;
}

interface DragState {
  pointerId: number | null;
  startX: number;
  startScrollLeft: number;
  moved: boolean;
}

const EMPTY_DRAG_STATE: DragState = {
  pointerId: null,
  startX: 0,
  startScrollLeft: 0,
  moved: false,
};

const DRAG_THRESHOLD_PX = 12;

export function PromptSuggestionStrip({ items, onSelect }: PromptSuggestionStripProps) {
  const stripRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState>(EMPTY_DRAG_STATE);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  useEffect(() => {
    const strip = stripRef.current;
    if (!strip) return;
    const syncHints = () => updateScrollHints(strip, setCanScrollLeft, setCanScrollRight);
    syncHints();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(syncHints);
    observer.observe(strip);
    return () => observer.disconnect();
  }, [items]);

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary) return;
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startScrollLeft: event.currentTarget.scrollLeft,
      moved: false,
    };
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (drag.pointerId !== event.pointerId) return;
    const distance = event.clientX - drag.startX;
    if (Math.abs(distance) > DRAG_THRESHOLD_PX) {
      if (!drag.moved) {
        drag.moved = true;
        try {
          event.currentTarget.setPointerCapture?.(event.pointerId);
        } catch {
          // ignore
        }
      }
      event.currentTarget.scrollLeft = drag.startScrollLeft - distance;
      updateScrollHints(event.currentTarget, setCanScrollLeft, setCanScrollRight);
    }
  };

  const handlePointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.pointerId !== event.pointerId) return;
    if (dragRef.current.moved) {
      try {
        event.currentTarget.releasePointerCapture?.(event.pointerId);
      } catch {
        // ignore
      }
    }
    dragRef.current.pointerId = null;
    window.setTimeout(() => {
      dragRef.current.moved = false;
    }, 0);
  };

  const handleSelect = (prompt: string) => {
    if (dragRef.current.moved) {
      dragRef.current.moved = false;
      return;
    }
    onSelect(prompt);
  };

  return (
    <div className="relative">
      <div
        ref={stripRef}
        aria-label="Danh sách câu hỏi gợi ý, kéo ngang để xem thêm"
        className="flex touch-pan-x gap-1.5 overflow-x-auto whitespace-nowrap pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden cursor-grab select-none active:cursor-grabbing"
        data-testid="prompt-suggestion-strip"
        onPointerCancel={handlePointerEnd}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerEnd}
        onScroll={(event) => updateScrollHints(event.currentTarget, setCanScrollLeft, setCanScrollRight)}
      >
        {items.map((item) => (
          <button
            key={item.prompt}
            type="button"
            className="inline-flex shrink-0 items-center rounded-full border border-border bg-secondary/60 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-foreground/30 hover:bg-secondary hover:text-foreground cursor-pointer"
            onClick={() => handleSelect(item.prompt)}
          >
            <span>{item.title}</span>
          </button>
        ))}
      </div>
      <ScrollFade className="left-0 bg-gradient-to-r" visible={canScrollLeft} />
      <ScrollFade className="right-0 bg-gradient-to-l" visible={canScrollRight} />
    </div>
  );
}

function ScrollFade({ className, visible }: { className: string; visible: boolean }) {
  if (!visible) return null;
  return <div aria-hidden className={cn('pointer-events-none absolute inset-y-0 w-8 from-card/95 to-transparent', className)} />;
}

function updateScrollHints(
  element: HTMLDivElement,
  setCanScrollLeft: (value: boolean) => void,
  setCanScrollRight: (value: boolean) => void,
) {
  setCanScrollLeft(element.scrollLeft > 0);
  setCanScrollRight(element.scrollLeft + element.clientWidth < element.scrollWidth - 1);
}
