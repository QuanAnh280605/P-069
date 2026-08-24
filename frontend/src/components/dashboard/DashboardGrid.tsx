'use client';

import { type CSSProperties, useMemo, useState } from 'react';
import {
  Announcements,
  closestCenter,
  DndContext,
  DragEndEvent,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  rectSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
} from '@dnd-kit/sortable';
import { MetricRecord, SemanticCatalog, TimeGrain } from '@/lib/api';
import {
  DashboardDatePreset,
  DashboardWidgetConfig,
  getWidgetColSpan,
  getWidgetRowSpan,
} from '@/lib/dashboard';
import { cn } from '@/lib/utils';

import { DashboardCard } from './DashboardCard';

export function reorderWidgets(
  widgets: DashboardWidgetConfig[],
  activeId: string,
  overId: string,
): DashboardWidgetConfig[] {
  const oldIndex = widgets.findIndex((w) => w.id === activeId);
  const newIndex = widgets.findIndex((w) => w.id === overId);
  if (oldIndex < 0 || newIndex < 0 || oldIndex === newIndex) return widgets;
  return arrayMove(widgets, oldIndex, newIndex);
}

export function widthToSpanClass(width: DashboardWidgetConfig['width']): string {
  switch (width) {
    case 'third':
      return 'col-span-1 md:col-span-8';
    case 'half':
      return 'col-span-1 md:col-span-12';
    case 'full':
      return 'col-span-1 md:col-span-24';
  }
}

export interface DashboardGridProps {
  widgets: DashboardWidgetConfig[];
  dbId: number | string;
  globalGrain: TimeGrain | null;
  datePreset: DashboardDatePreset | null;
  refreshGeneration: number;
  querySupported: boolean;
  editMode: boolean;
  metrics: MetricRecord[];
  catalog: SemanticCatalog | null;
  onReorder: (next: DashboardWidgetConfig[]) => void;
  onResizeWidget?: (widgetId: string, colSpan: number, rowSpan: number) => void;
  onEditWidget: (widget: DashboardWidgetConfig) => void;
  onDeleteWidget: (widget: DashboardWidgetConfig) => void;
  onDrillDown?: (widget: DashboardWidgetConfig, datePreset: DashboardDatePreset | null) => void;
}

interface WidgetViewModel {
  widget: DashboardWidgetConfig;
  metricName: string;
  dimensionLabel: string | null;
}

const gridAnnouncements: Announcements = {
  onDragStart: ({ active }) => `Bắt đầu kéo widget ${String(active.id)}.`,
  onDragOver: ({ active, over }) =>
    over ? `Widget ${String(active.id)} đang qua ${String(over.id)}.` : '',
  onDragEnd: ({ active, over }) =>
    over
      ? `Widget ${String(active.id)} thả tại ${String(over.id)}.`
      : `Hủy kéo widget ${String(active.id)}.`,
  onDragCancel: ({ active }) => `Đã hủy kéo widget ${String(active.id)}.`,
};

