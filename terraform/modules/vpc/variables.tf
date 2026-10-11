variable "compartment_id" {
  description = "OCID của Compartment trên Oracle Cloud"
  type        = string
}

variable "vcn_name" {
  description = "Tên nhận diện cho VCN"
  type        = string
  default     = "p069-vcn"
}

variable "vcn_cidr" {
  description = "Dải CIDR cho mạng chính VCN"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Dải CIDR cho Public Subnet (Load Balancer / Ingress / Cổng truy cập ngoài)"
  type        = string
  default     = "10.0.1.0/24"
}

variable "private_subnet_cidr" {
  description = "Dải CIDR cho Private Subnet (App Services, Database, Redis)"
  type        = string
  default     = "10.0.2.0/24"
}

variable "environment" {
  description = "Môi trường triển khai (production, staging, dev)"
  type        = string
  default     = "production"
}
