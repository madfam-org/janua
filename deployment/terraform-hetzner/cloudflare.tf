# Janua Cloudflare Configuration
# ==============================
# Cloudflare Tunnel for zero-trust ingress (no exposed ports)
# DNS records, SSL certificates, and Zero Trust Access policies

# =============================================================================
# CLOUDFLARE TUNNEL
# =============================================================================

resource "cloudflare_tunnel" "janua" {
  account_id = var.cloudflare_account_id
  name       = "janua-${var.environment}"
  secret     = var.tunnel_secret != "" ? base64encode(var.tunnel_secret) : base64encode(random_password.tunnel_secret.result)
}

resource "random_password" "tunnel_secret" {
  length  = 32
  special = false
}

# Tunnel configuration - routes traffic to internal services
resource "cloudflare_tunnel_config" "janua" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_tunnel.janua.id

  config {
    # Main auth API
    ingress_rule {
      hostname = "auth.${var.domain}"
      service  = "http://10.1.1.10:8000"
      origin_request {
        connect_timeout = "30s"
        no_tls_verify   = true
      }
    }

    # Admin dashboard
    ingress_rule {
      hostname = "auth-admin.${var.domain}"
      service  = "http://10.1.1.10:8000"
      path     = "/admin/*"
      origin_request {
        connect_timeout = "30s"
        no_tls_verify   = true
      }
    }

    # Health checks
    ingress_rule {
      hostname = "auth.${var.domain}"
      path     = "/health"
      service  = "http://10.1.1.10:8000"
    }

    # Catch-all (required by Cloudflare)
    ingress_rule {
      service = "http_status:404"
    }
  }
}

# =============================================================================
# DNS RECORDS
# =============================================================================

resource "cloudflare_record" "auth" {
  zone_id = data.cloudflare_zone.main.id
  name    = "auth"
  value   = "${cloudflare_tunnel.janua.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
  comment = "Janua auth API via Cloudflare Tunnel"
}

resource "cloudflare_record" "auth_admin" {
  zone_id = data.cloudflare_zone.main.id
  name    = "auth-admin"
  value   = "${cloudflare_tunnel.janua.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
  comment = "Janua admin dashboard via Cloudflare Tunnel"
}

# =============================================================================
# SSL/TLS CONFIGURATION
# =============================================================================

resource "cloudflare_zone_settings_override" "ssl" {
  zone_id = data.cloudflare_zone.main.id

  settings {
    ssl                      = "strict"
    always_use_https         = "on"
    min_tls_version          = "1.2"
    automatic_https_rewrites = "on"
    security_header {
      enabled            = true
      include_subdomains = true
      max_age            = 31536000
      preload            = true
    }
  }
}

# =============================================================================
# ZERO TRUST ACCESS (Admin Protection)
# =============================================================================

# Access application for admin dashboard
resource "cloudflare_access_application" "admin" {
  zone_id          = data.cloudflare_zone.main.id
  name             = "Janua Admin Dashboard"
  domain           = "auth-admin.${var.domain}"
  type             = "self_hosted"
  session_duration = "24h"

  allowed_idps = [cloudflare_access_identity_provider.github.id]
}

# GitHub identity provider for admin access
resource "cloudflare_access_identity_provider" "github" {
  zone_id = data.cloudflare_zone.main.id
  name    = "GitHub"
  type    = "github"
  config {
    client_id     = var.github_oauth_client_id
    client_secret = var.github_oauth_client_secret
  }
}

# Access policy - only allow specific GitHub users
resource "cloudflare_access_policy" "admin_policy" {
  zone_id        = data.cloudflare_zone.main.id
  application_id = cloudflare_access_application.admin.id
  name           = "Admin Users"
  precedence     = 1
  decision       = "allow"

  include {
    email = var.admin_emails
  }
}

# =============================================================================
# R2 BUCKET (for backups if needed)
# =============================================================================

resource "cloudflare_r2_bucket" "backups" {
  account_id = var.cloudflare_account_id
  name       = "janua-backups-${var.environment}"
  location   = "WEUR" # Western Europe
}

# =============================================================================
# ADDITIONAL VARIABLES FOR CLOUDFLARE
# =============================================================================

variable "github_oauth_client_id" {
  description = "GitHub OAuth client ID for Zero Trust Access"
  type        = string
  default     = ""
}

variable "github_oauth_client_secret" {
  description = "GitHub OAuth client secret for Zero Trust Access"
  type        = string
  sensitive   = true
  default     = ""
}

variable "admin_emails" {
  description = "Email addresses allowed to access admin dashboard"
  type        = list(string)
  default     = []
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "tunnel_id" {
  description = "Cloudflare Tunnel ID"
  value       = cloudflare_tunnel.janua.id
}

output "tunnel_token" {
  description = "Cloudflare Tunnel token for cloudflared"
  value       = cloudflare_tunnel.janua.tunnel_token
  sensitive   = true
}

output "auth_url" {
  description = "Janua auth API URL"
  value       = "https://auth.${var.domain}"
}

output "admin_url" {
  description = "Janua admin dashboard URL"
  value       = "https://auth-admin.${var.domain}"
}

output "r2_bucket_name" {
  description = "R2 bucket name for backups"
  value       = cloudflare_r2_bucket.backups.name
}
