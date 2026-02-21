variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "service_account_email" {
  description = "Service Account Email to grant access to"
  type        = string
}
