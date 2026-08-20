import { getStoredToken } from '@/lib/jwt';

export interface SemanticColumn {
  column_name: string;
  data_type: string;
  business_name: string;
  description?: string;
  sample_value?: string;
}
export interface SemanticTable {
  table_name: string;
  business_name: string;
  description: string;
  columns: SemanticColumn[];
}

export type MetricFunction = 'SUM' | 'COUNT' | 'COUNT_DISTINCT' | 'AVG' | 'MIN' | 'MAX';
export type MetricStatus = 'pending_approval' | 'approved' | 'needs_review';
export type MetricConfidence = 'low' | 'medium' | 'high';
export type FilterOperator = 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'not_in' | 'is_null' | 'is_not_null';

export interface MetricFilter {
  field: string;
  column_id?: number | null;
  operator: FilterOperator;
  value: unknown;
}

export interface MetricDefinition {
  schema_version?: 1 | 2;
  metric: {
    name: string;
    formula: { function: MetricFunction; expression: string };
    base_entity: string;
    base_entity_id?: number | null;
    grain?: { column_ids: number[] };
    filters: MetricFilter[];
    status: MetricStatus;
    confidence?: MetricConfidence | null;
    excluded_notes: string;
  };
  diagnostics?: Array<{ code: string; message: string }>;
}

export interface MetricRecord {
  metric_id: number;
  db_id?: number;
  name: string;
  description?: string;
  sql_template?: string;
  definition: MetricDefinition | null;
  source: 'ai' | 'manual';
  version?: number;
  status: MetricStatus;
  approved_by?: number | null;
  created_by?: number | null;
  created_at: string;
  updated_at?: string;
}

export interface SemanticLayerData {
  id: string;
  db_name: string;
  db_type: 'postgresql' | 'mysql' | 'sqlite' | 'auto';
  conn_url?: string;
  status: 'Draft' | 'Saved';
  updated_at: string;
  tables: SemanticTable[];
  semantic_db_id?: number | null;
  source_type?: 'live' | 'sql_dump';
  metrics: MetricRecord[];
  table_count?: number;
  is_loaded?: boolean;
}

export interface MetricConflictInfo {
  proposed_metric_name: string;
  existing_metric_id: number | null;
  existing_metric_name: string;
  existing_metric_status: string | null;
  suggested_name: string;
  clarify_question: string;
}

export interface DuplicateMetricNotice {
  existing_metric_id: number | null;
  existing_metric_name: string;
  existing_metric_status: string | null;
  user_message: string;
  similarity_reason: string;
  existing_definition?: MetricDefinition | null;
  existing_yaml?: string;
}

export interface MetricSuggestion {
  definition: MetricDefinition;
  yaml_preview: string;
  conflict?: MetricConflictInfo | null;
}

export interface MetricVersion {
  version: number;
  definition: MetricDefinition | null;
  changed_by?: number | null;
  change_reason: string;
  created_at: string;
}

export interface MetricHistory {
  metric_id: number;
  metric_name: string;
  versions: MetricVersion[];
}

export interface CatalogColumn {
  column_id: number;
  column_name: string;
  business_name: string;
  data_type: string;
  is_time_dimension: boolean;
  is_primary_key?: boolean;
  is_foreign_key?: boolean;
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
  tables: CatalogTable[];
  relationships: Array<{ from_entity_id: number; to_entity_id: number }>;
}

export interface SemanticQueryFilter {
  column_id: number;
  operator: FilterOperator;
  value: unknown;
}

export interface SemanticQueryRequest {
  metric_ids: number[];
  dimensions?: DimensionSelection[];
  dimension_ids?: number[];
  filters: SemanticQueryFilter[];
  limit: number;
}

export type TimeGrain = 'day' | 'week' | 'month' | 'quarter' | 'year';

export interface DimensionSelection {
  column_id: number;
  time_grain?: TimeGrain | null;
}

export interface SemanticQueryPreview {
  sql: string;
  parameters: Record<string, unknown>;
  metadata: Record<string, unknown>;
  diagnostics: Array<{ code: string; message: string }>;
}

export interface SemanticQueryResult {
  sql: string;
  parameters: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms?: number;
}

