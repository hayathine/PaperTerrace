# Project configuration
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "gen-lang-client-0800253336"
}

variable "cloud_task_queue" {
  description = "Cloud Tasks Queue"
  type        = string
  default     = "paper-analysis-queue"
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

variable "app_base_url" {
  description = "Base URL for the application"
  type        = string
  default     = "https://paperterrace-t2nx5gtwia-an.a.run.app"
}

# Secrets (sensitive)
variable "gemini_api_key" {
  description = "Gemini API Key"
  type        = string
  sensitive   = true
}

variable "gcp_service_account" {
  description = "GCP Service Account"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Cloud SQL database password"
  type        = string
  sensitive   = true
}
