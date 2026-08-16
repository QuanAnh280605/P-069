import { semanticRequest } from '@/lib/api';
import type {
  InterpretQueryInput,
  InterpretQueryOutcome,
  SavedQueryShare,
  SavedSemanticQuery,
  SemanticQueryRequest,
} from '@/lib/semantic-query';

export async function interpretSemanticQueryApi(
  dbId: string,
  input: InterpretQueryInput,
  signal?: AbortSignal,
): Promise<InterpretQueryOutcome> {
  return semanticRequest<InterpretQueryOutcome>(`/api/v1/semantic/${dbId}/query/interpret`, {
    method: 'POST',
    body: JSON.stringify({
      text: input.text,
      timezone: input.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
      selections: input.selections || {},
    }),
    signal,
  });
}

export async function listSavedQueriesApi(dbId: string): Promise<SavedSemanticQuery[]> {
  return semanticRequest<SavedSemanticQuery[]>(`/api/v1/semantic/${dbId}/saved-queries`);
}

export async function createSavedQueryApi(
  dbId: string,
  name: string,
  spec: SemanticQueryRequest,
): Promise<SavedSemanticQuery> {
  return semanticRequest<SavedSemanticQuery>(`/api/v1/semantic/${dbId}/saved-queries`, {
    method: 'POST',
    body: JSON.stringify({ name, spec }),
  });
}

export async function shareSavedQueryApi(queryId: number): Promise<SavedQueryShare> {
  return semanticRequest<SavedQueryShare>(`/api/v1/semantic/saved-queries/${queryId}/share`, {
    method: 'POST',
    body: JSON.stringify({ expires_in_days: 7 }),
  });
}

export async function resolveSharedQueryApi(token: string): Promise<SavedSemanticQuery> {
  return semanticRequest<SavedSemanticQuery>(
    `/api/v1/semantic/shared-queries/${encodeURIComponent(token)}`,
  );
}