const LEGACY_INITIAL_LAYERS: unknown[] = [
  {
    id: 'db-ecommerce-prod',
    db_name: 'E-Commerce Production Database',
    db_type: 'postgresql',
    status: 'Saved',
    updated_at: '2026-07-31 10:00',
    tables: [
      {
        table_name: 'orders',
        business_name: 'Đơn hàng',
        description: 'Bảng chứa thông tin lịch sử mua hàng của KH',
        columns: [
          { column_name: 'order_id', data_type: 'INTEGER (PK)', business_name: 'Mã đơn hàng', sample_value: '1001' },
          { column_name: 'customer_id', data_type: 'INTEGER (FK→customers)', business_name: 'Mã khách hàng', sample_value: 'C-88' },
          { column_name: 'total_amount', data_type: 'NUMERIC', business_name: 'Tổng tiền đơn hàng', sample_value: '450,000' },
          { column_name: 'order_status', data_type: 'VARCHAR(20)', business_name: 'Trạng thái đơn', sample_value: 'COMPLETED' },
          { column_name: 'created_at', data_type: 'TIMESTAMP', business_name: 'Ngày tạo đơn', sample_value: '2026-07-31' },
        ],
      },
      {
        table_name: 'customers',
        business_name: 'Khách hàng',
        description: 'Bảng chứa danh sách người dùng đăng ký',
        columns: [
          { column_name: 'customer_id', data_type: 'INTEGER (PK)', business_name: 'Mã khách hàng', sample_value: 'C-88' },
          { column_name: 'full_name', data_type: 'VARCHAR(100)', business_name: 'Họ và tên', sample_value: 'Nguyễn Văn A' },
          { column_name: 'email', data_type: 'VARCHAR(150)', business_name: 'Địa chỉ email', sample_value: 'user@example.com' },
          { column_name: 'created_at', data_type: 'TIMESTAMP', business_name: 'Ngày gia nhập', sample_value: '2026-01-15' },
        ],
      },
    ],
    metrics: [
      {
        id: 'm1',
        name: 'Doanh thu theo ngày',
        description: 'Tổng doanh thu phân nhóm theo ngày tạo đơn hàng',
        sql_template: `SELECT DATE(created_at), SUM(total_amount) FROM orders\nWHERE order_status = 'COMPLETED' GROUP BY 1 ORDER BY 1`,
        source: 'ai',
      },
      {
        id: 'm2',
        name: 'Số lượng đơn hàng theo trạng thái',
        description: 'Đếm số đơn phân nhóm theo trạng thái xử lý',
        sql_template: `SELECT order_status, COUNT(*) FROM orders GROUP BY order_status`,
        source: 'ai',
      },
      {
        id: 'm3',
        name: 'Tỷ lệ đơn hàng hoàn thành (Completion Rate)',
        description: '% đơn hàng có status COMPLETED / tổng đơn hàng',
        sql_template: `SELECT ROUND(\n  COUNT(*) FILTER(WHERE order_status='COMPLETED') * 100.0\n  / COUNT(*), 2) AS completion_rate FROM orders`,
        source: 'manual',
      },
    ],
  },
  {
    id: 'db-retail-sales',
    db_name: 'Retail Sales SQLite',
    db_type: 'sqlite',
    status: 'Draft',
    updated_at: '2026-07-30 14:20',
    tables: [
      {
        table_name: 'sales_transactions',
        business_name: 'Giao dịch bán lẻ',
        description: 'Bảng ghi nhận hóa đơn bán lẻ tại cửa hàng',
        columns: [
          { column_name: 'txn_id', data_type: 'INTEGER (PK)', business_name: 'Mã giao dịch', sample_value: 'TXN-9021' },
          { column_name: 'store_id', data_type: 'INTEGER', business_name: 'Mã chi nhánh', sample_value: 'ST-01' },
          { column_name: 'amount', data_type: 'REAL', business_name: 'Giá trị hóa đơn', sample_value: '120,000' },
        ],
      },
    ],
    metrics: [
      {
        id: 'm4',
        name: 'Tổng doanh số chi nhánh',
        description: 'Tính tổng tiền bán hàng theo chi nhánh',
        sql_template: `SELECT store_id, SUM(amount) FROM sales_transactions GROUP BY store_id`,
        source: 'ai',
      },
    ],
  },
];

void LEGACY_INITIAL_LAYERS;
const INITIAL_LAYERS: SemanticLayerData[] = [];

