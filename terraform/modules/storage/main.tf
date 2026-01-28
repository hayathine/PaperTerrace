# Cloud Storage Module

resource "google_storage_bucket" "papers" {
  name          = "paperterrace-papers"
  location      = var.region
  project       = var.project_id
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 3
    }
    action {
      type = "Delete"
    }
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  labels = {
    app         = "paperterrace"
    environment = "production"
  }
}

data "google_project" "project" {
  project_id = var.project_id
}

# IAM for Cloud Run service account to access bucket
resource "google_storage_bucket_iam_member" "cloud_run" {
  bucket = google_storage_bucket.papers.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}
