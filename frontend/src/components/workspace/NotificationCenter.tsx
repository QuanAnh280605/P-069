'use client';

import { Bell, CheckCircle2, ChevronRight, Inbox, XCircle } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { AppNotification } from '@/lib/api';
import { cn } from '@/lib/utils';

interface EventStyle {
  Icon: typeof Bell;
  chip: string;
}

const EVENT_STYLES: Record<string, EventStyle> = {
  metric_request_submitted: { Icon: Inbox, chip: 'bg-primary/10 text-primary' },
  metric_request_approved: {
    Icon: CheckCircle2,
    chip: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  },
  metric_request_rejected: { Icon: XCircle, chip: 'bg-destructive/10 text-destructive' },
};

const NEUTRAL_STYLE: EventStyle = { Icon: Bell, chip: 'bg-secondary text-muted-foreground' };

function eventStyle(type: string): EventStyle {
  return EVENT_STYLES[type] ?? NEUTRAL_STYLE;
}

function isMetricRequestNotification(item: AppNotification): boolean {
  return item.type.startsWith('metric_request');
}

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'vừa xong';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  return `${Math.floor(hours / 24)} ngày trước`;
}

function NotificationRowContent({ item }: { item: AppNotification }) {
  const { Icon, chip } = eventStyle(item.type);
  return (
    <>
      <span className={cn('mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md', chip)}>
        <Icon className="h-3.5 w-3.5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5">
          {!item.read_at && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />}
          <span className="truncate text-xs font-medium text-foreground">{item.title}</span>
        </span>
        <span className="mt-0.5 block truncate text-[11px] text-muted-foreground">{item.body}</span>
      </span>
      <span className="mt-1 shrink-0 font-mono text-[10px] text-muted-foreground/80">
        {timeAgo(item.created_at)}
      </span>
      {isMetricRequestNotification(item) && (
        <ChevronRight className="mt-2 h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
      )}
    </>
  );
}

function NotificationRow({
  item,
  onOpen,
}: {
  item: AppNotification;
  onOpen: (item: AppNotification) => void;
}) {
  if (!isMetricRequestNotification(item)) {
    return (
      <div className="flex items-start gap-2.5 border-t border-border px-3 py-2.5">
        <NotificationRowContent item={item} />
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(item)}
      className="flex w-full cursor-pointer items-start gap-2.5 border-t border-border px-3 py-2.5 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
    >
      <NotificationRowContent item={item} />
    </button>
  );
}

export function NotificationCenter({
  items,
  unreadCount,
  onOpenCatalog,
  onMarkAllRead,
}: {
  items: AppNotification[];
  unreadCount: number;
  onOpenCatalog: () => void;
  onMarkAllRead: () => Promise<void> | void;
}) {
  const [open, setOpen] = useState(false);

  const openItem = (item: AppNotification) => {
    if (!isMetricRequestNotification(item)) return;
    setOpen(false);
    onOpenCatalog();
  };

  return (
    <div className="fixed right-6 top-16 z-60">
      <Button
        size="icon"
        variant="outline"
        className="relative cursor-pointer"
        onClick={() => setOpen((current) => !current)}
        aria-label="Thông báo"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 rounded-full bg-primary px-1.5 text-[10px] text-primary-foreground">
            {unreadCount}
          </span>
        )}
      </Button>
      {open && (
        <div className="absolute right-0 mt-2 w-[min(20rem,calc(100vw-2rem))] animate-in fade-in slide-in-from-top-2 rounded-lg border border-border bg-card p-2 shadow-xl">
          <div className="flex items-center justify-between px-1 pb-1">
            <p className="text-sm font-semibold text-foreground">Thông báo</p>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => void onMarkAllRead()}
                className="cursor-pointer font-mono text-[10px] text-primary hover:underline"
              >
                Đánh dấu đã đọc
              </button>
            )}
          </div>
          <div className="max-h-[26rem] overflow-y-auto">
            {items.length ? (
              items.map((item) => <NotificationRow key={item.id} item={item} onOpen={openItem} />)
            ) : (
              <div className="flex flex-col items-center gap-2 border-t border-border px-4 py-8 text-center">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary">
                  <Bell className="h-4 w-4 text-muted-foreground" />
                </span>
                <p className="text-xs font-medium text-foreground">Chưa có thông báo</p>
                <p className="text-[11px] text-muted-foreground">
                  Yêu cầu metric và kết quả phê duyệt sẽ xuất hiện tại đây.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
