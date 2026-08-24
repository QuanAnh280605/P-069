'use client';

/**
 * Per-card data engine: builds widget requests, runs them through the bounded
 * scheduler, and exposes loading/error/success state. Stale results are
 * suppressed by comparing settled outcomes against the current request key.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import { SemanticQueryRequest, TimeGrain } from '@/lib/api';
import {
  DashboardChartType,
  DashboardDatePreset,
  DashboardWidgetConfig,
} from '@/lib/dashboard';

import {
  buildWidgetPoints,
  buildWidgetQueryRequests,
  DashboardWidgetConfigError,
  extractTotalValue,
  runWidgetExecution,
} from './dashboardQuery';
import {
  DashboardPoint,
  truncatePieSlices,
  truncateRankingRows,
} from './dashboardFormatters';

export type DashboardWidgetStatus = 'idle' | 'loading' | 'success' | 'error';

export interface DashboardWidgetData {
  status: DashboardWidgetStatus;
  points: DashboardPoint[];
  hiddenCount: number;
  totalValue: number | null;
  trendPoints: DashboardPoint[];
  errorMessage: string | null;
  isConfigurationError: boolean;
  retry: () => void;
}

export interface UseDashboardWidgetDataArgs {
  dbId: number | string;
  widget: DashboardWidgetConfig;
  globalGrain: TimeGrain | null;
  datePreset: DashboardDatePreset | null;
  refreshGeneration: number;
  enabled: boolean;
}

interface WidgetPayload {
  points: DashboardPoint[];
  hiddenCount: number;
  totalValue: number | null;
  trendPoints: DashboardPoint[];
}

type Outcome =
  | { kind: 'idle' }
  | { kind: 'pending' }
  | { kind: 'success'; payload: WidgetPayload }
  | { kind: 'error'; message: string | null; isConfiguration: boolean };

interface SettledState {
  key: string | null;
  outcome: Outcome;
}

const EMPTY_PAYLOAD: WidgetPayload = {
  points: [],
  hiddenCount: 0,
  totalValue: null,
  trendPoints: [],
};

function isTimeSeriesChart(chartType: DashboardChartType): boolean {
  return chartType === 'line' || chartType === 'area';
}

async function loadKpiPayload(
  dbId: string,
  widget: DashboardWidgetConfig,
  requests: SemanticQueryRequest[],
): Promise<WidgetPayload> {
  const [totalResult, trendResult] = await Promise.all([
    runWidgetExecution(dbId, requests[0]),
    runWidgetExecution(dbId, requests[1]),
  ]);
  return {
    points: [],
    hiddenCount: 0,
    totalValue: extractTotalValue(totalResult, widget.metric_id),
    trendPoints: buildWidgetPoints({
      result: trendResult,
      metricId: widget.metric_id,
      dimensionId: widget.date_filter_column_id,
      sortByTime: true,
    }),
  };
}

async function loadSeriesPayload(
  dbId: string,
  widget: DashboardWidgetConfig,
  request: SemanticQueryRequest,
): Promise<WidgetPayload> {
  const result = await runWidgetExecution(dbId, request);
  const points = buildWidgetPoints({
    result,
    metricId: widget.metric_id,
    dimensionId: widget.dimension_col_id,
    sortByTime: isTimeSeriesChart(widget.chart_type),
  });
  if (widget.chart_type === 'pie') {
    const sliced = truncatePieSlices(points);
    return { ...EMPTY_PAYLOAD, points: sliced, hiddenCount: points.length - sliced.length };
  }
  if (widget.chart_type === 'table') {
    const ranked = truncateRankingRows(points);
    return { ...EMPTY_PAYLOAD, points: ranked.rows, hiddenCount: ranked.hiddenCount };
  }
  return { ...EMPTY_PAYLOAD, points };
}

async function loadWidgetPayload(
  dbId: string,
  widget: DashboardWidgetConfig,
  globalGrain: TimeGrain | null,
  datePreset: DashboardDatePreset | null,
): Promise<WidgetPayload> {
  const requests = buildWidgetQueryRequests({ widget, globalGrain, datePreset });
  if (widget.chart_type === 'kpi') return loadKpiPayload(dbId, widget, requests);
  return loadSeriesPayload(dbId, widget, requests[0]);
}

const widgetPayloadCache = new Map<string, { expiresAt: number; payload: WidgetPayload }>();
const inFlightPayloads = new Map<string, Promise<WidgetPayload>>();
const PAYLOAD_CACHE_TTL_MS = 120_000; // 2 minutes

export function clearDashboardPayloadCache(): void {
  widgetPayloadCache.clear();
  inFlightPayloads.clear();
}

function resolveOutcome(enabled: boolean, settled: SettledState, requestKey: string): Outcome {
  if (!enabled) return { kind: 'idle' };
  if (settled.key === requestKey) return settled.outcome;
  return { kind: 'pending' };
}

/** Hook driving one dashboard card's query lifecycle. */
export function useDashboardWidgetData(args: UseDashboardWidgetDataArgs): DashboardWidgetData {
  const { dbId, widget, globalGrain, datePreset, refreshGeneration, enabled } = args;
  const [attempt, setAttempt] = useState(0);

  // Key strictly depends on query parameters, avoiding re-query on resize, reorder, or title edits
  const requestKey = useMemo(
    () =>
      JSON.stringify([
        dbId,
        widget.metric_id,
        widget.dimension_col_id,
        widget.date_filter_column_id,
        widget.time_grain,
        widget.chart_type,
        globalGrain,
        datePreset,
        refreshGeneration,
        attempt,
      ]),
    [
      dbId,
      widget.metric_id,
      widget.dimension_col_id,
      widget.date_filter_column_id,
      widget.time_grain,
      widget.chart_type,
      globalGrain,
      datePreset,
      refreshGeneration,
      attempt,
    ],
  );

  // Instant response if already cached in memory
  const [settled, setSettled] = useState<SettledState>(() => {
    const cached = widgetPayloadCache.get(requestKey);
    if (cached && cached.expiresAt > Date.now()) {
      return { key: requestKey, outcome: { kind: 'success', payload: cached.payload } };
    }
    return { key: null, outcome: { kind: 'idle' } };
  });

  useEffect(() => {
    if (!enabled) return;

    const cached = widgetPayloadCache.get(requestKey);
    if (cached && cached.expiresAt > Date.now()) {
      setSettled({ key: requestKey, outcome: { kind: 'success', payload: cached.payload } });
      return;
    }

    let cancelled = false;

    // Deduplicate in-flight requests for identical queries
    let inFlight = inFlightPayloads.get(requestKey);
    if (!inFlight) {
      inFlight = loadWidgetPayload(String(dbId), widget, globalGrain, datePreset)
        .then((payload) => {
          widgetPayloadCache.set(requestKey, {
            expiresAt: Date.now() + PAYLOAD_CACHE_TTL_MS,
            payload,
          });
          return payload;
        })
        .finally(() => {
          inFlightPayloads.delete(requestKey);
        });
      inFlightPayloads.set(requestKey, inFlight);
    }

    inFlight.then(
      (payload) => {
        if (!cancelled) setSettled({ key: requestKey, outcome: { kind: 'success', payload } });
      },
      (error: unknown) => {
        if (!cancelled) setSettled({ key: requestKey, outcome: describeOutcome(error) });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [
    requestKey,
    enabled,
    dbId,
    widget.metric_id,
    widget.dimension_col_id,
    widget.date_filter_column_id,
    widget.time_grain,
    widget.chart_type,
    globalGrain,
    datePreset,
  ]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return outcomeToData(resolveOutcome(enabled, settled, requestKey), retry);
}

function describeOutcome(error: unknown): Outcome {
  return {
    kind: 'error',
    message: error instanceof Error ? error.message : String(error),
    isConfiguration: error instanceof DashboardWidgetConfigError,
  };
}

const IDLE_EXTRA = { errorMessage: null, isConfigurationError: false };

function outcomeToData(outcome: Outcome, retry: () => void): DashboardWidgetData {
  if (outcome.kind === 'idle') {
    return { status: 'idle', ...EMPTY_PAYLOAD, ...IDLE_EXTRA, retry };
  }
  if (outcome.kind === 'error') {
    return {
      status: 'error',
      ...EMPTY_PAYLOAD,
      errorMessage: outcome.message,
      isConfigurationError: outcome.isConfiguration,
      retry,
    };
  }
  if (outcome.kind === 'success') {
    return { status: 'success', ...outcome.payload, ...IDLE_EXTRA, retry };
  }
  return { status: 'loading', ...EMPTY_PAYLOAD, ...IDLE_EXTRA, retry };
}
