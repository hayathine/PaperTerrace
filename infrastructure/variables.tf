# Project configuration
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "gen-lang-client-0800253336"
}

variable "project_number" {
  description = "GCP Project Number"
  type        = string
  default     = "602776143589"
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
  default     = "asia-northeast1-docker.pkg.dev/gen-lang-client-0800253336/paperterrace/app:latest"
}

variable "enable_staging" {
  description = "Enable Staging Environment"
  type        = bool
  default     = false
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
