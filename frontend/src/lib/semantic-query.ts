export type FilterOperator =
  | 'eq'
  | 'neq'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'in'
  | 'not_in'
  | 'is_null'
  | 'is_not_null';

export type TimeGrain = 'day' | 'week' | 'month' | 'quarter' | 'year';

export interface CatalogColumn {
  column_id: number;
  column_name: string;
  business_name: string;
  data_type: string;
  is_time_dimension: boolean;
  allowed_values: unknown;
}

export interface CatalogTable {
  table_id: number;
  table_name: string;
  business_name: string;
  columns: CatalogColumn[];
}

export interface SemanticCatalog {
  db_id: number;
  source_type: 'live' | 'sql_dump';
  query_supported: boolean;
  hybrid_query_enabled?: boolean;
  saved_queries_enabled?: boolean;
  tables: CatalogTable[];
  relationships: Array<{ from_entity_id: number; to_entity_id: number }>;
}

export interface SemanticQueryFilter {
  column_id: number;
  operator: FilterOperator;
  value: unknown;
}

export interface DimensionSelection {
  column_id: number;
  time_grain?: TimeGrain | null;
}

export interface SemanticQueryRequest {
  metric_ids: number[];
  dimensions: DimensionSelection[];
  filters: SemanticQueryFilter[];
  limit: number;
}

export interface QueryLineageMetric {
  metric_id: number;
  name: string;
  version: number;
  formula: string;
  base_entity: string;
  approved_by?: string | null;
  verified: boolean;
}

export interface QueryLineage {
  metrics: QueryLineageMetric[];
  source_tables: string[];
}

export interface SemanticQueryPreview {
  sql: string;
  parameters: Record<string, unknown>;
  metadata: Record<string, unknown>;
  diagnostics: Array<{ code: string; message: string }>;
  lineage?: QueryLineage;
}

export interface SemanticQueryResult {
  sql: string;
  parameters: Record<string, unknown>;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  lineage?: QueryLineage;
}

export interface ClarificationOption {
  value: string | number;
  label: string;
  description: string;
  semantic_id?: number | null;
  option_id?: string | null;
}

export interface SemanticToken {
  token_id: string;
  kind: 'metric' | 'dimension' | 'time' | 'filter';
  label: string;
  semantic_id?: number | null;
  confidence_bucket: 'deterministic' | 'high' | 'review';
  editable: boolean;
}

export interface SemanticQueryDraft {
  spec: SemanticQueryRequest | null;
  tokens: SemanticToken[];
  assumptions: string[];
  unresolved_mentions: string[];
}

export interface ClarificationDecision {
  decision_id: string;
  code: string;
  slot: 'metric' | 'dimension_role' | 'filter_value' | 'time_column' | 'time_range' | 'time_grain';
  prompt: string;
  options: ClarificationOption[];
  recommended_option_id?: string | null;
  required: boolean;
  allow_free_text: boolean;
  depends_on: string[];
}

export interface ReadyInterpretation {
  status: 'ready';
  draft: SemanticQueryDraft;
  summary: string;
  diagnostics: Array<{ code: string; message: string }>;
}

export interface NeedsConfirmation {
  status: 'needs_confirmation';
  draft: SemanticQueryDraft;
  decisions: ClarificationDecision[];
}

export interface UnsupportedInterpretation {
  status: 'unsupported';
  code: string;
  message: string;
  draft?: SemanticQueryDraft | null;
}

export type InterpretQueryOutcome =
  | ReadyInterpretation
  | NeedsConfirmation
  | UnsupportedInterpretation;

export interface InterpretQueryInput {
  text: string;
  timezone?: string;
  selections?: Record<string, string>;
}

export interface SavedSemanticQuery {
  id: number;
  owner_id: number;
  db_id: number;
  name: string;
  spec: SemanticQueryRequest;
  metric_versions: Record<string, number>;
  revision: number;
  share_enabled: boolean;
  share_expires_at?: string | null;
  stale: boolean;
  created_at: string;
  updated_at: string;
}

export interface SavedQueryShare {
  token: string;
  path: string;
  expires_at: string;
  scope: 'owner';
}