export function getLocalLayers(): SemanticLayerData[] {
  if (typeof window === 'undefined') return INITIAL_LAYERS;
  const stored = localStorage.getItem('semantic_layers_store');
  if (!stored) {
    localStorage.setItem('semantic_layers_store', JSON.stringify(INITIAL_LAYERS));
    return INITIAL_LAYERS;
  }
  try {
    return JSON.parse(stored);
  } catch {
    return INITIAL_LAYERS;
  }
}

export function saveLocalLayers(layers: SemanticLayerData[]): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('semantic_layers_store', JSON.stringify(layers));
}

export function getLayerById(id: string): SemanticLayerData | undefined {
  const layers = getLocalLayers();
  return layers.find((l) => l.id === id);
}

export function updateLayer(updated: SemanticLayerData): void {
  const layers = getLocalLayers();
  const index = layers.findIndex((l) => l.id === updated.id);
  if (index !== -1) {
    layers[index] = updated;
  } else {
    layers.unshift(updated);
  }
  saveLocalLayers(layers);
}

export function deleteLayer(id: string): void {
  const layers = getLocalLayers();
  const filtered = layers.filter((l) => l.id !== id);
  saveLocalLayers(filtered);
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000';
const API_BASE = API_BASE_URL;

export type WorkspaceRole = 'data_lead' | 'member';

export interface WorkspaceSummary {
  id: number;
  name: string;
  slug: string;
  role: WorkspaceRole;
  permissions: Record<string, boolean>;
  created_at: string;
}

export interface WorkspaceMember {
  user_id: number;
  email: string;
  username: string;
  full_name: string;
  role: WorkspaceRole;
  joined_at: string;
}

export interface WorkspaceInvite {
  id: number;
  org_id: number;
  role: 'member' | 'data_lead';
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
  expires_at: string;
  invite_url?: string | null;
}

export interface WorkspaceInvitePreview {
  organization_name: string;
  organization_slug: string;
  role: 'member' | 'data_lead';
  expires_at: string;
}

function getWorkspaceHeader(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const id = window.localStorage.getItem('current_organization_id');
  return id ? { 'X-Organization-ID': id } : {};
}

function getAuthHeader(): Record<string, string> {
  const token =
    getStoredToken() ||
    (typeof window !== 'undefined' ? localStorage.getItem('access_token') || localStorage.getItem('token') : null);
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...getWorkspaceHeader(),
  };
}

export function listWorkspacesApi(): Promise<WorkspaceSummary[]> {
  return semanticRequest<WorkspaceSummary[]>('/api/v1/org/my-orgs');
}

export function getCurrentWorkspaceApi(): Promise<WorkspaceSummary> {
  return semanticRequest<WorkspaceSummary>('/api/v1/org/current');
}

export function createWorkspaceApi(name: string, slug?: string): Promise<WorkspaceSummary> {
  return semanticRequest<WorkspaceSummary>('/api/v1/org', {
    method: 'POST',
    body: JSON.stringify({ name, slug }),
  });
}

export function listWorkspaceMembersApi(): Promise<WorkspaceMember[]> {
  return semanticRequest<WorkspaceMember[]>('/api/v1/org/members');
}

export function updateWorkspaceMemberApi(userId: number, role: WorkspaceRole): Promise<void> {
  return semanticRequest<void>(`/api/v1/org/members/${userId}`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  });
}

export function removeWorkspaceMemberApi(userId: number): Promise<void> {
  return semanticRequest<void>(`/api/v1/org/members/${userId}`, { method: 'DELETE' });
}

export function createWorkspaceInviteApi(
  role: 'member' | 'data_lead',
): Promise<WorkspaceInvite> {
  return semanticRequest<WorkspaceInvite>('/api/v1/org/invite', {
    method: 'POST',
    body: JSON.stringify({ role }),
  });
}

export function revokeWorkspaceInviteApi(invitationId: number): Promise<void> {
  return semanticRequest<void>(`/api/v1/org/invite/${invitationId}`, { method: 'DELETE' });
}

export function listWorkspaceInvitesApi(): Promise<WorkspaceInvite[]> {
  return semanticRequest<WorkspaceInvite[]>('/api/v1/org/invites');
}

export function previewWorkspaceInviteApi(token: string): Promise<WorkspaceInvitePreview> {
  return semanticRequest<WorkspaceInvitePreview>(`/api/v1/invite/${token}`);
}

