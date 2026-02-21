resource "google_redis_instance" "main" {
  name           = var.instance_name
  tier           = var.tier
  memory_size_gb = var.memory_size_gb
  region         = var.region
  
  authorized_network = var.vpc_network_id
  
  redis_version     = "REDIS_7_0"
  display_name      = var.display_name
  
  # バックアップ設定
  persistence_config {
    persistence_mode    = "RDB"
    rdb_snapshot_period = "TWENTY_FOUR_HOURS"
  }
  
  # メンテナンス設定
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
      }
    }
  }
  
  labels = var.labels
}