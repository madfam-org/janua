# Janua Infrastructure Variables
# ==============================

# =============================================================================
# PROVIDER CREDENTIALS
# =============================================================================

variable "hetzner_token" {
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with Zone and Tunnel permissions"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID for tunnels and R2"
  type        = string
}

# =============================================================================
# ENVIRONMENT
# =============================================================================

variable "environment" {
  description = "Deployment environment (production, staging)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging"], var.environment)
    error_message = "Environment must be production or staging."
  }
}

variable "domain" {
  description = "Root domain for Janua services"
  type        = string
  default     = "madfam.io"
}

variable "location" {
  description = "Hetzner datacenter location"
  type        = string
  default     = "nbg1" # Nuremberg, Germany - low latency for EU

  validation {
    condition     = contains(["nbg1", "fsn1", "hel1", "ash"], var.location)
    error_message = "Location must be a valid Hetzner datacenter."
  }
}

# =============================================================================
# SERVER CONFIGURATION
# =============================================================================

variable "api_server_count" {
  description = "Number of API servers"
  type        = number
  default     = 2

  validation {
    condition     = var.api_server_count >= 1 && var.api_server_count <= 5
    error_message = "API server count must be between 1 and 5."
  }
}

variable "api_server_type" {
  description = "Hetzner server type for API servers"
  type        = string
  default     = "cpx11" # 2 vCPU, 2GB RAM, €4.55/month

  validation {
    condition     = can(regex("^(cpx|cx|ccx)", var.api_server_type))
    error_message = "Server type must be a valid Hetzner cloud server type."
  }
}

variable "db_server_type" {
  description = "Hetzner server type for PostgreSQL"
  type        = string
  default     = "cpx21" # 3 vCPU, 4GB RAM, €8.39/month

  validation {
    condition     = can(regex("^(cpx|cx|ccx)", var.db_server_type))
    error_message = "Server type must be a valid Hetzner cloud server type."
  }
}

variable "redis_server_type" {
  description = "Hetzner server type for Redis"
  type        = string
  default     = "cpx11" # 2 vCPU, 2GB RAM, €4.55/month
}

variable "db_volume_size" {
  description = "PostgreSQL data volume size in GB"
  type        = number
  default     = 20

  validation {
    condition     = var.db_volume_size >= 10 && var.db_volume_size <= 1000
    error_message = "Volume size must be between 10 and 1000 GB."
  }
}

# =============================================================================
# DATABASE
# =============================================================================

variable "db_user" {
  description = "PostgreSQL admin username"
  type        = string
  default     = "janua"
}

# =============================================================================
# NETWORKING
# =============================================================================

variable "management_ips" {
  description = "IPs allowed SSH access (CIDR notation)"
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for ip in var.management_ips : can(cidrhost(ip, 0))
    ])
    error_message = "All management IPs must be valid CIDR blocks."
  }
}

# =============================================================================
# CLOUDFLARE TUNNEL
# =============================================================================

variable "tunnel_secret" {
  description = "Cloudflare Tunnel secret (generate with: cloudflared tunnel create)"
  type        = string
  sensitive   = true
  default     = ""
}

# =============================================================================
# ENCLII INTEGRATION
# =============================================================================

variable "enclii_oauth_client_id" {
  description = "OAuth client ID registered with Enclii"
  type        = string
  default     = ""
}

variable "enclii_oauth_client_secret" {
  description = "OAuth client secret for Enclii integration"
  type        = string
  sensitive   = true
  default     = ""
}

# =============================================================================
# COST REFERENCE (as of 2025)
# =============================================================================
#
# Server Costs (monthly):
#   cpx11 x2 (API):     €9.10
#   cpx21 x1 (Postgres): €8.39
#   cpx11 x1 (Redis):   €4.55
#   Volume 20GB:        €0.96
#   ────────────────────────
#   Total:              ~€23/month
#
# Cloudflare (Free tier):
#   Tunnel:             Free
#   DNS:                Free
#   Zero Trust (50):    Free
#
# Total estimated:      ~€25-30/month
# =============================================================================
