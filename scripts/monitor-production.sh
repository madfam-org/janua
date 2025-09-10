#!/bin/bash

# Plinto Production Monitoring Script
# Run this manually or via cron to monitor all services

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
ALERT_WEBHOOK="${ALERT_WEBHOOK_URL:-}"
LOG_FILE="${LOG_FILE:-monitoring.log}"

# Services to monitor
declare -A SERVICES=(
    ["API Health"]="https://api.plinto.dev/health"
    ["Marketing Site"]="https://www.plinto.dev"
    ["Main App"]="https://app.plinto.dev"
    ["Documentation"]="https://docs.plinto.dev"
    ["Admin Panel"]="https://admin.plinto.dev"
    ["Demo App"]="https://demo.plinto.dev"
)

# Initialize counters
TOTAL_SERVICES=0
SERVICES_UP=0
SERVICES_DOWN=0
TOTAL_RESPONSE_TIME=0

echo "════════════════════════════════════════════════════════"
echo "     Plinto Production Monitoring - $(date)"
echo "════════════════════════════════════════════════════════"
echo ""

# Function to check a service
check_service() {
    local name=$1
    local url=$2
    local start_time=$(date +%s%N)
    
    TOTAL_SERVICES=$((TOTAL_SERVICES + 1))
    
    # Perform the check
    if response=$(curl -s -o /dev/null -w "%{http_code}:%{time_total}" --max-time 10 "$url" 2>/dev/null); then
        local http_code=$(echo $response | cut -d: -f1)
        local response_time=$(echo $response | cut -d: -f2)
        
        # Convert to milliseconds
        local response_time_ms=$(echo "$response_time * 1000" | bc | cut -d. -f1)
        TOTAL_RESPONSE_TIME=$(echo "$TOTAL_RESPONSE_TIME + $response_time" | bc)
        
        if [[ "$http_code" =~ ^(200|301|302|308)$ ]]; then
            echo -e "${GREEN}✅ $name${NC}"
            echo "   Status: $http_code | Response: ${response_time_ms}ms | URL: $url"
            SERVICES_UP=$((SERVICES_UP + 1))
            
            # Log success
            echo "$(date -u +"%Y-%m-%d %H:%M:%S") | UP | $name | ${response_time_ms}ms | $http_code" >> "$LOG_FILE"
        else
            echo -e "${YELLOW}⚠️  $name${NC}"
            echo "   Status: $http_code | Response: ${response_time_ms}ms | URL: $url"
            SERVICES_DOWN=$((SERVICES_DOWN + 1))
            
            # Log warning
            echo "$(date -u +"%Y-%m-%d %H:%M:%S") | WARN | $name | ${response_time_ms}ms | $http_code" >> "$LOG_FILE"
            
            # Send alert if webhook configured
            send_alert "WARNING" "$name returned HTTP $http_code"
        fi
    else
        echo -e "${RED}❌ $name${NC}"
        echo "   Status: TIMEOUT | URL: $url"
        SERVICES_DOWN=$((SERVICES_DOWN + 1))
        
        # Log failure
        echo "$(date -u +"%Y-%m-%d %H:%M:%S") | DOWN | $name | TIMEOUT | 0" >> "$LOG_FILE"
        
        # Send alert if webhook configured
        send_alert "CRITICAL" "$name is not responding"
    fi
    echo ""
}

# Function to send alerts
send_alert() {
    local severity=$1
    local message=$2
    
    if [ -n "$ALERT_WEBHOOK" ]; then
        curl -X POST "$ALERT_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"🚨 [$severity] $message\"}" \
            2>/dev/null || true
    fi
}

