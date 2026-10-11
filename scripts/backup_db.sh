#!/bin/bash
# ==============================================================================
# SCRIPT TỰ ĐỘNG SAO LƯU POSTGRESQL (P-069)
# Tự động nén, quản lý vòng đời (Retention 7 ngày) và hỗ trợ đẩy lên OCI Storage
# ==============================================================================

set -euo pipefail

# Cấu hình đường dẫn và thông số
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/p069}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-p-069-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-semantic_layer}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/p069_${POSTGRES_DB}_${TIMESTAMP}.sql.gz"

echo "=========================================================="
echo "🕒 [$(date '+%Y-%m-%d %H:%M:%S')] Bắt đầu sao lưu Database..."
echo "📂 Thư mục sao lưu : ${BACKUP_DIR}"
echo "🗄️ Database        : ${POSTGRES_DB}"
echo "🐳 Container       : ${POSTGRES_CONTAINER}"
echo "=========================================================="

# Tạo thư mục sao lưu nếu chưa tồn tại
mkdir -p "${BACKUP_DIR}"

# 1. Kiểm tra container PostgreSQL có đang chạy không
if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    echo "⚡ Đang kết xuất và nén dữ liệu từ container Docker..."
    docker exec "${POSTGRES_CONTAINER}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
        | gzip -9 > "${BACKUP_FILE}"
elif command -v kubectl &> /dev/null && kubectl get pods -l app=postgres --no-headers 2>/dev/null | grep -q "Running"; then
    echo "⚡ Đang kết xuất từ Kubernetes Pod..."
    POD_NAME=$(kubectl get pods -l app=postgres -o jsonpath="{.items[0].metadata.name}")
    kubectl exec "${POD_NAME}" -- pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
        | gzip -9 > "${BACKUP_FILE}"
else
    echo "❌ LỖI: Không tìm thấy container hoặc pod PostgreSQL đang chạy!"
    exit 1
fi

FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "✅ Sao lưu thành công: ${BACKUP_FILE} (Dung lượng: ${FILE_SIZE})"

# 2. Xóa các bản sao lưu cũ hơn số ngày quy định (mặc định 7 ngày)
echo "🧹 Đang dọn dẹp các bản sao lưu cũ hơn ${RETENTION_DAYS} ngày..."
DELETED_COUNT=$(find "${BACKUP_DIR}" -name "p069_${POSTGRES_DB}_*.sql.gz" -mtime +"${RETENTION_DAYS}" | wc -l)
find "${BACKUP_DIR}" -name "p069_${POSTGRES_DB}_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete
echo "✨ Đã xóa ${DELETED_COUNT} bản sao lưu hết hạn."

# 3. (Tùy chọn) Đẩy lên OCI Object Storage nếu cấu hình OCI_BUCKET_NAME
if [ -n "${OCI_BUCKET_NAME:-}" ] && command -v oci &> /dev/null; then
    echo "☁️ Đang tải bản sao lưu lên OCI Object Storage Bucket: ${OCI_BUCKET_NAME}..."
    oci os object put -bn "${OCI_BUCKET_NAME}" --file "${BACKUP_FILE}" --force
    echo "✅ Đã tải lên OCI Cloud thành công!"
fi

echo "🎉 Quy trình sao lưu hoàn tất an toàn lúc $(date '+%Y-%m-%d %H:%M:%S')!"
