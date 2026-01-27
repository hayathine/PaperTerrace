# Cloud Run Module

resource "google_cloud_run_v2_service" "main" {
  name     = "paperterrace"
  location = var.region
  project  = var.project_id

  template {
    containers {
      image = var.image_url

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      # Environment variables
      env {
        name  = "DB_HOST"
        value = var.db_host
      }

      env {
        name  = "DB_NAME"
        value = var.db_name
      }

      env {
        name  = "DB_USER"
        value = var.db_user
      }

      env {
        name  = "STORAGE_BUCKET"
        value = var.storage_bucket
      }

      env {
        name  = "AI_PROVIDER"
        value = "gemini"
      }

      env {
        name  = "STORAGE_PROVIDER"
        value = "cloudsql"
      }

      # Secrets from Secret Manager
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = var.gemini_api_key_secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.db_password_secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/"
        }
        period_seconds    = 30
        failure_threshold = 3
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    timeout = "300s"

    annotations = {
      "run.googleapis.com/cloudsql-instances" = var.cloud_sql_connection
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = {
    app         = "paperterrace"
    environment = "production"
  }
}

# Allow unauthenticated access
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.main.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
