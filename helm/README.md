# ⎈ Hướng dẫn triển khai bằng Helm Chart — AI Semantic Layer Agent

Helm đóng vai trò là **Package Manager** cho Kubernetes. Thay vì chạy từng file YAML thủ công (`kubectl apply -f ...`), bạn chỉ cần **1 lệnh Helm duy nhất** để triển khai, nâng cấp hoặc rollback toàn bộ hệ thống (Postgres, Backend, Frontend, Ingress).

---

## 1. 📂 Cấu trúc Helm Chart

```text
helm/p069/
├── Chart.yaml              # Thông tin metadata của chart (version, name)
├── values.yaml             # Toàn bộ biến cấu hình (môi trường, replica, image, port, DB)
└── templates/              # Các mẫu Kubernetes manifests (tự động điền theo values.yaml)
    ├── _helpers.tpl        # Hàm tiện ích đặt tên và nhãn (labels)
    ├── postgres.yaml       # PVC + Deployment + Service của Database
    ├── backend.yaml        # Secret + Deployment + Service của FastAPI
    ├── frontend.yaml       # Deployment + Service của Next.js
    └── ingress.yaml        # Ingress phân luồng API và Frontend
```

---

## 2. 🚀 Cài đặt Helm trên VPS Oracle

Chạy lệnh sau trên cửa sổ SSH để cài đặt Helm 3 mới nhất:

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

Kiểm tra phiên bản sau khi cài:
```bash
helm version
```

---

## 3. 🛠️ Triển khai ứng dụng với Helm

### Bước 1: Dừng Docker Compose (để giải phóng cổng 80 & 443 cho K8s Ingress)
```bash
cd /home/ubuntu/P-069
docker compose down
```

### Bước 2: Đảm bảo K3s đã được cài đặt
Nếu VPS chưa có K3s, cài đặt bằng lệnh:
```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--write-kubeconfig-mode 644" sh -
```

### Bước 3: Nạp Docker Image vào K3s (hoặc kéo từ Container Registry)
```bash
# Build và nạp backend vào k3s
docker build -t p069-backend:latest .
docker save p069-backend:latest | sudo k3s ctr images import -

# Build và nạp frontend vào k3s
docker build -t p069-frontend:latest ./frontend
docker save p069-frontend:latest | sudo k3s ctr images import -
```

### Bước 4: Kiểm tra thử bản render của Chart (Dry-run)
```bash
helm template my-app ./helm/p069
```

### Bước 5: Cài đặt / Nâng cấp (Deploy)
```bash
helm upgrade --install p069 ./helm/p069
```

---

## 4. 🎛️ Các lệnh quản trị thường dùng

### Xem trạng thái triển khai:
```bash
helm status p069
kubectl get pods -w
kubectl get ingress
```

### Thay đổi cấu hình trực tiếp (ví dụ: tăng replicas Backend lên 2 hoặc đổi API Key):
```bash
# Tăng số lượng backend pod lên 2
helm upgrade p069 ./helm/p069 --set backend.replicaCount=2

# Hoặc truyền file values tùy biến cho môi trường production:
helm upgrade p069 ./helm/p069 -f ./helm/p069/values-prod.yaml
```

### Xem lịch sử các lần deploy (Releases):
```bash
helm history p069
```

### Rollback về phiên bản trước đó ngay lập tức (nếu bản mới bị lỗi):
```bash
helm rollback p069 1
```

### Xóa toàn bộ ứng dụng khi cần dọn dẹp:
```bash
helm uninstall p069
```
