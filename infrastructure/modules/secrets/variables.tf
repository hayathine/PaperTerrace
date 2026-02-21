variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gemini_api_key" {
  description = "Gemini API Key"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "service_account_email" {
  description = "Service Account Email to grant access to"
  type        = string
}