export function DashboardGrid(props: DashboardGridProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const models = buildWidgetViewModels(props);

  const estimatedRows = useMemo(() => {
    const totalRowSpan = props.widgets.reduce((acc, w) => acc + getWidgetRowSpan(w), 0);
    return Math.max(24, Math.ceil(totalRowSpan / 2) + 8);
  }, [props.widgets]);
  const totalGridCells = estimatedRows * 24;

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const next = reorderWidgets(props.widgets, String(active.id), String(over.id));
    if (next !== props.widgets) props.onReorder(next);
  }

  return (
    <div className="relative min-h-[500px] w-full">
      {/* Visual background slots for empty spaces in Edit Mode (Cube Dev style) */}
      {props.editMode && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 grid grid-cols-1 md:grid-cols-24 gap-4 auto-rows-[40px] z-0 select-none"
        >
          {Array.from({ length: totalGridCells }).map((_, i) => (
            <div
              key={i}
              className="h-[40px] rounded-lg border border-border/25 bg-muted/15 dark:border-white/[0.04] dark:bg-white/[0.025]"
            />
          ))}
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={(event) => setActiveId(String(event.active.id))}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setActiveId(null)}
        accessibility={{ announcements: gridAnnouncements }}
      >
        <SortableContext items={props.widgets.map((w) => w.id)} strategy={rectSortingStrategy}>
          <ul className="relative z-10 grid grid-cols-1 md:grid-cols-24 gap-4 auto-rows-[40px] w-full items-start">
            {models.map((model, index) => (
              <SortableCard
                key={model.widget.id}
                model={model}
                index={index}
                total={models.length}
                gridProps={props}
                isActive={activeId === model.widget.id}
              />
            ))}
          </ul>
        </SortableContext>
        <DragOverlay>
          {activeId ? <DragPreview widget={props.widgets.find((w) => w.id === activeId)} models={models} /> : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}

function buildWidgetViewModels(props: DashboardGridProps): WidgetViewModel[] {
  const nameById = new Map(props.metrics.map((m) => [m.metric_id, m.name]));
  return props.widgets.map((widget) => ({
    widget,
    metricName: nameById.get(widget.metric_id) ?? `Metric ${widget.metric_id}`,
    dimensionLabel: resolveDimensionLabel(widget, props.catalog),
  }));
}

function resolveDimensionLabel(
  widget: DashboardWidgetConfig,
  catalog: SemanticCatalog | null,
): string | null {
  if (widget.dimension_col_id === null || !catalog) return null;
  for (const table of catalog.tables) {
    const column = table.columns.find((c) => c.column_id === widget.dimension_col_id);
    if (column) return column.business_name;
  }
  return null;
}

interface SortableCardProps {
  model: WidgetViewModel;
  index: number;
  total: number;
  gridProps: DashboardGridProps;
  isActive: boolean;
}

function SortableCard(props: SortableCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: props.model.widget.id,
    disabled: !props.gridProps.editMode,
  });

  const [liveSpan, setLiveSpan] = useState<{ colSpan: number; rowSpan: number } | null>(null);

  const colSpan = liveSpan?.colSpan ?? getWidgetColSpan(props.model.widget);
  const rowSpan = liveSpan?.rowSpan ?? getWidgetRowSpan(props.model.widget);

  const style: CSSProperties = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
    transition: liveSpan ? 'none' : transition,
    gridColumn: `span ${colSpan} / span ${colSpan}`,
    gridRow: `span ${rowSpan} / span ${rowSpan}`,
    minHeight: `${rowSpan * 40 + (rowSpan - 1) * 16}px`,
    zIndex: liveSpan ? 40 : undefined,
  };

  return (
    <li
      ref={setNodeRef}
      data-widget-id={props.model.widget.id}
      style={style}
      className={cn('list-none col-span-1 md:col-auto h-full flex flex-col', liveSpan && 'relative')}
    >
      <DashboardCard
        widget={props.model.widget}
        dbId={props.gridProps.dbId}
        globalGrain={props.gridProps.globalGrain}
        datePreset={props.gridProps.datePreset}
        refreshGeneration={props.gridProps.refreshGeneration}
        querySupported={props.gridProps.querySupported}
        editMode={props.gridProps.editMode}
        metricName={props.model.metricName}
        dimensionLabel={props.model.dimensionLabel}
        isFirst={props.index === 0}
        isLast={props.index === props.total - 1}
        isDragging={isDragging}
        dragHandleProps={{ ...attributes, ...listeners }}
        onEdit={() => props.gridProps.onEditWidget(props.model.widget)}
        onDelete={() => props.gridProps.onDeleteWidget(props.model.widget)}
        onLiveResize={(newColSpan, newRowSpan) => {
          setLiveSpan({ colSpan: newColSpan, rowSpan: newRowSpan });
        }}
        onResize={(newColSpan, newRowSpan) => {
          setLiveSpan(null);
          props.gridProps.onResizeWidget?.(props.model.widget.id, newColSpan, newRowSpan);
        }}
        onDrillDown={
          props.gridProps.onDrillDown
            ? () => props.gridProps.onDrillDown?.(props.model.widget, props.gridProps.datePreset)
            : undefined
        }
      />
    </li>
  );
}

function DragPreview({
  widget,
  models,
}: {
  widget: DashboardWidgetConfig | undefined;
  models: WidgetViewModel[];
}) {
  if (!widget) return null;
  const name = models.find((m) => m.widget.id === widget.id)?.metricName ?? widget.metric_id;
  return (
    <div className="rounded-xl border border-primary bg-card p-3 text-sm font-semibold text-foreground shadow-xl ring-2 ring-primary/40">
      {widget.custom_title ?? name}
    </div>
  );
}
