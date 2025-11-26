# Janua Infrastructure - Hetzner + Cloudflare Configuration
# Cost-effective alternative to AWS (~$50/month vs $500+/month)
# Pairs with Enclii's infrastructure for unified madfam platform

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.20"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Store state in Cloudflare R2 (same as Enclii)
  backend "s3" {
    bucket                      = "janua-terraform-state"
    key                         = "production/terraform.tfstate"
    region                      = "auto"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
  }
}

# =============================================================================
# PROVIDERS
# =============================================================================

provider "hcloud" {
  token = var.hetzner_token
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# =============================================================================
# DATA SOURCES
# =============================================================================

data "cloudflare_zone" "main" {
  name = var.domain
}

# =============================================================================
# NETWORKING
# =============================================================================

resource "hcloud_network" "janua" {
  name     = "janua-network"
  ip_range = "10.1.0.0/16"  # Different range from Enclii (10.0.0.0/16)
}

resource "hcloud_network_subnet" "app" {
  network_id   = hcloud_network.janua.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = "10.1.1.0/24"
}

resource "hcloud_network_subnet" "database" {
  network_id   = hcloud_network.janua.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = "10.1.2.0/24"
}

# =============================================================================
# FIREWALL
# =============================================================================

resource "hcloud_firewall" "janua" {
  name = "janua-firewall"

  # SSH (management only)
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.management_ips
  }

  # Internal network
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "any"
    source_ips = ["10.1.0.0/16"]
  }

  rule {
    direction  = "in"
    protocol   = "udp"
    port       = "any"
    source_ips = ["10.1.0.0/16"]
  }

  # Outbound
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "any"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction       = "out"
    protocol        = "udp"
    port            = "any"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction       = "out"
    protocol        = "icmp"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }
}

# =============================================================================
# SSH KEY
# =============================================================================

resource "tls_private_key" "ssh" {
  algorithm = "ED25519"
}

resource "hcloud_ssh_key" "janua" {
  name       = "janua-terraform"
  public_key = tls_private_key.ssh.public_key_openssh
}

# =============================================================================
# APPLICATION SERVERS
# =============================================================================

resource "hcloud_server" "api" {
  count       = var.api_server_count
  name        = "janua-api-${count.index + 1}"
  server_type = var.api_server_type
  image       = "ubuntu-22.04"
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.janua.id]
  firewall_ids = [hcloud_firewall.janua.id]

  labels = {
    role        = "api"
    environment = var.environment
    managed_by  = "terraform"
  }

  network {
    network_id = hcloud_network.janua.id
    ip         = "10.1.1.${10 + count.index}"
  }

  user_data = templatefile("${path.module}/templates/janua-api.yaml", {
    node_name       = "janua-api-${count.index + 1}"
    database_url    = "postgresql://${var.db_user}:${random_password.postgres.result}@10.1.2.10:5432/janua"
    redis_url       = "redis://:${random_password.redis.result}@10.1.2.20:6379"
    jwt_secret      = random_password.jwt_secret.result
    api_domain      = "auth.${var.domain}"
    environment     = var.environment
  })

  depends_on = [hcloud_network_subnet.app]
}

# =============================================================================
# DATABASE SERVER (PostgreSQL)
# =============================================================================

resource "hcloud_server" "postgres" {
  name        = "janua-postgres"
  server_type = var.db_server_type
  image       = "ubuntu-22.04"
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.janua.id]
  firewall_ids = [hcloud_firewall.janua.id]

  labels = {
    role        = "database"
    environment = var.environment
    managed_by  = "terraform"
  }

  network {
    network_id = hcloud_network.janua.id
    ip         = "10.1.2.10"
  }

  user_data = templatefile("${path.module}/templates/postgres.yaml", {
    postgres_password = random_password.postgres.result
    postgres_user     = var.db_user
    postgres_db       = "janua"
  })

  depends_on = [hcloud_network_subnet.database]
}

# Database volume
resource "hcloud_volume" "postgres_data" {
  name      = "janua-postgres-data"
  size      = var.db_volume_size
  location  = var.location
  format    = "ext4"

  labels = {
    purpose     = "database"
    environment = var.environment
  }
}

resource "hcloud_volume_attachment" "postgres_data" {
  volume_id = hcloud_volume.postgres_data.id
  server_id = hcloud_server.postgres.id
  automount = true
}

# =============================================================================
# REDIS SERVER
# =============================================================================

resource "hcloud_server" "redis" {
  name        = "janua-redis"
  server_type = var.redis_server_type
  image       = "ubuntu-22.04"
  location    = var.location
  ssh_keys    = [hcloud_ssh_key.janua.id]
  firewall_ids = [hcloud_firewall.janua.id]

  labels = {
    role        = "cache"
    environment = var.environment
    managed_by  = "terraform"
  }

  network {
    network_id = hcloud_network.janua.id
    ip         = "10.1.2.20"
  }

  user_data = templatefile("${path.module}/templates/redis.yaml", {
    redis_password = random_password.redis.result
  })

  depends_on = [hcloud_network_subnet.database]
}

# =============================================================================
# SECRETS
# =============================================================================

resource "random_password" "postgres" {
  length  = 32
  special = false
}

resource "random_password" "redis" {
  length  = 32
  special = false
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

resource "random_password" "session_secret" {
  length  = 32
  special = true
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "api_server_ips" {
  description = "API server IPs"
  value = {
    public  = hcloud_server.api[*].ipv4_address
    private = [for s in hcloud_server.api : s.network[0].ip]
  }
}

output "postgres_ip" {
  description = "PostgreSQL server private IP"
  value       = hcloud_server.postgres.network[0].ip
}

output "redis_ip" {
  description = "Redis server private IP"
  value       = hcloud_server.redis.network[0].ip
}

output "ssh_private_key" {
  description = "SSH private key"
  value       = tls_private_key.ssh.private_key_openssh
  sensitive   = true
}

output "postgres_password" {
  description = "PostgreSQL password"
  value       = random_password.postgres.result
  sensitive   = true
}

output "redis_password" {
  description = "Redis password"
  value       = random_password.redis.result
  sensitive   = true
}

output "jwt_secret" {
  description = "JWT signing secret"
  value       = random_password.jwt_secret.result
  sensitive   = true
}

output "database_url" {
  description = "Full database connection URL"
  value       = "postgresql://${var.db_user}:${random_password.postgres.result}@10.1.2.10:5432/janua"
  sensitive   = true
}

output "redis_url" {
  description = "Full Redis connection URL"
  value       = "redis://:${random_password.redis.result}@10.1.2.20:6379"
  sensitive   = true
}