# Check API specific endpoints
check_api_endpoints() {
    echo "━━━ API Endpoint Checks ━━━"
    echo ""
    
    # Check auth status
    echo -n "Auth Router: "
    if curl -s "https://api.plinto.dev/api/v1/auth/status" | grep -q "auth router working"; then
        echo -e "${GREEN}Working${NC}"
    else
        echo -e "${RED}Not Working${NC}"
    fi
    
    # Check OpenAPI docs
    echo -n "API Documentation: "
    if curl -s "https://api.plinto.dev/openapi.json" | grep -q "Plinto API"; then
        echo -e "${GREEN}Available${NC}"
    else
        echo -e "${RED}Not Available${NC}"
    fi
    
    # Check database connectivity
    echo -n "Database Connection: "
    if curl -s "https://api.plinto.dev/ready" | grep -q '"database":true'; then
        echo -e "${GREEN}Connected${NC}"
    else
        echo -e "${RED}Not Connected${NC}"
    fi
    
    # Check Redis connectivity
    echo -n "Redis Connection: "
    if curl -s "https://api.plinto.dev/ready" | grep -q '"redis":true'; then
        echo -e "${GREEN}Connected${NC}"
    else
        echo -e "${RED}Not Connected${NC}"
    fi
    
    echo ""
}

# Check SSL certificates
check_ssl_certificates() {
    echo "━━━ SSL Certificate Status ━━━"
    echo ""
    
    for domain in api.plinto.dev www.plinto.dev app.plinto.dev; do
        echo -n "$domain: "
        if echo | openssl s_client -connect $domain:443 -servername $domain 2>/dev/null | openssl x509 -noout -checkend 604800 &>/dev/null; then
            # Certificate valid for at least 7 more days
            local expiry=$(echo | openssl s_client -connect $domain:443 -servername $domain 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
            echo -e "${GREEN}Valid${NC} (expires: $expiry)"
        else
            echo -e "${YELLOW}Expiring Soon${NC}"
            send_alert "WARNING" "SSL certificate for $domain expiring soon"
        fi
    done
    echo ""
}

# Main monitoring loop
echo "━━━ Service Health Checks ━━━"
echo ""

for service in "${!SERVICES[@]}"; do
    check_service "$service" "${SERVICES[$service]}"
done

# API-specific checks
check_api_endpoints

# SSL certificate checks
check_ssl_certificates

# Calculate statistics
if [ $TOTAL_SERVICES -gt 0 ]; then
    AVG_RESPONSE_TIME=$(echo "scale=2; $TOTAL_RESPONSE_TIME / $TOTAL_SERVICES * 1000" | bc)
    UPTIME_PERCENTAGE=$(echo "scale=2; $SERVICES_UP * 100 / $TOTAL_SERVICES" | bc)
else
    AVG_RESPONSE_TIME=0
    UPTIME_PERCENTAGE=0
fi

# Summary
echo "════════════════════════════════════════════════════════"
echo "                      SUMMARY                           "
echo "════════════════════════════════════════════════════════"
echo ""
echo "Services Monitored: $TOTAL_SERVICES"
echo -e "Services Up: ${GREEN}$SERVICES_UP${NC}"
if [ $SERVICES_DOWN -gt 0 ]; then
    echo -e "Services Down: ${RED}$SERVICES_DOWN${NC}"
else
    echo -e "Services Down: ${GREEN}$SERVICES_DOWN${NC}"
fi
echo "Average Response Time: ${AVG_RESPONSE_TIME}ms"
echo "Uptime: ${UPTIME_PERCENTAGE}%"
echo ""

# Overall status
if [ $SERVICES_DOWN -eq 0 ]; then
    echo -e "${GREEN}✅ All Systems Operational${NC}"
    EXIT_CODE=0
elif [ $SERVICES_DOWN -eq 1 ]; then
    echo -e "${YELLOW}⚠️  Partial Outage Detected${NC}"
    EXIT_CODE=1
else
    echo -e "${RED}❌ Multiple Services Down${NC}"
    EXIT_CODE=2
fi

echo ""
echo "Log file: $LOG_FILE"
echo "Next check recommended in 5 minutes"
echo ""

# Create status JSON for programmatic access
cat > status.json << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "services_total": $TOTAL_SERVICES,
  "services_up": $SERVICES_UP,
  "services_down": $SERVICES_DOWN,
  "average_response_time_ms": $AVG_RESPONSE_TIME,
  "uptime_percentage": $UPTIME_PERCENTAGE,
  "status": $([ $SERVICES_DOWN -eq 0 ] && echo '"operational"' || echo '"degraded"')
}
EOF

echo "Status JSON saved to: status.json"
echo "════════════════════════════════════════════════════════"

exit $EXIT_CODE