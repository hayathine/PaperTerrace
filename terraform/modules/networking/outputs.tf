output "vpc_network_id" {
  description = "VPC Network ID"
  value       = google_compute_network.main.id
}

output "vpc_network_name" {
  description = "VPC Network name"
  value       = google_compute_network.main.name
}

output "subnet_id" {
  description = "Subnet ID"
  value       = google_compute_subnetwork.main.id
}

output "vpc_connector_id" {
  description = "VPC Connector ID"
  value       = google_vpc_access_connector.connector.id
}

output "private_ip_address" {
  description = "Private IP address for Cloud SQL"
  value       = google_compute_global_address.private_ip.name
}
