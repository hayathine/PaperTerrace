# Networking Module - VPC, Subnets, VPC Connector

# VPC Network
resource "google_compute_network" "main" {
  name                    = "paperterrace-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

# Subnet for Cloud Run VPC Connector
resource "google_compute_subnetwork" "main" {
  name          = "paperterrace-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.main.id
  project       = var.project_id

  private_ip_google_access = true
}

# VPC Connector for Cloud Run to access Cloud SQL
resource "google_vpc_access_connector" "connector" {
  name          = "paperterrace-connector"
  region        = var.region
  project       = var.project_id
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.main.name

  min_instances = 2
  max_instances = 3
}

# Private IP allocation for Cloud SQL
resource "google_compute_global_address" "private_ip" {
  name          = "paperterrace-private-ip"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

# Private connection for Cloud SQL
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

# Firewall rules
resource "google_compute_firewall" "allow_internal" {
  name    = "paperterrace-allow-internal"
  network = google_compute_network.main.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/8"]
}
