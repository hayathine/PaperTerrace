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
    "run.googleapis.com",
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

# IAM Module (New)
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

# Cloud Run
module "cloud_run" {
  source = "./modules/cloud_run"

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

  # Pass service account email
  service_account_email = module.iam.service_account_email

  # Pass new variables explicitly (optional since defaults are set)
  service_name         = "paperterrace"
  min_instance_count   = local.resources.backend.min_instances
  max_instance_count   = local.resources.backend.max_instances
  cpu                  = local.resources.backend.cpu
  memory               = local.resources.backend.memory
  concurrency          = local.resources.backend.concurrency

  # Redis configuration (Disabled to save cost)
  # redis_host = module.redis_production.redis_host
  # redis_port = tostring(module.redis_production.redis_port)

  depends_on = [
    google_project_service.apis,
    module.cloud_sql,
    module.secrets,
    module.storage,
    module.networking,
    module.iam,
    # module.redis_production, # Disabled
  ]
}

# ============================================================================
# Staging Environment
# ============================================================================

# Staging Database (Creates a new DB in the SAME instance)
resource "google_sql_database" "staging" {
  count    = var.enable_staging ? 1 : 0
  name     = "paperterrace_staging"
  instance = module.cloud_sql.instance_name
  project  = var.project_id
}

# Get Inference Service URL (Service B) for proper linking
# data "google_cloud_run_v2_service" "inference_staging" {
#   count    = var.enable_staging ? 1 : 0
#   name     = "paperterrace-inference-staging"
#   location = var.region
#   project  = var.project_id
# }

# Staging Cloud Run Service
module "cloud_run_staging" {
  source = "./modules/cloud_run"
  count  = var.enable_staging ? 1 : 0

  project_id               = var.project_id
  region                   = var.region
  image_url                = var.image_url # Share same image or use different tag if needed
  subnet_name              = module.networking.subnet_name
  vpc_network_name         = module.networking.vpc_network_name
  cloud_sql_connection     = module.cloud_sql.connection_name
  gemini_api_key_secret_id = module.secrets.gemini_api_key_secret_id
  db_password_secret_id    = module.secrets.db_password_secret_id
  storage_bucket           = module.storage.bucket_name
  db_host                  = module.cloud_sql.private_ip
  
  # Staging Specific Config
  service_name          = "paperterrace-staging"
  db_name               = google_sql_database.staging[0].name
  db_user               = module.cloud_sql.database_user # Share same user
  min_instance_count    = local.resources.backend_staging.min_instances
  max_instance_count    = local.resources.backend_staging.max_instances
  cpu                  = local.resources.backend_staging.cpu
  memory               = local.resources.backend_staging.memory
  concurrency          = local.resources.backend_staging.concurrency

  # Pass service account email
  service_account_email = module.iam.service_account_email

  # Redis configuration for staging (Disabled to save cost)
  # redis_host = var.enable_staging ? module.redis_staging[0].redis_host : "localhost"
  # redis_port = var.enable_staging ? tostring(module.redis_staging[0].redis_port) : "6379"

  # Inference Service Integration
  # inference_service_url = var.enable_staging ? data.google_cloud_run_v2_service.inference_staging[0].uri : ""
  inference_service_url = ""

  depends_on = [
    google_project_service.apis,
    module.cloud_sql,
    module.secrets,
    module.storage,
    module.networking,
    module.iam,
    google_sql_database.staging,
    # module.redis_staging, # Disabled
  ]
}

# ============================================================================
# Redis (Memorystore) - DISABLED TO SAVE COST
# ============================================================================

# Production Redis
# module "redis_production" {
#   source = "./modules/memorystore"
#
#   instance_name    = "paperterrace-redis-prod"
#   tier            = "Basic"
#   memory_size_gb  = 1
#   region          = var.region
#   vpc_network_id  = module.networking.vpc_network_id
#   display_name    = "PaperTerrace Production Redis"
#   
#   labels = {
#     environment = "production"
#     application = "paperterrace"
#   }
#
#   depends_on = [
#     google_project_service.apis,
#     module.networking
#   ]
# }

# Staging Redis (conditional)
# module "redis_staging" {
#   source = "./modules/memorystore"
#   count  = var.enable_staging ? 1 : 0
#
#   instance_name    = "paperterrace-redis-staging"
#   tier            = "BASIC"
#   memory_size_gb  = 1
#   region          = var.region
#   vpc_network_id  = module.networking.vpc_network_id
#   display_name    = "PaperTerrace Staging Redis"
#   
#   labels = {
#     environment = "staging"
#     application = "paperterrace"
#   }
#
#   depends_on = [
#     google_project_service.apis,
#     module.networking
#   ]
# }
