variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "service_name" {
  description = "Cloud Run Service Name"
  type        = string
  default     = "paperterrace"
}

variable "min_instance_count" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "cpu" {
  description = "CPU limit"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory limit"
  type        = string
  default     = "1Gi"
}

variable "concurrency" {
  description = "Max concurrent requests per instance"
  type        = number
  default     = 80
}

variable "image_url" {
  description = "Docker image URL"
  type        = string
}

variable "subnet_name" {
  description = "Subnet Name for Direct VPC Egress"
  type        = string
}

variable "vpc_network_name" {
  description = "VPC Network Name"
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

variable "service_account_email" {
  description = "Service Account Email to run the service as"
  type        = string
}

/*
variable "redis_host" {
  description = "Redis host"
  type        = string
  default     = "localhost"
}

variable "redis_port" {
  description = "Redis port"
  type        = string
  default     = "6379"
}
*/

variable "request_timeout" {
  description = "Request timeout in seconds"
  type        = string
  default     = "300s"
}

variable "idle_timeout" {
  description = "Idle timeout annotation (not directly supported in Cloud Run v2)"
  type        = string
  default     = "15m"
}

variable "inference_service_url" {
  description = "URL of the inference service (Service B)"
  type        = string
  default     = ""
}

variable "batch_parallel_workers" {
  description = "Number of parallel workers for batch processing"
  type        = number
  default     = 2
}
