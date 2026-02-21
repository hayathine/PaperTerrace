variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "vpc_network_id" {
  description = "VPC Network ID for private IP"
  type        = string
}

variable "private_ip_address" {
  description = "Private IP address name for Cloud SQL"
  type        = string
}
