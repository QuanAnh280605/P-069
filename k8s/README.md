# ☸️ Hướng dẫn Kubernetes Cơ bản — AI Semantic Layer Agent

Bộ cấu hình này được thiết kế **tinh gọn, trực quan** cho người đã biết Docker Compose và muốn bước lên Kubernetes trên VPS mà không bị ngợp.

---

## 1. 🗺️ Bản đồ chuyển đổi từ Docker Compose sang Kubernetes

Thay vì gom tất cả vào 1 file `docker-compose.yml`, chúng ta tách thành **4 bước độc lập** để dễ học và dễ kiểm soát:

```
[ docker-compose.yml ]                         [ Kubernetes (Thư mục k8s/) ]
----------------------                         -----------------------------
1. services.postgres          ----->           k8s/01-postgres.yaml (PVC + Pod + Service)
2. services.backend           ----->           k8s/02-backend.yaml  (Secret + Pod + Service)
3. services.frontend          ----->           k8s/03-frontend.yaml (Pod + Service)
4. ports (8000, 3000)         ----->           k8s/04-ingress.yaml  (Cổng vào duy nhất từ internet)
```

---

## 2. 🚀 Thực hành từng bước trên VPS

### Chuẩn bị trước khi chạy:
Nếu chạy trên VPS, hãy đảm bảo đã cài K3s (bản Kubernetes nhẹ nhất cho VPS):
```bash
# Cài K3s trong 1 lệnh (trên Ubuntu/Debian):
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--write-kubeconfig-mode 644" sh -
```

Build Docker image và nạp vào Kubernetes:
```bash
# Build backend
docker build -t p069-backend:latest .
docker save p069-backend:latest | sudo k3s ctr images import -

# Build frontend
docker build -t p069-frontend:latest ./frontend
docker save p069-frontend:latest | sudo k3s ctr images import -
```

---

### BẬT TỪNG DỊCH VỤ ĐỂ QUAN SÁT:

#### 🔹 Bước 1: Khởi động Database
```bash
kubectl apply -f k8s/01-postgres.yaml
```
> **Kiểm tra**: Chạy `kubectl get pods`. Bạn sẽ thấy pod `postgres-...` chuyển từ `ContainerCreating` sang `Running`.

---

#### 🔹 Bước 2: Khởi động Backend (FastAPI)
Mở file `k8s/02-backend.yaml`, điền `OPENAI_API_KEY` (hoặc API key bạn dùng), sau đó chạy:
```bash
kubectl apply -f k8s/02-backend.yaml
```
> **Xem log Backend kết nối DB**:  
> `kubectl logs -l app=backend -f`  
> *(Bạn sẽ thấy alembic tự động migrate DB và uvicorn khởi động).*

---

#### 🔹 Bước 3: Khởi động Frontend (Next.js)
```bash
kubectl apply -f k8s/03-frontend.yaml
```
> **Kiểm tra**: Chạy `kubectl get pods` $\rightarrow$ Thấy cả 3 pod `postgres`, `backend`, `frontend` đều `Running (1/1)`.

---

#### 🔹 Bước 4: Mở Ingress để truy cập từ ngoài Internet / VPS
```bash
kubectl apply -f k8s/04-ingress.yaml
```
> Giờ đây bạn có thể mở trình duyệt:
> - `http://<IP_VPS>/` $\rightarrow$ Giao diện Web
> - `http://<IP_VPS>/api/v1/...` $\rightarrow$ Gọi API Backend
> - `http://<IP_VPS>/health` $\rightarrow$ Kiểm tra trạng thái hệ thống

---

## 3. 🧪 Trải nghiệm tính năng "xịn" của Kubernetes mà Docker Compose không có

### 1. Thử nghiệm "Tự phục hồi" (Auto-healing):
Thử xóa pod backend xem Kubernetes làm gì:
```bash
kubectl delete pod -l app=backend
```
Gõ ngay `kubectl get pods`: Bạn sẽ thấy Kubernetes **tự động sinh ra ngay 1 pod mới thay thế** chỉ trong tích tắc!

### 2. Thử nghiệm "Nhân đôi sức mạnh" (Scale Replicas):
Muốn Backend chạy 3 bản sao cùng lúc để chịu tải?
```bash
kubectl scale deployment backend --replicas=3
```
Kiểm tra `kubectl get pods`, bạn sẽ thấy 3 pod backend chạy song song và tự động chia tải.

---

## 4. 🧹 Dọn dẹp khi muốn tắt
```bash
kubectl delete -f k8s/
```
Toàn bộ dịch vụ sẽ được gỡ bỏ sạch sẽ.
