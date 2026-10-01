# 🏗️ Hướng dẫn Import VPS Oracle Cloud vào Terraform (IaC)

Tài liệu này hướng dẫn cách **nhập (import) con VPS Oracle hiện tại (`140.245.58.162`)** vào mã nguồn Terraform để quản lý hạ tầng bằng code, **tuyệt đối không gây gián đoạn hay tắt máy chủ**.

---

## 1. 🔑 Lấy OCI API Key (Để Terraform có quyền đọc hạ tầng)

1. Đăng nhập [Oracle Cloud Console](https://cloud.oracle.com/).
2. Bấm vào icon **Profile** (góc trên cùng bên phải) ➔ Chọn **User settings**.
3. Cuộn xuống mục **API Keys** (cột trái) ➔ Bấm **Add API Key**.
4. Chọn **Generate API Key Pair** ➔ Bấm **Download Private Key** (lưu file này vào máy, ví dụ: `~/.oci/oci_api_key.pem`).
5. Bấm **Add**.
6. Một bảng cấu hình mẫu sẽ hiện ra. Bạn copy các thông tin:
   - `user`: (User OCID)
   - `fingerprint`: (Chuỗi fingerprint)
   - `tenancy`: (Tenancy OCID)
   - `region`: (Vùng cloud của bạn)

---

## 2. 📋 Lấy OCID của con VPS đang chạy

1. Trên Oracle Console, vào menu hamburger ➔ **Compute** ➔ **Instances**.
2. Bấm vào tên VPS của bạn (`instance-20261001-1134`).
3. Ở dòng **OCID**, bấm **Copy**.

---

## 3. ⚙️ Điền thông tin vào `terraform.tfvars`

Tạo file `terraform/terraform.tfvars` từ file mẫu:

```hcl
tenancy_ocid     = "ocid1.tenancy.oc1..aaaaaaaaxxxxx"
user_ocid        = "ocid1.user.oc1..aaaaaaaayyyyy"
fingerprint      = "xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx"
private_key_path = "C:/Users/admin/.oci/oci_api_key.pem" # Đường dẫn file .pem vừa tải
region           = "ap-singapore-1"                      # Điền đúng region của bạn
compartment_ocid = "ocid1.tenancy.oc1..aaaaaaaaxxxxx"    # Dùng luôn Tenancy OCID nếu dùng root compartment

# Dán OCID của con VPS vừa copy ở Bước 2:
instance_ocid    = "ocid1.instance.oc1.ap-singapore-1.aaaaaaaawwwww"
```

---

## 4. 🚀 Chạy Import VPS vào Terraform

Mở terminal tại thư mục `terraform/` và chạy:

```bash
# 1. Tải OCI Provider
terraform init

# 2. Tự động đọc cấu hình VPS thật và import vào code
terraform plan -generate-config-out=generated_instance.tf

# 3. Áp dụng quản lý
terraform apply
```

Sau lệnh này, toàn bộ cấu hình con VPS Oracle (`140.245.58.162`) đã được số hóa và quản lý 100% bằng Terraform!
