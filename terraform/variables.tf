# Project configuration
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "paperterrace"
}

variable "project_number" {
  description = "GCP Project Number"
  type        = string
  default     = "316073929194"
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "asia-northeast1"
}

# Application configuration
variable "image_url" {
  description = "Docker image URL for Cloud Run"
  type        = string
  default     = "asia-northeast1-docker.pkg.dev/paperterrace/paperterrace/app:latest"
}

# Secrets (sensitive)
variable "gemini_api_key" {
  description = "Gemini API Key"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Cloud SQL database password"
  type        = string
  sensitive   = true
}
