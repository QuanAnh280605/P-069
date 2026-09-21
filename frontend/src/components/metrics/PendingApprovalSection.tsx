'use client';

import { Sparkles, User } from 'lucide-react';

import { MetricCard } from '@/components/metrics/MetricCard';
import { MetricRequestCard } from '@/components/metrics/MetricRequestCard';
import { MetricRecord, MetricRequest } from '@/lib/api';

interface PendingApprovalSectionProps {
  canManage: boolean;
  canApprove: boolean;
  isMemberSubmitter: boolean;
  pendingRequests: MetricRequest[];
  pendingMetrics: MetricRecord[];
  submittedMetrics: MetricRecord[];
  onEditRequest?: (req: MetricRequest) => void;
  onApproveRequest: (req: MetricRequest) => void;
  onRejectRequest: (req: MetricRequest) => void;
  onEditMetric?: (m: MetricRecord) => void;
  onDeleteMetric?: (id: number) => Promise<void> | void;
  onHistory: (id: number) => Promise<void>;
  onApproveMetric?: (id: number) => Promise<void> | void;
}

export function PendingApprovalSection({
  canManage,
  canApprove,
  isMemberSubmitter,
  pendingRequests,
  pendingMetrics,
  submittedMetrics,
  onEditRequest,
  onApproveRequest,
  onRejectRequest,
  onEditMetric,
  onDeleteMetric,
  onHistory,
  onApproveMetric,
}: PendingApprovalSectionProps) {
  const showRequests = canManage && pendingRequests.length > 0;
  const metricsToShow = isMemberSubmitter ? submittedMetrics : pendingMetrics;
  const showMetrics = metricsToShow.length > 0;

  return (
    <div className="space-y-4">
      {showRequests && (
        <div className="space-y-2">
          {showMetrics && (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                <User className="h-3 w-3" />
                Yêu cầu metric từ Member ({pendingRequests.length})
              </span>
              <span className="text-[11px] text-muted-foreground">
                Chờ Data Lead phê duyệt để khởi tạo metric
              </span>
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {pendingRequests.map((req) => (
              <MetricRequestCard
                key={req.id}
                request={req}
                onEdit={canManage ? onEditRequest : undefined}
                onApprove={() => onApproveRequest(req)}
                onReject={() => onRejectRequest(req)}
              />
            ))}
          </div>
        </div>
      )}

      {showMetrics && (
        <div className="space-y-2">
          {showRequests && (
            <div className="flex items-center gap-2 pt-2">
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                <Sparkles className="h-3 w-3" />
                Đề xuất hệ thống & Bản nháp ({metricsToShow.length})
              </span>
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {metricsToShow.map((metric) => (
              <MetricCard
                key={metric.metric_id}
                metric={metric}
                onEdit={canManage ? onEditMetric : undefined}
                onDelete={canManage ? onDeleteMetric : undefined}
                onHistory={onHistory}
                onApprove={canApprove ? onApproveMetric : undefined}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
