'use client';

import * as React from 'react';

import { EngineIcon, engineLabels, type WorkspaceDatabase } from './shared';

export interface ViewHeaderProps {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
  database?: WorkspaceDatabase | null;
}

export function ViewHeader({
  eyebrow,
  title,
  description,
  actions,
  database,
}: ViewHeaderProps) {
  return (
    <header className="relative overflow-hidden border-b border-border px-6 py-5">
      {/* Editorial grid backdrop */}
      <div className="ws-grid-bg pointer-events-none absolute inset-0" aria-hidden />

      <div className="relative flex items-start justify-between gap-4">
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
              <span className="ws-reveal inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-1 font-mono text-[11px] text-secondary-foreground [animation-delay:120ms]">
                <span
                  className={
                    database.status === 'connected'
                      ? 'h-1.5 w-1.5 rounded-full bg-emerald-500'
                      : 'h-1.5 w-1.5 rounded-full bg-muted-foreground/50'
                  }
                />
                <EngineIcon engine={database.engine} className="h-3 w-3" />
                {database.name}
                <span className="text-muted-foreground">· {engineLabels[database.engine]}</span>
              </span>
            )}
          </div>
          <p className="ws-reveal mt-1.5 max-w-2xl text-pretty text-sm text-muted-foreground [animation-delay:160ms]">
            {description}
          </p>
        </div>
        {actions && (
          <div className="ws-reveal flex shrink-0 items-center gap-2 [animation-delay:200ms]">
            {actions}
          </div>
        )}
      </div>
    </header>
  );
}
