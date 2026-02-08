# Cloud Run Module

resource "google_cloud_run_v2_service" "main" {
  name     = var.service_name
  location = var.region
  project  = var.project_id

  template {
    service_account = var.service_account_email

    
    containers {
      image = var.image_url

      ports {
        container_port = 8000
        name = "http1"
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
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
        name  = "GCS_BUCKET_NAME"
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

/*
      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }

      env {
        name  = "REDIS_PORT"
        value = var.redis_port
      }

      env {
        name  = "REDIS_DB"
        value = "0"
      }
*/

      env {
        name  = "INFERENCE_SERVICE_URL"
        value = var.inference_service_url
      }

      env {
        name  = "BATCH_PARALLEL_WORKERS"
        value = tostring(var.batch_parallel_workers)
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
          path = "/api/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 12
      }

      liveness_probe {
        http_get {
          path = "/api/health"
        }
        period_seconds    = 30
        failure_threshold = 3
      }
    }

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    vpc_access {
      network_interfaces {
        network    = var.vpc_network_name
        subnetwork = var.subnet_name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }

    timeout = "300s"
    max_instance_request_concurrency = var.concurrency

    annotations = {
      "run.googleapis.com/cloudsql-instances" = var.cloud_sql_connection
      "run.googleapis.com/startup-cpu-boost" = "true"
      "run.googleapis.com/execution-environment" = "gen2"
      # アイドルタイムアウト設定（デフォルトは15分、最大60分）
      "autoscaling.knative.dev/maxScale" = tostring(var.max_instance_count)
      "run.googleapis.com/cpu-throttling" = "false"
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
