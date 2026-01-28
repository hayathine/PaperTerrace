output "service_account_email" {
  description = "Email of the creating service account"
  value       = google_service_account.app_sa.email
}
