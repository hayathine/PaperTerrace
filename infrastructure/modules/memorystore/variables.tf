variable "instance_name" {
  description = "Redis instance name"
  type        = string
}

variable "tier" {
  description = "Redis tier (BASIC or STANDARD_HA)"
  type        = string
  default     = "STANDARD_HA"
  
  validation {
    condition     = contains(["BASIC", "STANDARD_HA"], var.tier)
    error_message = "Tier must be either BASIC or STANDARD_HA."
  }
}

variable "memory_size_gb" {
  description = "Memory size in GB"
  type        = number
  default     = 2
  
  validation {
    condition     = var.memory_size_gb >= 1 && var.memory_size_gb <= 300
    error_message = "Memory size must be between 1 and 300 GB."
  }
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "vpc_network_id" {
  description = "VPC network ID"
  type        = string
}

variable "display_name" {
  description = "Display name for the instance"
  type        = string
}

variable "labels" {
  description = "Labels to apply to the instance"
  type        = map(string)
  default     = {}
}