output "bucket_name" {
  description = "Cloud Storage bucket name"
  value       = google_storage_bucket.papers.name
}

output "bucket_url" {
  description = "Cloud Storage bucket URL"
  value       = google_storage_bucket.papers.url
}
