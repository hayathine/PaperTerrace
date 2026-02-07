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
    prefix = "terraform/state/staging"
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
  resources = jsondecode(file("${path.module}/../../../config/resources.json"))
}

# Read Production State
data "terraform_remote_state" "production" {
  backend = "gcs"
  config = {
    bucket = "gen-lang-client-0800253336-terraform-state"
    prefix = "terraform/state/production"
  }
}

# Staging Database Schema (Shared Instance)
resource "google_sql_database" "staging" {
  name     = "paperterrace_staging"
  instance = data.terraform_remote_state.production.outputs.cloud_sql_instance_name
  project  = var.project_id
}

/*
# Staging Redis
module "redis_staging" {
  source = "../../modules/memorystore"

  instance_name    = "paperterrace-redis-staging"
  tier            = "BASIC"
  memory_size_gb  = 1
  region          = var.region
  vpc_network_id  = data.terraform_remote_state.production.outputs.vpc_network_id
  display_name    = "PaperTerrace Staging Redis"
  
  labels = {
    environment = "staging"
    application = "paperterrace"
  }
}
*/

# Cloud Run Staging
module "cloud_run_staging" {
  source = "../../modules/cloud_run"

  project_id               = var.project_id
  region                   = var.region
  image_url                = var.image_url # Can be overridden via TF_VAR_image_url
  subnet_name              = data.terraform_remote_state.production.outputs.subnet_name
  vpc_network_name         = data.terraform_remote_state.production.outputs.vpc_network_name
  cloud_sql_connection     = data.terraform_remote_state.production.outputs.cloud_sql_connection_name
  gemini_api_key_secret_id = data.terraform_remote_state.production.outputs.gemini_api_key_secret_id
  db_password_secret_id    = data.terraform_remote_state.production.outputs.db_password_secret_id
  storage_bucket           = data.terraform_remote_state.production.outputs.storage_bucket_name
  db_host                  = data.terraform_remote_state.production.outputs.cloud_sql_private_ip
  
  # Staging Specifics
  service_name          = "paperterrace-staging"
  db_name               = google_sql_database.staging.name
  db_user               = data.terraform_remote_state.production.outputs.cloud_sql_db_user
  min_instance_count    = local.resources.backend_staging.min_instance_count
  max_instance_count    = local.resources.backend_staging.max_instances
  cpu                  = local.resources.backend_staging.cpu
  memory               = local.resources.backend_staging.memory
  concurrency          = local.resources.backend_staging.concurrency
  
  # Redis
  # redis_host = module.redis_staging.redis_host
  # redis_port = tostring(module.redis_staging.redis_port)

  service_account_email = data.terraform_remote_state.production.outputs.service_account_email
}
