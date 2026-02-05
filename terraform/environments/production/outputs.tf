output "cloud_run_url" {
  description = "The URL of the Cloud Run service"
  value       = module.cloud_run.service_url
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = module.artifact_registry.repository_url
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name"
  value       = module.cloud_sql.connection_name
}

output "cloud_sql_private_ip" {
  description = "Cloud SQL private IP"
  value       = module.cloud_sql.private_ip
  sensitive   = true
}

output "cloud_sql_instance_name" {
  description = "Cloud SQL instance name"
  value       = module.cloud_sql.instance_name
}

output "cloud_sql_db_user" {
  description = "Cloud SQL Database User"
  value       = module.cloud_sql.database_user
}

output "storage_bucket_name" {
  description = "Cloud Storage bucket name"
  value       = module.storage.bucket_name
}

output "vpc_network_name" {
  description = "VPC Network Name"
  value       = module.networking.vpc_network_name
}

output "vpc_network_id" {
  description = "VPC Network ID"
  value       = module.networking.vpc_network_id
}

output "subnet_name" {
  description = "Subnet Name"
  value       = module.networking.subnet_name
}

output "service_account_email" {
  description = "Service Account Email"
  value       = module.iam.service_account_email
}

output "gemini_api_key_secret_id" {
  description = "Secret ID for Gemini API Key"
  value       = module.secrets.gemini_api_key_secret_id
}

output "db_password_secret_id" {
  description = "Secret ID for DB Password"
  value       = module.secrets.db_password_secret_id
}

output "redis_production_host" {
  description = "Production Redis host"
  value       = module.redis_production.redis_host
}

output "redis_production_port" {
  description = "Production Redis port"
  value       = module.redis_production.redis_port
}

output "redis_production_connection_string" {
  description = "Production Redis connection string"
  value       = module.redis_production.redis_connection_string
}
