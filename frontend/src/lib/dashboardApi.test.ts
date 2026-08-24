import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SemanticApiError } from '@/lib/api';
import { DashboardLayoutParseError, DashboardWidgetConfig } from '@/lib/dashboard';
import {
  DashboardVersionConflictError,
  loadDashboardApi,
  saveDashboardApi,
} from '@/lib/dashboardApi';

const savedLine: DashboardWidgetConfig = {
  id: 'w-line',
  metric_id: 2,
  dimension_col_id: 12,
  date_filter_column_id: 12,
  time_grain: 'month',
  chart_type: 'line',
  width: 'half',
  height: 'normal',
  custom_title: null,
};

const savedPayload = {
  db_id: 5,
  version: 3,
  updated_at: '2026-08-20T10:00:00Z',
  updated_by: 7,
  layout: { widgets: [savedLine] },
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('dashboard singleton API client', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token');
    localStorage.setItem('current_organization_id', '42');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  describe('loadDashboardApi', () => {
    it('GETs the singleton endpoint with auth and org headers', async () => {
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, savedPayload));
      vi.stubGlobal('fetch', fetchMock);

      const state = await loadDashboardApi(5);

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, init] = fetchMock.mock.calls[0];
      expect(String(url)).toMatch(/\/api\/v1\/semantic\/5\/dashboard$/);
      expect((init as RequestInit).method).toBeUndefined();
      const headers = (init as RequestInit).headers as Record<string, string>;
      expect(headers.Authorization).toBe('Bearer test-token');
      expect(headers['X-Organization-ID']).toBe('42');
      expect(state.db_id).toBe(5);
      expect(state.version).toBe(3);
      expect(state.layout).toEqual({ widgets: [savedLine] });
    });

    it('returns the uninitialized empty state with a null layout', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse(200, {
            db_id: 5,
            layout: null,
            version: 0,
            updated_at: null,
            updated_by: null,
          }),
        ),
      );

      const state = await loadDashboardApi('5');

      expect(state.layout).toBeNull();
      expect(state.version).toBe(0);
    });

    it('surfaces malformed backend layouts as a recoverable parse error', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse(200, {
            db_id: 5,
            version: 2,
            updated_at: null,
            updated_by: null,
            layout: { widgets: [{ id: 'broken' }] },
          }),
        ),
      );

      await expect(loadDashboardApi(5)).rejects.toThrow(DashboardLayoutParseError);
    });

    it('propagates masked authorization failures as SemanticApiError', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'Semantic database not found' })),
      );

      await expect(loadDashboardApi(5)).rejects.toEqual(
        new SemanticApiError(404, 'Semantic database not found', 'Semantic database not found'),
      );
    });
  });

  describe('saveDashboardApi', () => {
    it('PUTs the layout with the expected version using JSON conventions', async () => {
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, savedPayload));
      vi.stubGlobal('fetch', fetchMock);

      const state = await saveDashboardApi(5, { widgets: [savedLine] }, 3);

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, init] = fetchMock.mock.calls[0];
      expect(String(url)).toMatch(/\/api\/v1\/semantic\/5\/dashboard$/);
      expect((init as RequestInit).method).toBe('PUT');
      const headers = (init as RequestInit).headers as Record<string, string>;
      expect(headers['Content-Type']).toBe('application/json');
      expect(headers.Authorization).toBe('Bearer test-token');
      expect(headers['X-Organization-ID']).toBe('42');
      expect(JSON.parse(String((init as RequestInit).body))).toEqual({
        layout: { widgets: [savedLine] },
        expected_version: 3,
      });
      expect(state.version).toBe(3);
    });

    it('maps the stable lowercase 409 conflict contract to a typed error', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse(409, {
            detail: { code: 'dashboard_version_conflict', current_version: 4 },
          }),
        ),
      );

      const failure = await saveDashboardApi(5, { widgets: [savedLine] }, 3).catch(
        (error: unknown) => error,
      );

      expect(failure).toBeInstanceOf(DashboardVersionConflictError);
      const conflict = failure as DashboardVersionConflictError;
      expect(conflict.currentVersion).toBe(4);
      expect(conflict).not.toBeInstanceOf(SemanticApiError);
    });

    it('keeps unrelated 409 payloads as SemanticApiError', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse(409, { detail: { code: 'other_conflict', current_version: 9 } }),
        ),
      );

      await expect(saveDashboardApi(5, { widgets: [savedLine] }, 3)).rejects.toThrow(
        SemanticApiError,
      );
    });

    it('surfaces invalid-layout rejections without swallowing details', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse(422, {
            detail: { code: 'dashboard_invalid_layout', message: 'Widget IDs must be unique' },
          }),
        ),
      );

      try {
        await saveDashboardApi(5, { widgets: [] }, 0);
        throw new Error('expected save to fail');
      } catch (error) {
        expect(error).toBeInstanceOf(SemanticApiError);
        const apiError = error as SemanticApiError;
        expect(apiError.status).toBe(422);
        expect(apiError.message).toContain('dashboard_invalid_layout');
        expect(apiError.message).toContain('Widget IDs must be unique');
      }
    });

    it('propagates masked authorization failures on save', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'Semantic database not found' })),
      );

      await expect(saveDashboardApi(5, { widgets: [savedLine] }, 1)).rejects.toEqual(
        new SemanticApiError(404, 'Semantic database not found', 'Semantic database not found'),
      );
    });
  });
});
