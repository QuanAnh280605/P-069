output "vcn_id" {
  description = "OCID của Virtual Cloud Network (VCN)"
  value       = oci_core_vcn.this.id
}

output "vcn_cidr" {
  description = "Dải CIDR của VCN"
  value       = oci_core_vcn.this.cidr_blocks[0]
}

output "public_subnet_id" {
  description = "OCID của Public Subnet"
  value       = oci_core_subnet.public.id
}

output "private_subnet_id" {
  description = "OCID của Private Subnet"
  value       = oci_core_subnet.private.id
}

output "internet_gateway_id" {
  description = "OCID của Internet Gateway"
  value       = oci_core_internet_gateway.igw.id
}

output "nat_gateway_id" {
  description = "OCID của NAT Gateway"
  value       = oci_core_nat_gateway.nat_gw.id
}