export function acceptWorkspaceInviteApi(token: string): Promise<WorkspaceSummary> {
  return semanticRequest<WorkspaceSummary>(`/api/v1/invite/${token}/accept`, { method: 'POST' });
}

export class SemanticApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'SemanticApiError';
  }
}

export const METRIC_WRITE_PERMISSION_MESSAGE =
  'Bạn không có quyền lưu hoặc chỉnh sửa metric. Chỉ Data Lead được thực hiện thao tác này.';

export function isPermissionDenied(error: unknown): boolean {
  return error instanceof SemanticApiError && error.status === 403;
}

export async function semanticRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...getAuthHeader(),
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) throw new SemanticApiError(response.status, await semanticError(response));
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function semanticError(response: Response): Promise<string> {
  const payload = await response.json().catch(() => null) as { detail?: unknown } | null;
  if (typeof payload?.detail === 'string') return payload.detail;
  return payload?.detail ? JSON.stringify(payload.detail) : `Request failed (${response.status})`;
}

function metricResponseToRecord(data: {
  metric_id: number;
  definition: MetricDefinition;
  source: 'ai' | 'manual';
}): MetricRecord {
  return {
    ...data,
    name: data.definition.metric.name,
    version: 1,
    status: data.definition.metric.status,
    created_at: new Date().toISOString(),
  };
}

export interface GeneratedMetricsResult {
  suggestions: MetricSuggestion[];
  duplicates: DuplicateMetricNotice[];
  dedupe_performed: boolean;
  isLiveLLM: boolean;
}

export async function generateCustomMetricsApi(
  dbId: string,
  prompt: string,
  targetTables: string[] = [],
): Promise<GeneratedMetricsResult> {
  const res = await fetch(`${API_BASE}/api/v1/semantic/${dbId}/metrics/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ prompt, target_tables: targetTables.length ? targetTables : null }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Lỗi khi gọi API Backend' }));
    const errorMsg =
      typeof errData?.detail === 'string'
        ? errData.detail
        : JSON.stringify(errData?.detail || 'Không thể sinh metric từ LLM Backend');
    throw new Error(`[Backend LLM Error ${res.status}]: ${errorMsg}`);
  }

  const data = await res.json();
  const suggestions: MetricSuggestion[] = data.suggestions || [];
  const duplicates: DuplicateMetricNotice[] = data.duplicates || [];
  // Duplicates-only is a successful result (all proposals matched saved metrics).
  if (suggestions.length === 0 && duplicates.length === 0) {
    throw new Error('LLM không tìm thấy hoặc không sinh được chỉ số phù hợp với schema');
  }
  return { suggestions, duplicates, dedupe_performed: data.dedupe_performed !== false, isLiveLLM: true };
}

export interface ChatOrchestratorResponse {
  intent: 'chitchat' | 'data_question' | 'metric_query';
  chat_response?: string | null;
  suggestions?: MetricSuggestion[] | null;
  duplicates?: DuplicateMetricNotice[];
  dedupe_performed?: boolean;
  session_id: string;
  user_message_id: string;
  assistant_message_id: string;
  session?: ChatSessionItem | null;
}

export interface ChatSessionItem {
  id: string;
  db_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessageItem {
  id: string;
  session_id: string;
  client_message_id?: string | null;
  sequence_no: number;
  sender: 'user' | 'assistant' | 'system';
  content: string;
  intent?: string | null;
  metadata_json?: {
    schema_version?: number;
    status?: 'pending' | 'completed' | 'error';
    suggestions?: MetricSuggestion[];
    duplicates?: DuplicateMetricNotice[];
    dedupe_performed?: boolean;
    error?: string | null;
  } | null;
  created_at: string;
}

export interface ChatSessionDetail extends ChatSessionItem {
  messages: ChatMessageItem[];
  next_before_sequence?: number | null;
}

async function chatRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...getAuthHeader(), ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Lỗi khi gọi API Chat' }));
    throw new Error(typeof errData?.detail === 'string' ? errData.detail : 'Không thể xử lý yêu cầu chat');
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function listChatSessionsApi(dbId: string): Promise<ChatSessionItem[]> {
  return chatRequest<ChatSessionItem[]>(`${API_BASE}/api/v1/semantic/${dbId}/chat/sessions`);
}

export async function getChatSessionDetailApi(
  dbId: string,
  sessionId: string,
  beforeSequence?: number,
): Promise<ChatSessionDetail> {
  const cursor = beforeSequence ? `?limit=100&before_sequence=${beforeSequence}` : '?limit=100';
  return chatRequest<ChatSessionDetail>(`${API_BASE}/api/v1/semantic/${dbId}/chat/sessions/${sessionId}${cursor}`);
}

export async function deleteChatSessionApi(dbId: string, sessionId: string): Promise<void> {
  await chatRequest<void>(`${API_BASE}/api/v1/semantic/${dbId}/chat/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function updateChatSessionTitleApi(
  dbId: string,
  sessionId: string,
  title: string,
): Promise<ChatSessionItem> {
  return chatRequest<ChatSessionItem>(`${API_BASE}/api/v1/semantic/${dbId}/chat/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
}

export async function sendChatOrchestratorApi(
  dbId: string,
  message: string,
  sessionId?: string | null,
  clientMessageId?: string,
): Promise<ChatOrchestratorResponse> {
  return chatRequest<ChatOrchestratorResponse>(`${API_BASE}/api/v1/semantic/${dbId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId || null, client_message_id: clientMessageId }),
  });
}

