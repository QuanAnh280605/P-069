# ==============================================================================
# HẠ TẦNG VPS ORACLE CLOUD (140.245.58.162) - ĐÃ ĐƯỢC IMPORT VÀO TERRAFORM
# ==============================================================================

resource "oci_core_instance" "vps" {
  availability_domain = "ScQZ:AP-SINGAPORE-2-AD-1"
  compartment_id      = "ocid1.tenancy.oc1..aaaaaaaavms5zapkgqcrgb5nkp57u7rfnmvgkfuun7jrs7oi34pyvm5uehaa"
  display_name        = "instance-20261001-1134"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = 2
    memory_in_gbs = 12
  }

  create_vnic_details {
    subnet_id        = "ocid1.subnet.oc1.ap-singapore-2.aaaaaaaazbppuzzgideqepnagevs5xbcbwfbvvvu3lskfaofdom3mlnydl7q"
    assign_public_ip = "true"
    display_name     = "instance-20261001-1134"
    hostname_label   = "instance-20261001-1134"
  }

  source_details {
    source_type             = "image"
    source_id               = "ocid1.image.oc1.ap-singapore-2.aaaaaaaan7h2srks22b2jnihsx7i5vwdurk7g6wq5wtjmnzqaghiesnintxa"
    boot_volume_size_in_gbs = "47"
  }

  # Bảo vệ máy chủ: Không tự động tạo lại (recreate) khi có thay đổi nhỏ
  lifecycle {
    ignore_changes = [
      metadata,
      defined_tags,
      freeform_tags,
      create_vnic_details[0].defined_tags
    ]
  }
}
