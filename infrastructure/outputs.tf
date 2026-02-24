# Artifact Registry
output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = module.artifact_registry.repository_url
}

# Cloud SQL
output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name"
  value       = module.cloud_sql.connection_name
}

output "cloud_sql_private_ip" {
  description = "Cloud SQL private IP"
  value       = module.cloud_sql.private_ip
  sensitive   = true
}

# Storage
output "storage_bucket_name" {
  description = "Cloud Storage bucket name"
  value       = module.storage.bucket_name
}

/*
# Redis (Memorystore)
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

output "redis_staging_host" {
  description = "Staging Redis host"
  value       = var.enable_staging ? module.redis_staging[0].redis_host : null
}

output "redis_staging_port" {
  description = "Staging Redis port"
  value       = var.enable_staging ? module.redis_staging[0].redis_port : null
}

output "redis_staging_connection_string" {
  description = "Staging Redis connection string"
  value       = var.enable_staging ? module.redis_staging[0].redis_connection_string : null
}
*/

# Networking