/* Legacy SQL metric adapter removed in favor of canonical definitions.
export async function createMetricApi(
  dbId: string,
  metric: { name: string; description: string; sql_template: string; source: 'ai' | 'manual' }
): Promise<BusinessMetric> {
  const localMetric: BusinessMetric = {
    id: `m_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    ...metric,
    created_at: new Date().toISOString(),
  };

  try {
    const res = await fetch(`${API_BASE}/api/v1/semantic/${dbId}/metric`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(metric),
    });
    if (res.ok) {
      const data = await res.json();
      return {
        id: String(data.metric_id || localMetric.id),
        name: data.name || localMetric.name,
        description: data.description || localMetric.description,
        sql_template: data.sql_template || localMetric.sql_template,
        source: data.source || localMetric.source,
      };
    }
  } catch {
    // Return localMetric on network error
  }
  return localMetric;
}

export async function updateMetricApi(
  dbId: string,
  metricId: string,
  data: { name?: string; description?: string; sql_template?: string }
): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/v1/semantic/${dbId}/metric/${metricId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
      },
      body: JSON.stringify(data),
    });
  } catch {
    // Ignore on offline fallback
  }
}

export async function deleteMetricApi(dbId: string, metricId: string): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/v1/semantic/${dbId}/metric/${metricId}`, {
      method: 'DELETE',
      headers: getAuthHeader(),
    });
  } catch {
    // Ignore on offline fallback
  }
}

*/

