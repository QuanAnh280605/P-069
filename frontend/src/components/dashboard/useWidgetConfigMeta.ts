'use client';

/**
 * Loads recommended dimensions and safe filter columns for the currently
 * selected metric. Results are tagged with the metric id so stale responses
 * can never be applied to a different metric.
 */

import { useEffect, useState } from 'react';

import {
  getMetricFilterColumnsApi,
  getMetricRecommendedDimensionsApi,
} from '@/lib/api';

import { WidgetMeta } from './widgetConfigForm';

interface MetaFailure {
  metricId: number;
  message: string;
}

export interface UseWidgetMetaResult {
  currentMeta: WidgetMeta | null;
  errorMessage: string | null;
  loading: boolean;
}

/** Load recommended dimensions plus filter columns for the chosen metric. */
export function useWidgetConfigMeta(
  metricId: number | null,
  dbId: number | string,
  onLoaded: (meta: WidgetMeta) => void,
): UseWidgetMetaResult {
  const [meta, setMeta] = useState<WidgetMeta | null>(null);
  const [failure, setFailure] = useState<MetaFailure | null>(null);

  useEffect(() => {
    if (metricId === null) return;
    let cancelled = false;
    Promise.all([
      getMetricRecommendedDimensionsApi(dbId, metricId),
      getMetricFilterColumnsApi(dbId, metricId),
    ]).then(([dimensionsResponse, columnsResponse]) => {
      if (cancelled) return;
      if (dimensionsResponse.metric_id !== metricId || columnsResponse.metric_id !== metricId) return;
      const next: WidgetMeta = {
        metricId,
        dimensions: dimensionsResponse.dimensions,
        columns: columnsResponse.columns,
      };
      setMeta(next);
      setFailure(null);
      onLoaded(next);
    }).catch(() => {
      if (!cancelled) setFailure({ metricId, message: 'Không thể tải danh sách chiều dữ liệu cho metric này.' });
    });
    return () => {
      cancelled = true;
    };
  }, [dbId, metricId, onLoaded]);

  const currentMeta = meta && meta.metricId === metricId ? meta : null;
  const errorMessage = failure && failure.metricId === metricId ? failure.message : null;
  const loading = metricId !== null && currentMeta === null && errorMessage === null;
  return { currentMeta, errorMessage, loading };
}
