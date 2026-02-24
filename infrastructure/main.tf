# PaperTerrace Infrastructure

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "gen-lang-client-0800253336-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Load Resource Configuration
locals {
  resources = jsondecode(file("${path.module}/../config/resources.json"))
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "iam.googleapis.com", 
    "iamcredentials.googleapis.com",
    # "redis.googleapis.com", # Redis API disabled to save cost
  ])

  service            = each.value
  disable_on_destroy = false
}

# IAM Module
module "iam" {
  source = "./modules/iam"

  project_id = var.project_id
  
  depends_on = [google_project_service.apis]
}

# Networking
module "networking" {
  source = "./modules/networking"

  project_id = var.project_id
  region     = var.region

  depends_on = [google_project_service.apis]
}

# Artifact Registry
module "artifact_registry" {
  source = "./modules/artifact_registry"

  project_id = var.project_id
  region     = var.region

  depends_on = [google_project_service.apis]
}

# Secret Manager
module "secrets" {
  source = "./modules/secrets"

  project_id     = var.project_id
  gemini_api_key = var.gemini_api_key
  db_password    = var.db_password
  
  # Pass service account email
  service_account_email = module.iam.service_account_email

  depends_on = [google_project_service.apis, module.iam]
}

# Cloud SQL
module "cloud_sql" {
  source = "./modules/cloud_sql"

  project_id         = var.project_id
  region             = var.region
  db_password        = var.db_password
  vpc_network_id     = module.networking.vpc_network_id
  private_ip_address = module.networking.private_ip_address

  depends_on = [
    google_project_service.apis,
    module.networking,
  ]
}

# Cloud Storage
module "storage" {
  source = "./modules/storage"

  project_id = var.project_id
  region     = var.region

  # Pass service account email
  service_account_email = module.iam.service_account_email

  depends_on = [google_project_service.apis, module.iam]
}
