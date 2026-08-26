'use client';

import * as React from 'react';
import { Bell, History, ShieldCheck, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EngineIcon, engineLabels, type WorkspaceDatabase } from './shared';

export interface ViewHeaderProps {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
  database?: WorkspaceDatabase | null;
  onOpenSyncLogs?: () => void;
  hasHealedLogs?: boolean;
}

export function ViewHeader({
  eyebrow,
  title,
  description,
  actions,
  database,
  onOpenSyncLogs,
  hasHealedLogs,
}: ViewHeaderProps) {
  return (
    <header className="view-header-container relative overflow-hidden border-b border-border px-4 py-5 sm:px-6">
      {/* Editorial grid backdrop */}
      <div className="ws-grid-bg pointer-events-none absolute inset-0" aria-hidden />

      <div className="view-header-layout relative">
        <div className="min-w-0">
          {eyebrow && (
            <span className="ws-reveal mb-2 inline-flex items-center gap-2.5 font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              <span className="h-px w-7 bg-foreground/30" />
              {eyebrow}
            </span>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="ws-reveal font-display text-3xl leading-none tracking-tight text-foreground [animation-delay:60ms]">
              {title}
            </h1>
            {database && (
              <span className="ws-reveal inline-flex max-w-full min-w-0 flex-wrap items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-1 font-mono text-[11px] text-secondary-foreground [animation-delay:120ms]">
                <span
                  className={
                    database.status === 'connected'
                      ? 'h-1.5 w-1.5 rounded-full bg-emerald-500'
                      : 'h-1.5 w-1.5 rounded-full bg-muted-foreground/50'
                  }
                />
                <EngineIcon engine={database.engine} className="h-3 w-3" />
                <span className="min-w-0 truncate">{database.name}</span>
                <span className="shrink-0 text-muted-foreground">· {engineLabels[database.engine]}</span>
              </span>
            )}
            {database && onOpenSyncLogs && (
              <Button
                variant="outline"
                size="sm"
                onClick={onOpenSyncLogs}
                title="Lịch sử đồng bộ & tự phục hồi schema"
                className="ws-reveal h-7 gap-1.5 rounded-full border-border/80 px-2.5 font-mono text-[11px] text-muted-foreground hover:text-foreground [animation-delay:140ms]"
              >
                <div className="relative flex items-center justify-center">
                  <Bell className="h-3.5 w-3.5" />
                  {hasHealedLogs && (
                    <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-background" />
                  )}
                </div>
                <span className="hidden sm:inline">Auto-Sync</span>
              </Button>
            )}
          </div>
          <p className="ws-reveal mt-1.5 max-w-2xl text-pretty text-sm text-muted-foreground [animation-delay:160ms]">
            {description}
          </p>
        </div>
        {actions && (
          <div className="view-header-actions ws-reveal [animation-delay:200ms]">
            {actions}
          </div>
        )}
      </div>
    </header>
  );
}
