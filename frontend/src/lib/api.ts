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

export interface BusinessMetric {
  id: string;
  name: string;
  description: string;
  sql_template: string;
  source: 'ai' | 'manual';
  created_at?: string;
}

export interface SemanticLayerData {
  id: string;
  db_name: string;
  db_type: 'postgresql' | 'mysql' | 'sqlite';
  conn_url?: string;
  status: 'Draft' | 'Saved';
  updated_at: string;
  tables: SemanticTable[];
  metrics: BusinessMetric[];
}

const INITIAL_LAYERS: SemanticLayerData[] = [
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
