#!/bin/bash
# Database backup script for Janua
# Called by .github/workflows/backup.yml
#
# Required environment variables:
#   DB_HOST     - PostgreSQL host
#   DB_NAME     - Database name
#   DB_USER     - Database username
#   DB_PASSWORD - Database password
#   DB_PORT     - Database port (default: 5432)
#
# Optional environment variables:
#   S3_BUCKET           - S3 bucket for backup storage
#   ENVIRONMENT         - Environment name (default: production)
#   ALERT_WEBHOOK_URL   - Slack webhook for alerts
#   METRICS_ENDPOINT    - Metrics endpoint URL
#   VERIFY_RESTORE      - Whether to verify backup (default: false)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
DB_PORT="${DB_PORT:-5432}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/backups"
BACKUP_FILE="janua_${ENVIRONMENT}_${TIMESTAMP}.sql.gz"

log_info "Starting database backup..."
log_info "Environment: ${ENVIRONMENT}"
log_info "Database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
log_info "Timestamp: ${TIMESTAMP}"

# Validate required variables
if [ -z "${DB_HOST:-}" ]; then
    log_error "DB_HOST is not set"
    exit 1
fi

if [ -z "${DB_NAME:-}" ]; then
    log_error "DB_NAME is not set"
    exit 1
fi

if [ -z "${DB_USER:-}" ]; then
    log_error "DB_USER is not set"
    exit 1
fi

if [ -z "${DB_PASSWORD:-}" ]; then
    log_error "DB_PASSWORD is not set"
    exit 1
fi

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Perform backup
log_info "Creating backup: ${BACKUP_FILE}"
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --verbose \
    2>&1 | tee "${BACKUP_DIR}/backup.log" \
    > "${BACKUP_DIR}/${BACKUP_FILE}"

# Check backup was created
if [ ! -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    log_error "Backup file was not created"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
log_info "Backup created: ${BACKUP_FILE} (${BACKUP_SIZE})"

# Upload to S3 if configured
if [ -n "${S3_BUCKET:-}" ]; then
    log_info "Uploading to S3: s3://${S3_BUCKET}/backups/${BACKUP_FILE}"

    if command -v aws &> /dev/null; then
        aws s3 cp "${BACKUP_DIR}/${BACKUP_FILE}" "s3://${S3_BUCKET}/backups/${BACKUP_FILE}"
        log_info "Upload complete"

        # Cleanup old backups (keep last 30 days)
        log_info "Cleaning up old backups..."
        CUTOFF_DATE=$(date -d "30 days ago" +%Y-%m-%d 2>/dev/null || date -v-30d +%Y-%m-%d)
        aws s3 ls "s3://${S3_BUCKET}/backups/" | while read -r line; do
            FILE_DATE=$(echo "$line" | awk '{print $1}')
            FILE_NAME=$(echo "$line" | awk '{print $4}')
            if [[ "${FILE_DATE}" < "${CUTOFF_DATE}" ]]; then
                log_info "Deleting old backup: ${FILE_NAME}"
                aws s3 rm "s3://${S3_BUCKET}/backups/${FILE_NAME}"
            fi
        done
    else
        log_warn "AWS CLI not installed - skipping S3 upload"
    fi
else
    log_warn "S3_BUCKET not configured - backup stored locally only"
fi

# Verify backup if requested
if [ "${VERIFY_RESTORE:-true}" = "true" ]; then
    log_info "Verifying backup integrity..."
    pg_restore --list "${BACKUP_DIR}/${BACKUP_FILE}" > /dev/null
    log_info "Backup verification passed"
fi

# Send metrics if endpoint configured
if [ -n "${METRICS_ENDPOINT:-}" ]; then
    log_info "Sending metrics..."
    BACKUP_SIZE_BYTES=$(stat -f%z "${BACKUP_DIR}/${BACKUP_FILE}" 2>/dev/null || stat -c%s "${BACKUP_DIR}/${BACKUP_FILE}")
    curl -s -X POST "${METRICS_ENDPOINT}" \
        -H "Content-Type: application/json" \
        -d "{\"metric\":\"backup_size_bytes\",\"value\":${BACKUP_SIZE_BYTES},\"environment\":\"${ENVIRONMENT}\"}" \
        || log_warn "Failed to send metrics"
fi

# Cleanup local backup
rm -f "${BACKUP_DIR}/${BACKUP_FILE}"
log_info "Local backup cleaned up"

log_info "Backup completed successfully"
echo "::notice::Backup completed: ${BACKUP_FILE} (${BACKUP_SIZE})"
