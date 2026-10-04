variable "ssh_public_key_path" {
  type        = string
  description = "Path to the local SSH public key file"
}

variable "ssh_allowed_cidr" {
  type        = string
  description = "Local public IP allowed for SSH access (with /32)"
}
