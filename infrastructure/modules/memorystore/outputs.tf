output "redis_host" {
  description = "Redis instance host"
  value       = google_redis_instance.main.host
}

output "redis_port" {
  description = "Redis instance port"
  value       = google_redis_instance.main.port
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = "${google_redis_instance.main.host}:${google_redis_instance.main.port}"
}

output "instance_id" {
  description = "Redis instance ID"
  value       = google_redis_instance.main.id
}

output "instance_name" {
  description = "Redis instance name"
  value       = google_redis_instance.main.name
}