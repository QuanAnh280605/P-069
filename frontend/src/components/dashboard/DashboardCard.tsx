'use client';

import { useCallback, useRef, useState } from 'react';
import { ExternalLink, Pencil, Trash2 } from 'lucide-react';

import { TimeGrain } from '@/lib/api';
import {
  DashboardDatePreset,
  DashboardWidgetConfig,
  getWidgetColSpan,
  getWidgetRowSpan,
} from '@/lib/dashboard';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

import { DashboardChart } from './DashboardChart';
import { useDashboardWidgetData } from './useDashboardWidgetData';

export interface DashboardCardProps {
  widget: DashboardWidgetConfig;
  dbId: number | string;
  globalGrain: TimeGrain | null;
  datePreset: DashboardDatePreset | null;
  refreshGeneration: number;
  querySupported: boolean;
  editMode: boolean;
  metricName: string;
  dimensionLabel: string | null;
  isFirst: boolean;
  isLast: boolean;
  dragHandleProps?: Record<string, unknown>;
  isDragging?: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onMoveLeft?: () => void;
  onMoveRight?: () => void;
  onResize?: (colSpan: number, rowSpan: number) => void;
  onLiveResize?: (colSpan: number, rowSpan: number) => void;
  onDrillDown?: (widget: DashboardWidgetConfig, datePreset: DashboardDatePreset | null) => void;
}

export function DashboardCard(props: DashboardCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const title = props.widget.custom_title ?? props.metricName;
  const subtitle = props.dimensionLabel
    ? props.widget.custom_title
      ? `${props.metricName} theo ${props.dimensionLabel}`
      : `Theo ${props.dimensionLabel}`
    : null;

  const data = useDashboardWidgetData({
    dbId: props.dbId,
    widget: props.widget,
    globalGrain: props.globalGrain,
    datePreset: props.datePreset,
    refreshGeneration: props.refreshGeneration,
    enabled: props.querySupported,
  });

  const [resizingSpan, setResizingSpan] = useState<{ colSpan: number; rowSpan: number } | null>(null);

  const startResize = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!props.editMode) return;

      e.preventDefault();
      e.stopPropagation();

      const card = cardRef.current;
      if (!card) return;

      const grid = card.parentElement?.parentElement;
      const gridRect = grid ? grid.getBoundingClientRect() : card.getBoundingClientRect();
      const gap = 16;
      const colWidth = (gridRect.width - gap * 23) / 24;
      const rowHeight = 40;

      const startX = e.clientX;
      const startY = e.clientY;
      const initialColSpan = getWidgetColSpan(props.widget);
      const initialRowSpan = getWidgetRowSpan(props.widget);

      let currentCols = initialColSpan;
      let currentRows = initialRowSpan;

      const onPointerMove = (moveEvent: PointerEvent) => {
        const dx = moveEvent.clientX - startX;
        const dy = moveEvent.clientY - startY;
        const deltaCols = Math.round(dx / (colWidth + gap));
        const deltaRows = Math.round(dy / (rowHeight + gap));

        const nextCols = Math.max(2, Math.min(24, initialColSpan + deltaCols));
        const nextRows = Math.max(3, Math.min(24, initialRowSpan + deltaRows));

        if (nextCols !== currentCols || nextRows !== currentRows) {
          currentCols = nextCols;
          currentRows = nextRows;
          setResizingSpan({ colSpan: nextCols, rowSpan: nextRows });
          props.onLiveResize?.(nextCols, nextRows);
        }
      };

      const onPointerUp = () => {
        window.removeEventListener('pointermove', onPointerMove);
        window.removeEventListener('pointerup', onPointerUp);
        setResizingSpan(null);
        if (props.onResize && (currentCols !== initialColSpan || currentRows !== initialRowSpan)) {
          props.onResize(currentCols, currentRows);
        }
      };

      window.addEventListener('pointermove', onPointerMove);
      window.addEventListener('pointerup', onPointerUp);
    },
    [props],
  );

  return (
    <section
      ref={cardRef}
      data-widget-id={props.widget.id}
      data-height={props.widget.height}
      aria-label={title}
      className={cn(
        'group relative flex h-full w-full flex-col overflow-hidden rounded-xl border border-border/80 bg-card shadow-xs transition-all select-none',
        props.editMode && 'cursor-grab hover:border-primary/50 hover:shadow-md',
        props.isDragging && 'cursor-grabbing opacity-50 ring-2 ring-primary',
        resizingSpan && 'ring-2 ring-primary/80',
      )}
      {...(props.editMode ? props.dragHandleProps : {})}
    >
      <CardHeader title={title} subtitle={subtitle} props={props} />

      <div className="min-h-0 min-w-0 flex-1 p-3 pt-1">
        <DashboardChart
          widget={props.widget}
          title={title}
          metricName={props.metricName}
          dimensionLabel={props.dimensionLabel}
          data={data}
        />
      </div>

      {/* Resize indicator & handle in bottom right corner (Cube Dev style) */}
      <ResizeHandle
        editMode={props.editMode}
        onPointerDown={startResize}
        resizingSpan={resizingSpan}
      />
    </section>
  );
}

