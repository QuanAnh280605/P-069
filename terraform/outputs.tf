output "vps_id" {
  description = "OCID của VPS Oracle"
  value       = oci_core_instance.vps.id
}

output "vps_public_ip" {
  description = "Địa chỉ IP Public của VPS"
  value       = oci_core_instance.vps.public_ip
}

output "vps_shape" {
  description = "Cấu hình phần cứng"
  value       = "${oci_core_instance.vps.shape} (${oci_core_instance.vps.shape_config[0].ocpus} OCPU, ${oci_core_instance.vps.shape_config[0].memory_in_gbs} GB RAM)"
}

output "vcn_id" {
  description = "OCID của Virtual Cloud Network (VCN)"
  value       = module.vpc.vcn_id
}

output "public_subnet_id" {
  description = "OCID của Public Subnet (Load Balancer / Ingress)"
  value       = module.vpc.public_subnet_id
}

output "private_subnet_id" {
  description = "OCID của Private Subnet (Database, Redis, App)"
  value       = module.vpc.private_subnet_id
}