export async function createMetricApi(
  dbId: string,
  payload: { definition: MetricDefinition; source: 'ai' | 'manual' },
): Promise<MetricRecord> {
  const data = await semanticRequest<{ metric_id: number; definition: MetricDefinition; source: 'ai' | 'manual' }>(
    `/api/v1/semantic/${dbId}/metric`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
  return metricResponseToRecord(data);
}

export async function updateMetricApi(
  dbId: string,
  metricId: number,
  definition: MetricDefinition,
): Promise<MetricRecord> {
  const data = await semanticRequest<{ metric_id: number; definition: MetricDefinition; source: 'ai' | 'manual' }>(
    `/api/v1/semantic/${dbId}/metric/${metricId}`,
    { method: 'PUT', body: JSON.stringify({ definition }) },
  );
  return metricResponseToRecord(data);
}

export async function deleteMetricApi(dbId: string, metricId: number): Promise<void> {
  await semanticRequest<void>(`/api/v1/semantic/${dbId}/metric/${metricId}`, { method: 'DELETE' });
}

export async function listMetricsApi(dbId: string): Promise<MetricRecord[]> {
  return semanticRequest<MetricRecord[]>(`/api/v1/semantic/${dbId}/metrics`);
}

export async function getMetricHistoryApi(dbId: string, metricId: number): Promise<MetricHistory> {
  return semanticRequest<MetricHistory>(`/api/v1/semantic/${dbId}/metric/${metricId}/history`);
}

export async function approveMetricsApi(dbId: number): Promise<{ approved_count: number; message: string }> {
  return semanticRequest('/api/v1/semantic/approve', {
    method: 'POST',
    body: JSON.stringify({ db_id: dbId }),
  });
}

export async function approveSingleMetricApi(dbId: string, metricId: number): Promise<MetricRecord> {
  const data = await semanticRequest<{ metric_id: number; definition: MetricDefinition; source: 'ai' | 'manual' }>(
    `/api/v1/semantic/${dbId}/metric/${metricId}/approve`,
    { method: 'POST' },
  );
  return metricResponseToRecord(data);
}


export async function getSemanticCatalogApi(dbId: string): Promise<SemanticCatalog> {
  return semanticRequest<SemanticCatalog>(`/api/v1/semantic/${dbId}/catalog`);
}

export async function executeSemanticQueryApi(
  dbId: string,
  request: SemanticQueryRequest,
): Promise<SemanticQueryResult> {
  return semanticRequest<SemanticQueryResult>(`/api/v1/semantic/${dbId}/query`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function compileSemanticQueryApi(
  dbId: string,
  request: SemanticQueryRequest,
): Promise<SemanticQueryPreview> {
  return semanticRequest<SemanticQueryPreview>('/api/v1/semantic/' + dbId + '/query/compile', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function exportSemanticLayerApi(dbId: string, format: 'json' | 'yaml'): Promise<string> {
  const response = await fetch(`${API_BASE}/api/v1/semantic/${dbId}/export?format=${format}`, {
    headers: getAuthHeader(),
  });
  if (!response.ok) throw new SemanticApiError(response.status, await semanticError(response));
  return response.text();
}

// SQL Dump & Imported Schema Types & Functions
export interface SqlIdentifier {
  raw_name: string;
  normalized_name: string;
  quoted: boolean;
}

export interface SqlDumpColumn {
  column_name: SqlIdentifier;
  ordinal_position: number;
  raw_data_type: string;
  data_type: string;
  nullable: boolean;
  default_expression: string | null;
  primary_key: boolean;
}

export interface SqlDumpForeignKey {
  constrained_columns: SqlIdentifier[];
  referred_schema: SqlIdentifier;
  referred_table: SqlIdentifier;
  referred_columns: SqlIdentifier[];
}

export interface SqlDumpTable {
  schema_name: SqlIdentifier;
  table_name: SqlIdentifier;
  columns: SqlDumpColumn[];
  foreign_keys: SqlDumpForeignKey[];
}

export interface ParseDiagnostic {
  severity: 'info' | 'warning' | 'error';
  code: string;
  message: string;
  line: number | null;
  column: number | null;
}

export interface SqlDumpPreview {
  dialect: 'postgresql' | 'mysql' | 'sqlite';
  raw_schema: {
    contract_version: '1.0';
    tables: SqlDumpTable[];
  };
  diagnostics: ParseDiagnostic[];
}

export interface ImportedSchemaSummary {
  id: number;
  semantic_db_id: number | null;
  display_name: string;
  dialect: 'postgresql' | 'mysql' | 'sqlite';
  table_count: number;
  created_at: string;
  updated_at: string;
}

export interface ImportedSchemaRecord extends ImportedSchemaSummary {
  raw_schema: SqlDumpPreview['raw_schema'];
}

export async function uploadSqlDumpPreview(
  file: File,
  dialect: '' | 'postgresql' | 'mysql',
  token: string,
): Promise<SqlDumpPreview> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/sql',
    'X-Filename': file.name,
    ...getWorkspaceHeader(),
  };
  if (dialect) headers['X-SQL-Dialect'] = dialect;
  const response = await fetch(`${API_BASE_URL}/api/v1/semantic/import/preview`, {
    method: 'POST',
    headers,
    body: file,
  });
  if (!response.ok) throw new Error(await readPreviewError(response));
  return response.json() as Promise<SqlDumpPreview>;
}

async function readPreviewError(response: Response): Promise<string> {
  const payload = (await response.json().catch(() => null)) as {
    detail?: string | { message?: string };
  } | null;
  if (typeof payload?.detail === 'string') return payload.detail;
  return payload?.detail?.message || `Upload failed (${response.status})`;
}

export async function saveImportedSchema(
  displayName: string,
  preview: SqlDumpPreview,
  token: string,
): Promise<ImportedSchemaRecord> {
  return requestImportedSchema('/api/v1/semantic/import/saved', token, {
    method: 'POST',
    body: JSON.stringify({ display_name: displayName, raw_schema: preview.raw_schema }),
  });
}

export async function listImportedSchemas(token: string): Promise<ImportedSchemaSummary[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/semantic/import/saved`, {
    headers: { Authorization: `Bearer ${token}`, ...getWorkspaceHeader() },
  });
  if (!response.ok) throw new Error(await readPreviewError(response));
  return response.json() as Promise<ImportedSchemaSummary[]>;
}

export async function getImportedSchema(id: number, token: string): Promise<ImportedSchemaRecord> {
  return requestImportedSchema(`/api/v1/semantic/import/saved/${id}`, token);
}

export async function deleteImportedSchema(id: number, token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/semantic/import/saved/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}`, ...getWorkspaceHeader() },
  });
  if (!response.ok) throw new Error(await readPreviewError(response));
}