function CardHeader({
  title,
  subtitle,
  props,
}: {
  title: string;
  subtitle: string | null;
  props: DashboardCardProps;
}) {
  return (
    <header className="flex shrink-0 items-start justify-between gap-2 px-3 pt-3 pb-1">
      <div className="min-w-0 flex-1">
        <h3
          data-testid="dashboard-card-title"
          className="truncate text-sm font-semibold text-foreground tracking-tight"
          title={title}
        >
          {title}
        </h3>
        {subtitle && (
          <p className="truncate text-xs text-muted-foreground" title={subtitle}>
            {subtitle}
          </p>
        )}
      </div>
      <div
        className="flex shrink-0 items-center gap-1"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        {props.onDrillDown && (
          <DrillDownButton onDrillDown={() => props.onDrillDown?.(props.widget, props.datePreset)} />
        )}
        {props.editMode && <EditControls props={props} title={title} />}
      </div>
    </header>
  );
}

function DrillDownButton({ onDrillDown }: { onDrillDown: () => void }) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      aria-label="Xem chi tiết"
      onClick={onDrillDown}
      className="h-7 w-7 text-muted-foreground hover:text-foreground"
    >
      <ExternalLink className="h-3.5 w-3.5" />
    </Button>
  );
}

function EditControls({ props, title }: { props: DashboardCardProps; title: string }) {
  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={`Chỉnh sửa widget ${title}`}
        onClick={props.onEdit}
        className="h-7 w-7 text-muted-foreground hover:text-foreground"
      >
        <Pencil className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={`Xóa widget ${title}`}
        onClick={props.onDelete}
        className="h-7 w-7 text-muted-foreground hover:text-destructive"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </>
  );
}

function ResizeHandle({
  editMode,
  onPointerDown,
  resizingSpan,
}: {
  editMode: boolean;
  onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => void;
  resizingSpan: { colSpan: number; rowSpan: number } | null;
}) {
  if (!editMode) return null;

  return (
    <div
      role="button"
      tabIndex={-1}
      aria-label="Kéo để thay đổi kích thước"
      onPointerDown={onPointerDown}
      onClick={(e) => e.stopPropagation()}
      className="absolute bottom-1 right-1 flex h-4 w-4 items-center justify-center cursor-se-resize select-none opacity-80 hover:opacity-100 transition-opacity"
      title="Kéo góc để thu phóng"
    >
      {/* Sleek Cube Dev corner icon `┘` */}
      <svg
        className="h-3.5 w-3.5 text-muted-foreground/70 hover:text-primary transition-colors"
        viewBox="0 0 10 10"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M8.5 2V8.5H2"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {resizingSpan && (
        <span className="absolute bottom-5 right-0 rounded bg-popover px-1.5 py-0.5 text-[10px] font-mono text-popover-foreground shadow-md border border-border pointer-events-none whitespace-nowrap z-50">
          {resizingSpan.colSpan}c × {resizingSpan.rowSpan}r
        </span>
      )}
    </div>
  );
}
