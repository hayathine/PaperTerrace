# Cloud Run URL
output "cloud_run_url" {
  description = "The URL of the Cloud Run service"
  value       = module.cloud_run.service_url
}

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

# Networking
output "vpc_connector_id" {
  description = "VPC Connector ID for Cloud Run"
  value       = module.networking.vpc_connector_id
}
