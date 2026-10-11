# ==============================================================================
# MODULE VPC / VCN CHO ORACLE CLOUD INFRASTRUCTURE (OCI)
# Phân tầng mạng 2 lớp chuẩn Enterprise: Public Subnet & Private Subnet
# ==============================================================================

# 1. Virtual Cloud Network (VCN)
resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_id
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "${var.environment}-${var.vcn_name}"
  dns_label      = "p069vcn"
}

# 2. Internet Gateway (Cổng Internet cho Public Subnet)
resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.environment}-igw"
  enabled        = true
}

# 3. NAT Gateway (Cổng Internet 1 chiều cho Private Subnet tải package/image)
resource "oci_core_nat_gateway" "nat_gw" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.environment}-nat-gw"
}

# 4. Route Table cho Public Subnet (Trỏ 0.0.0.0/0 ra Internet Gateway)
resource "oci_core_route_table" "public_rt" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.environment}-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.igw.id
    description       = "Default route to Internet Gateway"
  }
}

# 5. Route Table cho Private Subnet (Trỏ 0.0.0.0/0 qua NAT Gateway)
resource "oci_core_route_table" "private_rt" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.environment}-private-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.nat_gw.id
    description       = "Default route to NAT Gateway for outbound traffic"
  }
}

# 6. Security List cho Public Subnet (Mở Ingress: HTTP 80, HTTPS 443, SSH 22)
resource "oci_core_security_list" "public_sl" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.environment}-public-sl"

  # Cho phép mọi traffic đi ra ngoài
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
    description = "Allow all outbound traffic"
  }

  # Ingress: HTTP (Port 80)
  ingress_security_rules {
    protocol    = "6" # TCP
    source      = "0.0.0.0/0"
    description = "Allow HTTP traffic from anywhere (for Nginx / Cloudflare)"
    tcp_options {
      min = 80
      max = 80
    }
  }

  # Ingress: HTTPS (Port 443)
  ingress_security_rules {
    protocol    = "6" # TCP
    source      = "0.0.0.0/0"
    description = "Allow HTTPS traffic from anywhere"
    tcp_options {
      min = 443
      max = 443
    }
  }

  # Ingress: SSH (Port 22)
  ingress_security_rules {
    protocol    = "6" # TCP
    source      = "0.0.0.0/0"
    description = "Allow SSH management"
    tcp_options {
      min = 22
      max = 22
    }
  }
}

# 7. Security List cho Private Subnet (Bảo mật tối đa, CHỈ nhận từ Public Subnet)
resource "oci_core_security_list" "private_sl" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.environment}-private-sl"

  # Cho phép ra ngoài qua NAT Gateway
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
    description = "Allow all outbound traffic via NAT"
  }

  # Ingress: Traffic nội bộ trong Private Subnet (giữa các Pod/Service với nhau)
  ingress_security_rules {
    protocol    = "all"
    source      = var.private_subnet_cidr
    description = "Allow all intra-private-subnet communication"
  }

  # Ingress: PostgreSQL (Port 5432) chỉ cho phép từ Public Subnet
  ingress_security_rules {
    protocol    = "6" # TCP
    source      = var.public_subnet_cidr
    description = "Allow PostgreSQL access strictly from Public Subnet"
    tcp_options {
      min = 5432
      max = 5432
    }
  }

  # Ingress: Redis (Port 6379) chỉ cho phép từ Public Subnet
  ingress_security_rules {
    protocol    = "6" # TCP
    source      = var.public_subnet_cidr
    description = "Allow Redis access strictly from Public Subnet"
    tcp_options {
      min = 6379
      max = 6379
    }
  }

  # Ingress: Backend Service (Port 8000) từ Public Subnet (Nginx Reverse Proxy)
  ingress_security_rules {
    protocol    = "6" # TCP
    source      = var.public_subnet_cidr
    description = "Allow Backend API access from Public Subnet / Nginx"
    tcp_options {
      min = 8000
      max = 8000
    }
  }
}

# 8. Public Subnet (Load Balancer, Ingress Controller, Public Entry)
resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.this.id
  cidr_block                 = var.public_subnet_cidr
  display_name               = "${var.environment}-public-subnet"
  dns_label                  = "public"
  route_table_id             = oci_core_route_table.public_rt.id
  security_list_ids          = [oci_core_security_list.public_sl.id]
  prohibit_public_ip_on_vnic = false
}

# 9. Private Subnet (K8s Nodes, Database, Redis, Core Services)
resource "oci_core_subnet" "private" {
  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.this.id
  cidr_block                 = var.private_subnet_cidr
  display_name               = "${var.environment}-private-subnet"
  dns_label                  = "private"
  route_table_id             = oci_core_route_table.private_rt.id
  security_list_ids          = [oci_core_security_list.private_sl.id]
  prohibit_public_ip_on_vnic = true
}