async function requestImportedSchema(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<ImportedSchemaRecord> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...getWorkspaceHeader(),
      'Content-Type': 'application/json',
    },
  });
  if (!response.ok) throw new Error(await readPreviewError(response));
  return response.json() as Promise<ImportedSchemaRecord>;
}

export interface LiveDbSummary {
  id: number;
  semantic_db_id: number | null;
  display_name: string;
  dialect: 'postgresql' | 'mysql' | 'sqlite';
  table_count: number;
  created_at: string;
  updated_at: string;
}

export interface LiveDbRecord extends LiveDbSummary {
  raw_schema: SqlDumpPreview['raw_schema'];
}

export async function connectLiveTargetDb(
  displayName: string,
  dialect: 'auto' | 'postgresql' | 'mysql' | 'sqlite',
  connUrl: string,
  token: string,
): Promise<LiveDbRecord> {
  const response = await fetch(`${API_BASE_URL}/api/v1/semantic/db/connect`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      ...getWorkspaceHeader(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      display_name: displayName,
      dialect,
      conn_url: connUrl,
    }),
  });
  if (!response.ok) throw new Error(await readPreviewError(response));
  return response.json() as Promise<LiveDbRecord>;
}

export async function listLiveTargetDbs(token: string): Promise<LiveDbSummary[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/semantic/db/saved`, {
    headers: { Authorization: `Bearer ${token}`, ...getWorkspaceHeader() },
  });
  if (!response.ok) throw new Error(await readPreviewError(response));
  return response.json() as Promise<LiveDbSummary[]>;
}

export async function getLiveTargetDb(id: number, token: string): Promise<LiveDbRecord> {
  const response = await fetch(`${API_BASE_URL}/api/v1/semantic/db/saved/${id}`, {
    headers: { Authorization: `Bearer ${token}`, ...getWorkspaceHeader() },
  });
  if (!response.ok) throw new Error(await readPreviewError(response));
  return response.json() as Promise<LiveDbRecord>;
}

export async function deleteLiveTargetDb(id: number, token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/semantic/db/saved/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}`, ...getWorkspaceHeader() },
  });
  if (!response.ok) throw new Error(await readPreviewError(response));
}

