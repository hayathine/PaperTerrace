resource "google_cloud_tasks_queue" "paper_analysis" {
  name     = var.queue_name
  location = var.region
  project  = var.project_id

  rate_limits {
    max_dispatches_per_second = 10
    max_concurrent_dispatches = 10
  }

  retry_config {
    max_attempts       = 5
    max_backoff        = "3600s"
    min_backoff        = "5s"
    max_doublings      = 16
    retry_count        = 0
  }
}
