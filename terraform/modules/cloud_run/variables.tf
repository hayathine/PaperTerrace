variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "image_url" {
  description = "Docker image URL"
  type        = string
}

variable "vpc_connector_id" {
  description = "VPC Connector ID for Cloud Run"
  type        = string
}

variable "cloud_sql_connection" {
  description = "Cloud SQL connection name"
  type        = string
}

variable "gemini_api_key_secret_id" {
  description = "Secret ID for Gemini API Key"
  type        = string
}

variable "db_password_secret_id" {
  description = "Secret ID for database password"
  type        = string
}

variable "storage_bucket" {
  description = "Cloud Storage bucket name"
  type        = string
}

variable "db_host" {
  description = "Database host (Cloud SQL private IP)"
  type        = string
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "db_user" {
  description = "Database user"
  type        = string
}
