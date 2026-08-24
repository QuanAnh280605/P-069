import { SemanticApiError, semanticRequest } from '@/lib/api';
import { DashboardLayout, DashboardLayoutState, parseDashboardLayoutPayload } from '@/lib/dashboard';

const DASHBOARD_VERSION_CONFLICT_CODE = 'dashboard_version_conflict';

interface DashboardConflictDetail {
  code?: unknown;
  current_version?: unknown;
}

export class DashboardVersionConflictError extends Error {
  constructor(public readonly currentVersion: number) {
    super(`Dashboard layout is stale; the server holds version ${currentVersion}.`);
    this.name = 'DashboardVersionConflictError';
  }
}

export async function loadDashboardApi(dbId: number | string): Promise<DashboardLayoutState> {
  const payload = await semanticRequest<unknown>(`/api/v1/semantic/${dbId}/dashboard`);
  return parseDashboardLayoutPayload(payload);
}

export async function saveDashboardApi(
  dbId: number | string,
  layout: DashboardLayout,
  expectedVersion: number,
): Promise<DashboardLayoutState> {
  let payload: unknown;
  try {
    payload = await semanticRequest<unknown>(`/api/v1/semantic/${dbId}/dashboard`, {
      method: 'PUT',
      body: JSON.stringify({ layout, expected_version: expectedVersion }),
    });
  } catch (error) {
    throw mapDashboardSaveError(error);
  }
  return parseDashboardLayoutPayload(payload);
}

function mapDashboardSaveError(error: unknown): unknown {
  if (!(error instanceof SemanticApiError) || error.status !== 409) return error;
  const detail = error.detail as DashboardConflictDetail | null;
  if (!detail || detail.code !== DASHBOARD_VERSION_CONFLICT_CODE) return error;
  const currentVersion = detail.current_version;
  if (typeof currentVersion !== 'number' || !Number.isInteger(currentVersion) || currentVersion < 0) {
    return error;
  }
  return new DashboardVersionConflictError(currentVersion);
}
