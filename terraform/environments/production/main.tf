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
    prefix = "terraform/state/production"
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

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "iam.googleapis.com", 
    "redis.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# IAM Module
module "iam" {
  source = "../../modules/iam"

  project_id = var.project_id
  
  depends_on = [google_project_service.apis]
}

# Networking
module "networking" {
  source = "../../modules/networking"

  project_id = var.project_id
  region     = var.region

  depends_on = [google_project_service.apis]
}

# Artifact Registry
module "artifact_registry" {
  source = "../../modules/artifact_registry"

  project_id = var.project_id
  region     = var.region

  depends_on = [google_project_service.apis]
}

# Secret Manager
module "secrets" {
  source = "../../modules/secrets"

  project_id     = var.project_id
  gemini_api_key = var.gemini_api_key
  db_password    = var.db_password
  
  service_account_email = module.iam.service_account_email

  depends_on = [google_project_service.apis, module.iam]
}

# Cloud SQL
module "cloud_sql" {
  source = "../../modules/cloud_sql"

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
  source = "../../modules/storage"

  project_id = var.project_id
  region     = var.region

  service_account_email = module.iam.service_account_email

  depends_on = [google_project_service.apis, module.iam]
}

# Redis Production
module "redis_production" {
  source = "../../modules/memorystore"

  instance_name    = "paperterrace-redis-prod"
  tier            = "STANDARD_HA"
  memory_size_gb  = 2
  region          = var.region
  vpc_network_id  = module.networking.vpc_network_id
  display_name    = "PaperTerrace Production Redis"
  
  labels = {
    environment = "production"
    application = "paperterrace"
  }

  depends_on = [
    google_project_service.apis,
    module.networking
  ]
}

# Cloud Run
module "cloud_run" {
  source = "../../modules/cloud_run"

  project_id               = var.project_id
  region                   = var.region
  image_url                = var.image_url
  subnet_name              = module.networking.subnet_name
  vpc_network_name         = module.networking.vpc_network_name
  cloud_sql_connection     = module.cloud_sql.connection_name
  gemini_api_key_secret_id = module.secrets.gemini_api_key_secret_id
  db_password_secret_id    = module.secrets.db_password_secret_id
  storage_bucket           = module.storage.bucket_name
  db_host                  = module.cloud_sql.private_ip
  db_name                  = module.cloud_sql.database_name
  db_user                  = module.cloud_sql.database_user

  service_account_email = module.iam.service_account_email

  service_name         = "paperterrace"
  min_instance_count   = 0

  redis_host = module.redis_production.redis_host
  redis_port = tostring(module.redis_production.redis_port)

  depends_on = [
    google_project_service.apis,
    module.cloud_sql,
    module.secrets,
    module.storage,
    module.networking,
    module.iam,
    module.redis_production,
  ]
}
