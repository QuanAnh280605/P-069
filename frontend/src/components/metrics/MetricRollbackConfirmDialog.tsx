'use client';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface MetricRollbackConfirmDialogProps {
  open: boolean;
  metricName: string;
  targetVersion: number;
  currentVersion: number;
  pending?: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}

export function MetricRollbackConfirmDialog({
  open,
  metricName,
  targetVersion,
  currentVersion,
  pending = false,
  onConfirm,
  onOpenChange,
}: MetricRollbackConfirmDialogProps) {
  const handleOpenChange = (nextOpen: boolean) => {
    if (pending && nextOpen === false) return;
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent showCloseButton={!pending} className="max-w-md">
        <DialogHeader>
          <DialogTitle className="text-base">Xác nhận khôi phục phiên bản</DialogTitle>
          <DialogDescription>
            Bạn sẽ khôi phục metric “{metricName}” về phiên bản v{targetVersion}.
          </DialogDescription>
        </DialogHeader>
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-600 dark:text-red-400">
          <p className="font-semibold">
            Mọi phiên bản mới hơn v{targetVersion} sẽ bị xóa vĩnh viễn và không thể hoàn tác.
          </p>
          <p>{`Phạm vi bị xóa: ${listAffectedVersions(targetVersion, currentVersion)}`}</p>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={pending}
            onClick={() => handleOpenChange(false)}
          >
            Hủy
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? 'Đang khôi phục...' : 'Khôi phục & xóa phiên bản mới'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function listAffectedVersions(target: number, current: number): string {
  const versions: string[] = [];
  for (let version = target + 1; version <= current; version += 1) {
    versions.push(`v${version}`);
  }
  return versions.join(', ');
}
