# Artifact Registry Module

resource "google_artifact_registry_repository" "main" {
  project       = var.project_id
  location      = var.region
  repository_id = "paperterrace"
  description   = "Docker repository for PaperTerrace"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 days
    }
  }
}

# IAM for Cloud Build to push images
resource "google_artifact_registry_repository_iam_member" "cloud_build" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.main.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${var.project_id}@cloudbuild.gserviceaccount.com"
}
