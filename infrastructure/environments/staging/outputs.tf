output "cloud_run_url" {
  description = "The URL of the Cloud Run Staging service"
  value       = module.cloud_run_staging.service_url
}

/*
output "redis_staging_host" {
  description = "Staging Redis host"
  value       = module.redis_staging.redis_host
}

output "redis_staging_port" {
  description = "Staging Redis port"
  value       = module.redis_staging.redis_port
}
*/
