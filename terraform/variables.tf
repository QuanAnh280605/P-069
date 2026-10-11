variable "compartment_id" {
  description = "OCID của Compartment trên Oracle Cloud"
  type        = string
  default     = "ocid1.tenancy.oc1..aaaaaaaavms5zapkgqcrgb5nkp57u7rfnmvgkfuun7jrs7oi34pyvm5uehaa"
}

variable "environment" {
  description = "Môi trường triển khai (production, staging, dev)"
  type        = string
  default     = "production"
}
