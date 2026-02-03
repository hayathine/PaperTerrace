resource "google_cloud_tasks_queue" "analysis_queue" {
  name     = "paper-analysis-queue"
  location = var.region

  rate_limits {
    max_dispatches_per_second = 5
    max_concurrent_dispatches = 10
  }

  retry_config {
    max_attempts       = 5
    max_backoff        = "3600s"
    min_backoff        = "5s"
    max_doublings      = 5
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}