export async function deleteDatabaseApi(id: string, token: string): Promise<void> {
  const numId = Number(id);
  if (isNaN(numId)) {
    return;
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/semantic/db/${id}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}`, ...getWorkspaceHeader() },
  });
  if (!response.ok) {
    await deleteLiveTargetDb(numId, token).catch(() => null);
    await deleteImportedSchema(numId, token).catch(() => null);
  }
}

interface RawColumnItem {
  column_name?: string | { raw_name?: string; normalized_name?: string };
  data_type?: string;
  raw_data_type?: string;
}

interface RawTableItem {
  table_name?: string | { raw_name?: string; normalized_name?: string };
  columns?: RawColumnItem[];
}

interface RawSchemaContainer {
  tables?: RawTableItem[];
}

export function convertRawSchemaToLayer(
  id: string | number,
  dbName: string,
  dialect: string,
  rawSchema: RawSchemaContainer | null | undefined,
  connUrl?: string,
  updatedAt?: string,
  semanticDbId?: number | null,
  sourceType: 'live' | 'sql_dump' = 'live',
): SemanticLayerData {
  const tables: SemanticTable[] = (rawSchema?.tables || []).map((tbl: RawTableItem) => {
    const rawTableName =
      typeof tbl.table_name === 'object' && tbl.table_name !== null
        ? tbl.table_name.raw_name || tbl.table_name.normalized_name
        : String(tbl.table_name || 'table');

    const columns: SemanticColumn[] = (tbl.columns || []).map((col: RawColumnItem) => {
      const rawColName =
        typeof col.column_name === 'object' && col.column_name !== null
          ? col.column_name.raw_name || col.column_name.normalized_name
          : String(col.column_name || 'column');
      const dataType = col.data_type || col.raw_data_type || 'VARCHAR';
      return {
        column_name: rawColName || 'column',
        data_type: dataType,
        business_name: rawColName || 'column',
        description: '',
      };
    });

    return {
      table_name: rawTableName || 'table',
      business_name: rawTableName || 'table',
      description: '',
      columns,
    };
  });

  const normalizedDialect = (
    dialect === 'mysql' || dialect === 'sqlite' || dialect === 'postgresql' ? dialect : 'postgresql'
  ) as 'postgresql' | 'mysql' | 'sqlite';

  return {
    id: String(id),
    semantic_db_id: semanticDbId,
    source_type: sourceType,
    db_name: dbName,
    db_type: normalizedDialect,
    conn_url: connUrl,
    status: 'Draft',
    updated_at: updatedAt || new Date().toISOString().replace('T', ' ').slice(0, 16),
    tables,
    metrics: [],
  };
}

// ---------------------------------------------------------------------------
// Guided Wizard AI Query Assistant API
// ---------------------------------------------------------------------------

export interface SemanticQuerySpec {
  metric_ids: number[];
  dimensions: DimensionSelection[];
  filters: SemanticQueryFilter[];
  limit: number;
}

export interface WizardOption {
  id: string;
  label: string;
  description?: string;
}

export interface WizardStartResponse {
  session_id: string;
  step: number;
  title: string;
  question: string;
  options: WizardOption[];
  is_completed: boolean;
}

export interface WizardStepResponse {
  step: number;
  title: string;
  question: string;
  options: WizardOption[];
  is_completed: boolean;
  resolved_spec?: SemanticQuerySpec | null;
  sql_preview?: string | null;
}

export async function startWizardApi(dbId: number): Promise<WizardStartResponse> {
  return semanticRequest<WizardStartResponse>(`/api/v1/semantic/${dbId}/query/wizard/start`, {
    method: 'POST',
  });
}

export async function advanceWizardApi(
  dbId: number,
  sessionId: string,
  optionId: string
): Promise<WizardStepResponse> {
  return semanticRequest<WizardStepResponse>(`/api/v1/semantic/${dbId}/query/wizard/step`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, option_id: optionId }),
  });
}

export interface RecommendedDimensionItem {
  column_id: number;
  column_name: string;
  business_name: string;
  table_id: number;
  table_name: string;
  table_business_name: string;
  tier: 'A' | 'B' | 'C' | 'D';
  tier_label: string;
  is_safe_join: boolean;
  requires_reaggregation: boolean;
  data_type: string;
  cardinality_hint?: number | null;
}

export interface MetricDimensionsResponse {
  metric_id: number;
  metric_name: string;
  base_table: string;
  dimensions: RecommendedDimensionItem[];
}

export async function getMetricRecommendedDimensionsApi(
  dbId: number | string,
  metricId: number | string
): Promise<MetricDimensionsResponse> {
  return semanticRequest<MetricDimensionsResponse>(
    `/api/v1/semantic/${dbId}/metric/${metricId}/dimensions`
  );
}
export interface FilterColumnItem {
  column_id: number;
  column_name: string;
  business_name: string;
  table_id: number;
  table_name: string;
  table_business_name: string;
  group_type: 'base' | 'related';
  data_type: string;
  is_time_dimension: boolean;
}

export interface MetricFilterColumnsResponse {
  metric_id: number;
  metric_name: string;
  base_table: string;
  columns: FilterColumnItem[];
}

export async function getMetricFilterColumnsApi(
  dbId: number | string,
  metricId: number | string
): Promise<MetricFilterColumnsResponse> {
  return semanticRequest<MetricFilterColumnsResponse>(
    `/api/v1/semantic/${dbId}/metric/${metricId}/filter-columns`
  );
}

