output "gemini_api_key_secret_id" {
  description = "Gemini API Key secret ID"
  value       = google_secret_manager_secret.gemini_api_key.secret_id
}

output "db_password_secret_id" {
  description = "Database password secret ID"
  value       = google_secret_manager_secret.db_password.secret_id
}
