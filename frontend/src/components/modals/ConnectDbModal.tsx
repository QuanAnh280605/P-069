'use client';

import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileText,
  HardDrive,
  Loader2,
  ShieldCheck,
  Upload,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/context/AuthContext';
import {
  connectLiveTargetDb,
  convertRawSchemaToLayer,
  saveImportedSchema,
  updateLayer,
  uploadSqlDumpPreview,
} from '@/lib/api';
import { getStoredToken } from '@/lib/jwt';
import { cn } from '@/lib/utils';
import { DbEngine, EngineIcon, engineLabels } from '@/components/workspace/shared';

interface ConnectDbModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newDbName: string, dbId?: string) => void;
}

const engines: DbEngine[] = ['postgresql', 'mysql', 'sqlite', 'dump'];

export const ConnectDbModal: React.FC<ConnectDbModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { token } = useAuth();
  const [engine, setEngine] = useState<DbEngine>('postgresql');
  const [dbName, setDbName] = useState('');
  const [connUrl, setConnUrl] = useState('');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');

  const isDump = engine === 'dump';

  const resetForm = () => {
    setDbName('');
    setConnUrl('');
    setDescription('');
    setFile(null);
    setError('');
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!dbName.trim()) return;

    setIsProcessing(true);
    setError('');
    const accessToken = token || getStoredToken();

    if (!accessToken) {
      setError('Vui lòng đăng nhập để lưu kết nối an toàn trên backend.');
      setIsProcessing(false);
      return;
    }

    try {
      if (isDump) {
        if (!file) {
          setError('Vui lòng chọn một tệp SQL dump.');
          setIsProcessing(false);
          return;
        }
        const preview = await uploadSqlDumpPreview(file, '', accessToken);
        const name = dbName.trim() || file.name.replace(/\.sql$/i, '');
        const savedRecord = await saveImportedSchema(name, preview, accessToken);
        const newLayer = convertRawSchemaToLayer(
          savedRecord.id,
          savedRecord.display_name || name,
          savedRecord.dialect || 'auto',
          savedRecord.raw_schema,
          undefined,
          savedRecord.updated_at,
          savedRecord.semantic_db_id,
          'sql_dump',
        );
        updateLayer(newLayer);
        onSuccess(name, newLayer.id);
        handleClose();
      } else {
        if (!connUrl.trim()) {
          setError('Vui lòng nhập chuỗi kết nối Database.');
          setIsProcessing(false);
          return;
        }
        const dbType = engine === 'sqlite' ? 'sqlite' : engine === 'mysql' ? 'mysql' : 'auto';
        const liveRecord = await connectLiveTargetDb(
          dbName.trim(),
          dbType,
          connUrl.trim(),
          accessToken,
        );
        const newLayer = convertRawSchemaToLayer(
          liveRecord.id,
          liveRecord.display_name || dbName.trim(),
          liveRecord.dialect || dbType,
          liveRecord.raw_schema,
          undefined,
          liveRecord.updated_at,
          liveRecord.semantic_db_id,
          'live',
        );
        updateLayer(newLayer);
        onSuccess(dbName.trim(), newLayer.id);
        handleClose();
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : isDump
            ? 'Tải lên và trích xuất SQL dump thất bại'
            : 'Kết nối và trích xuất schema thất bại';
      setError(msg);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="bg-background sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Connect a data source</DialogTitle>
          <DialogDescription>
            Point Optimus at a live database or upload a SQL dump. Credentials are read-only.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {/* Engine Selector */}
          <div>
            <Label className="mb-2 block font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Engine
            </Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {engines.map((e) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => setEngine(e)}
                  className={cn(
                    'flex items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors cursor-pointer',
                    engine === e
                      ? 'border-primary bg-accent text-foreground font-semibold'
                      : 'border-border text-muted-foreground hover:text-foreground',
                  )}
                >
                  <EngineIcon engine={e} className="h-4 w-4 shrink-0" />
                  <span className="truncate text-xs">{engineLabels[e]}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Connection Name */}
          <div>
            <Label htmlFor="db-name" className="mb-1.5 block text-sm">
              Connection name
            </Label>
            <Input
              id="db-name"
              value={dbName}
              onChange={(e) => setDbName(e.target.value)}
              placeholder="e.g. E-Commerce Production DB"
              required
            />
          </div>

          {/* Connection String or Dump Upload */}
          {!isDump ? (
            <div>
              <Label htmlFor="db-host" className="mb-1.5 block text-sm">
                Host / connection string
              </Label>
              <Input
                id="db-host"
                value={connUrl}
                onChange={(e) => setConnUrl(e.target.value)}
                placeholder="postgresql+asyncpg://user:pass@localhost:5432/analytics"
                required
              />
            </div>
          ) : (
            <div>
              <Label htmlFor="db-file" className="mb-1.5 block text-sm">
                Tệp SQL Dump (.sql)
              </Label>
              <Input
                id="db-file"
                type="file"
                accept=".sql"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="cursor-pointer file:cursor-pointer"
                required
              />
            </div>
          )}

          {/* Description */}
          <div>
            <Label htmlFor="db-desc" className="mb-1.5 block text-sm">
              Description
            </Label>
            <Input
              id="db-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Mô tả mục đích hoặc nội dung của nguồn dữ liệu này"
            />
          </div>

          {/* Guardrails Safety Box */}
          <div className="rounded-lg border border-border bg-secondary/30 p-3 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
              <span>Bảo vệ an toàn dữ liệu:</span>
            </div>
            <ul className="mt-1 space-y-0.5 font-mono text-[11px] text-muted-foreground">
              <li>• Chỉ dành cho Live DB.</li>
              <li>• Truy vấn SELECT-only, được biên dịch deterministic.</li>
              <li>• Mặc định 100 dòng · Tối đa 1.000 dòng.</li>
              <li>• Timeout 15 giây.</li>
            </ul>
          </div>

          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={handleClose}>
              Hủy
            </Button>
            <Button type="submit" disabled={!dbName.trim() || isProcessing} className="gap-1.5">
              {isProcessing && <Loader2 className="h-4 w-4 animate-spin" />}
              {isProcessing
                ? 'Đang xử lý...'
                : isDump
                  ? 'Tải lên & Khởi tạo Schema'
                  : 'Bắt Đầu Kết Nối & Introspect'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
