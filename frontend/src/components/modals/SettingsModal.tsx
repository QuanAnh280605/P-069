'use client';

import React from 'react';
import { History, Key, Moon, RefreshCw, ShieldCheck, Sparkles, Sun, Zap } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { useWorkspace } from '@/context/WorkspaceContext';
import { cn } from '@/lib/utils';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  databaseCount?: number;
  metricCount?: number;
  onOpenSyncLogs?: () => void;
}

const workspaceRoleLabels = {
  admin: 'Admin',
  data_lead: 'Data Lead',
  member: 'Member',
} as const;

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  databaseCount = 1,
  metricCount = 0,
  onOpenSyncLogs,
}) => {
  const { user, token } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { role } = useWorkspace();

  if (!isOpen) return null;

  const initials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'AI';

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="bg-background sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Settings</DialogTitle>
          <DialogDescription>
            Manage your workspace, account, and appearance.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 text-xs">
          {/* Account Card */}
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 shadow-2xs">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary font-mono text-sm font-bold text-primary-foreground">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">
                {user?.name || 'Guest User'}
              </p>
              <p className="truncate font-mono text-[11px] text-muted-foreground">
                {user?.email || 'guest@optimus.io'} · Workspace member
              </p>
            </div>
            <span className="rounded-full border border-border bg-secondary px-2.5 py-0.5 font-mono text-[10px] text-secondary-foreground">
              {role ? workspaceRoleLabels[role] : 'Chưa có vai trò'}
            </span>
          </div>

          {/* Appearance Switcher */}
          <div className="flex items-center justify-between rounded-lg border border-border bg-card p-3 shadow-2xs">
            <div className="flex items-center gap-3">
              {theme === 'dark' ? (
                <Moon className="h-4 w-4 text-primary" />
              ) : (
                <Sun className="h-4 w-4 text-amber-500" />
              )}
              <div>
                <Label className="text-sm font-medium">Appearance</Label>
                <p className="font-mono text-[11px] text-muted-foreground">
                  {theme === 'dark' ? 'Dark mode' : 'Light mode'}
                </p>
              </div>
            </div>
            <Switch
              checked={theme === 'dark'}
              onCheckedChange={toggleTheme}
              aria-label="Toggle dark mode"
            />
          </div>

          {/* Auto-Sync & Self-Healing Card */}
          <div className="rounded-lg border border-border bg-card p-3 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-500" />
                <Label className="text-sm font-medium">Tự động đồng bộ & Tự vá schema</Label>
              </div>
              <span className="flex items-center gap-1 font-mono text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="h-3.5 w-3.5" />
                Daily 02:00 AM
              </span>
            </div>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
              Phát hiện thay đổi schema (đổi tên/thêm/xóa cột) & tự động viết lại AST metric formula.
            </p>
            {onOpenSyncLogs && (
              <div className="mt-2.5 pt-2 border-t border-border/50 flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    onClose();
                    onOpenSyncLogs();
                  }}
                  className="h-7 gap-1.5 font-mono text-[11px]"
                >
                  <History className="h-3.5 w-3.5" />
                  Xem lịch sử đồng bộ (Audit Logs)
                </Button>
              </div>
            )}
          </div>

          {/* Guardrails Card */}
          <div className="rounded-lg border border-border bg-card p-3 shadow-2xs">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">Query guardrails</Label>
              <span className="flex items-center gap-1 font-mono text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="h-3.5 w-3.5" />
                Active
              </span>
            </div>
            <div className="mt-2 space-y-1.5 font-mono text-[11px] text-muted-foreground">
              <div className="flex items-center justify-between">
                <span>Read-only enforcement</span>
                <span className="text-emerald-500 font-semibold">Enabled</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Row limit (default / max)</span>
                <span className="text-foreground">100 / 1.000</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Statement timeout</span>
                <span className="text-foreground">15s</span>
              </div>
            </div>
          </div>

          {/* Workspace Stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-card p-3 shadow-2xs">
              <p className="font-display text-2xl text-foreground tabular-nums">{databaseCount}</p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Data sources
              </p>
            </div>
            <div className="rounded-lg border border-border bg-card p-3 shadow-2xs">
              <p className="font-display text-2xl text-foreground tabular-nums">{metricCount}</p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Metrics
              </p>
            </div>
          </div>

          {/* API Info */}
          <div className="rounded-lg border border-border bg-secondary/20 p-2.5 font-mono text-[10px] text-muted-foreground space-y-1">
            <div className="flex justify-between">
              <span>Engine:</span>
              <span className="text-foreground font-semibold">LangGraph + SemanticQueryCompiler</span>
            </div>
            {token && (
              <div className="flex justify-between truncate">
                <span>Token:</span>
                <span className="text-foreground truncate max-w-[200px]">{token.slice(0, 16)}...</span>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
