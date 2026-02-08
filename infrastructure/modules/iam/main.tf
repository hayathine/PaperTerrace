resource "google_service_account" "app_sa" {
  account_id   = "paperterrace-sa"
  display_name = "PaperTerrace Application Service Account"
  project      = var.project_id
}

# Grant necessary roles to the service account
resource "google_project_iam_member" "cloud_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

# Optional: Add AI Platform User role if moving to Vertex AI later
resource "google_project_iam_member" "ai_platform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

# Allow service account to sign URLs using IAM
resource "google_project_iam_member" "token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}
