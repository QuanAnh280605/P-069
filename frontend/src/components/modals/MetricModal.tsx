'use client';

import { FormEvent, useState } from 'react';

import {
  MetricDefinition,
  METRIC_WRITE_PERMISSION_MESSAGE,
  SemanticCatalog,
  SemanticTable,
} from '@/lib/api';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { createMetricDefinition, withPendingStatus } from '@/lib/metrics';
import {
  MetricDefinitionForm,
  MetricModalFormProps,
  useMetricModalReset,
  validateDefinition,
} from '@/components/modals/MetricModalForm';
import {
  MetricModalHeader,
  MetricTabControls,
  TabKey,
  VersionHistory,
} from '@/components/modals/MetricModalShell';

export interface MetricVersion {
  version: number;
  definition?: MetricDefinition | null;
  change_reason?: string;
  created_at?: string;
}

interface MetricModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (definition: MetricDefinition, changeReason?: string) => Promise<void> | void;
  tables: SemanticTable[];
  initialDefinition?: MetricDefinition | null;
  initialName?: string;
  status?: string;
  onApprove?: () => Promise<void> | void;
  versions?: MetricVersion[];
  canSave?: boolean;
  saveDisabledReason?: string;
  submissionMode?: boolean;
  isMemberRequest?: boolean;
  /** Semantic database id used to fetch governed join-path options. */
  dbId?: string | null;
  /** Catalog used to resolve a base entity name to its numeric id. */
  catalog?: SemanticCatalog | null;
}

export function MetricModal(props: MetricModalProps) {
  const [definition, setDefinition] = useState<MetricDefinition>(createMetricDefinition());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<TabKey>('definition');
  const [changeReason, setChangeReason] = useState('');
  useMetricModalReset(props, setDefinition, setError, setChangeReason, setActiveTab);

  const setMetric = (patch: Partial<MetricDefinition['metric']>) =>
    setDefinition((current) => ({ metric: { ...current.metric, ...patch } }));
  const setPreferredPaths = (next: Record<string, number[]>) =>
    setDefinition((current) => ({ metric: { ...current.metric, preferred_join_paths: next } }));
  const requiresChangeReason =
    !props.submissionMode && !props.isMemberRequest && (props.status || definition.metric.status) === 'approved';
  const status = props.submissionMode
    ? 'unverified'
    : props.status || definition.metric.status || 'pending_approval';
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (props.canSave === false) {
      setError(props.saveDisabledReason || METRIC_WRITE_PERMISSION_MESSAGE);
      return;
    }
    const message = validateDefinition(definition);
    if (message) return setError(message);
    if (requiresChangeReason && !changeReason.trim()) {
      return setError('Chỉ số đã publish: vui lòng nhập lý do thay đổi để lưu vào lịch sử phiên bản.');
    }
    setSaving(true);
    setError('');
    try {
      await props.onSave(withPendingStatus(definition), changeReason);
      props.onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể lưu metric');
    } finally {
      setSaving(false);
    }
  };

  const formProps: MetricModalFormProps = {
    metric: definition.metric,
    setMetric,
    setPreferredPaths,
    tables: props.tables,
    dbId: props.dbId,
    catalog: props.catalog,
    requiresChangeReason,
    changeReason,
    setChangeReason,
    error,
    canSave: props.canSave,
    saveDisabledReason: props.saveDisabledReason,
    submissionMode: props.submissionMode,
    isMemberRequest: props.isMemberRequest,
    status,
    onApprove: props.onApprove,
    onClose: props.onClose,
    saving,
    submit,
    staleTargets: [] as string[],
    onStaleChange: () => {},
  };

  return (
    <Dialog open={props.isOpen} onOpenChange={(open) => !open && props.onClose()}>
      <DialogContent className="flex max-h-[88vh] flex-col overflow-hidden bg-background sm:max-w-3xl">
        <MetricModalHeader
          submissionMode={props.submissionMode}
          isMemberRequest={props.isMemberRequest}
          initialName={props.initialName}
          initialDefinition={props.initialDefinition}
          status={status}
          metricName={definition.metric.name}
          baseEntity={definition.metric.base_entity}
        />
        <MetricTabControls
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          versionsLength={props.versions?.length || 0}
        />
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {activeTab === 'definition' ? (
            <MetricDefinitionForm {...formProps} />
          ) : (
            <div className="p-4">
              <VersionHistory versions={props.versions || []} />
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
