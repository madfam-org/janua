#!/bin/bash
# Complete Enterprise Readiness and Validation Pipeline
# Runs all validation scripts and generates comprehensive report

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
OUTPUT_DIR="${OUTPUT_DIR:-validation-reports}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_DIR="$OUTPUT_DIR/$TIMESTAMP"

# Create output directory
mkdir -p "$REPORT_DIR"

echo -e "${PURPLE}================================================================${NC}"
echo -e "${PURPLE}🏢 ENTERPRISE READINESS & VALIDATION PIPELINE${NC}"
echo -e "${PURPLE}================================================================${NC}"
echo ""
echo -e "${BLUE}Target API:${NC} $API_URL"
echo -e "${BLUE}Output Directory:${NC} $REPORT_DIR"
echo -e "${BLUE}Timestamp:${NC} $TIMESTAMP"
echo ""

# Track overall results
TOTAL_VALIDATIONS=0
PASSED_VALIDATIONS=0
FAILED_VALIDATIONS=0

run_validation() {
    local name="$1"
    local command="$2"
    local output_file="$3"

    echo -e "${YELLOW}🔍 Running $name...${NC}"
    ((TOTAL_VALIDATIONS++))

    if eval "$command" > "$REPORT_DIR/$output_file" 2>&1; then
        echo -e "${GREEN}✅ $name: PASSED${NC}"
        ((PASSED_VALIDATIONS++))
        return 0
    else
        echo -e "${RED}❌ $name: FAILED${NC}"
        ((FAILED_VALIDATIONS++))
        return 1
    fi
}

run_python_validation() {
    local name="$1"
    local script="$2"
    local output_file="$3"

    echo -e "${YELLOW}🔍 Running $name...${NC}"
    ((TOTAL_VALIDATIONS++))

    if python3 "$script" --url "$API_URL" --output "$REPORT_DIR/${output_file%.txt}.json" > "$REPORT_DIR/$output_file" 2>&1; then
        echo -e "${GREEN}✅ $name: PASSED${NC}"
        ((PASSED_VALIDATIONS++))
        return 0
    else
        echo -e "${RED}❌ $name: FAILED${NC}"
        ((FAILED_VALIDATIONS++))
        return 1
    fi
}

# Wait for API to be ready
echo -e "${BLUE}⏳ Waiting for API to be ready...${NC}"
for i in {1..30}; do
    if curl -s "$API_URL/api/v1/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ API is ready${NC}"
        break
    fi

    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ API not responding after 30 attempts${NC}"
        echo -e "${RED}Please ensure the API is running at $API_URL${NC}"
        exit 1
    fi

    echo -e "${YELLOW}Attempt $i/30: API not ready, waiting...${NC}"
    sleep 2
done

echo ""
echo -e "${PURPLE}🚀 Starting Validation Pipeline...${NC}"
echo ""

# 1. Enterprise Readiness Validation
run_python_validation \
    "Enterprise Readiness Assessment" \
    "scripts/validate-enterprise-readiness.py" \
    "enterprise-readiness.txt"

# 2. Security and Compliance Audit
run_python_validation \
    "Security & Compliance Audit" \
    "scripts/security-compliance-audit.py" \
    "security-compliance.txt"

# 3. Deployment Validation
run_validation \
    "Deployment Validation" \
    "scripts/validate-deployment.sh --url $API_URL" \
    "deployment-validation.txt"

# 4. Enterprise Onboarding Readiness
run_python_validation \
    "Enterprise Onboarding Readiness" \
    "scripts/enterprise-onboarding-validation.py" \
    "onboarding-readiness.txt"

# 5. API Test Suite (if available)
if [ -f "apps/api/tests/test_enterprise_readiness.py" ]; then
    echo -e "${YELLOW}🔍 Running API Test Suite...${NC}"
    ((TOTAL_VALIDATIONS++))

    if cd apps/api && python -m pytest tests/test_enterprise_readiness.py -v --tb=short > "$REPORT_DIR/api-tests.txt" 2>&1; then
        echo -e "${GREEN}✅ API Test Suite: PASSED${NC}"
        ((PASSED_VALIDATIONS++))
        cd - > /dev/null
    else
        echo -e "${RED}❌ API Test Suite: FAILED${NC}"
        ((FAILED_VALIDATIONS++))
        cd - > /dev/null
    fi
else
    echo -e "${YELLOW}⚠️  API Test Suite: SKIPPED (not found)${NC}"
fi

# Generate comprehensive report
echo ""
echo -e "${PURPLE}📊 Generating Comprehensive Report...${NC}"

cat > "$REPORT_DIR/comprehensive-report.md" << EOF
# Enterprise Readiness Validation Report

**Generated:** $(date)
**API Endpoint:** $API_URL
**Report ID:** $TIMESTAMP

## Executive Summary

- **Total Validations:** $TOTAL_VALIDATIONS
- **Passed:** $PASSED_VALIDATIONS
- **Failed:** $FAILED_VALIDATIONS
- **Success Rate:** $(( (PASSED_VALIDATIONS * 100) / TOTAL_VALIDATIONS ))%

## Validation Results

### 1. Enterprise Readiness Assessment
EOF

if [ -f "$REPORT_DIR/enterprise-readiness.json" ]; then
    if command -v jq >/dev/null 2>&1; then
        echo "**Overall Score:** $(jq -r '.overall_score' "$REPORT_DIR/enterprise-readiness.json")%" >> "$REPORT_DIR/comprehensive-report.md"
        echo "**Enterprise Ready:** $(jq -r '.enterprise_ready' "$REPORT_DIR/enterprise-readiness.json")" >> "$REPORT_DIR/comprehensive-report.md"
    fi
fi

cat >> "$REPORT_DIR/comprehensive-report.md" << EOF

See: \`enterprise-readiness.txt\` and \`enterprise-readiness.json\`

### 2. Security & Compliance Audit
EOF

if [ -f "$REPORT_DIR/security-compliance.json" ]; then
    if command -v jq >/dev/null 2>&1; then
        echo "**Security Score:** $(jq -r '.security_score' "$REPORT_DIR/security-compliance.json")%" >> "$REPORT_DIR/comprehensive-report.md"
        echo "**Compliance Score:** $(jq -r '.compliance_score' "$REPORT_DIR/security-compliance.json")%" >> "$REPORT_DIR/comprehensive-report.md"
    fi
fi

cat >> "$REPORT_DIR/comprehensive-report.md" << EOF

See: \`security-compliance.txt\` and \`security-compliance.json\`

### 3. Deployment Validation

See: \`deployment-validation.txt\`

### 4. Enterprise Onboarding Readiness
EOF

if [ -f "$REPORT_DIR/onboarding-readiness.json" ]; then
    if command -v jq >/dev/null 2>&1; then
        echo "**Readiness Score:** $(jq -r '.readiness_score' "$REPORT_DIR/onboarding-readiness.json")%" >> "$REPORT_DIR/comprehensive-report.md"
        echo "**Onboarding Ready:** $(jq -r '.onboarding_readiness' "$REPORT_DIR/onboarding-readiness.json")" >> "$REPORT_DIR/comprehensive-report.md"
    fi
fi

cat >> "$REPORT_DIR/comprehensive-report.md" << EOF

See: \`onboarding-readiness.txt\` and \`onboarding-readiness.json\`

### 5. API Test Suite

See: \`api-tests.txt\`

## Next Steps

Based on the validation results:

1. **If all validations passed:** Ready for enterprise customer engagement
2. **If some validations failed:** Address critical issues before enterprise deployment
3. **Review detailed reports** for specific recommendations and action items

## Files in this Report

- \`comprehensive-report.md\` - This summary report
- \`enterprise-readiness.txt/json\` - Detailed enterprise readiness assessment
- \`security-compliance.txt/json\` - Security and compliance audit results
- \`deployment-validation.txt\` - Deployment readiness validation
- \`onboarding-readiness.txt/json\` - Enterprise onboarding readiness
- \`api-tests.txt\` - API test suite results (if available)

EOF

# Create summary JSON
cat > "$REPORT_DIR/summary.json" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "api_url": "$API_URL",
  "report_id": "$TIMESTAMP",
  "total_validations": $TOTAL_VALIDATIONS,
  "passed_validations": $PASSED_VALIDATIONS,
  "failed_validations": $FAILED_VALIDATIONS,
  "success_rate": $(( (PASSED_VALIDATIONS * 100) / TOTAL_VALIDATIONS )),
  "overall_status": "$([ $FAILED_VALIDATIONS -eq 0 ] && echo "READY" || echo "NOT_READY")"
}
EOF

# Print final summary
echo ""
echo -e "${PURPLE}================================================================${NC}"
echo -e "${PURPLE}📊 VALIDATION PIPELINE COMPLETE${NC}"
echo -e "${PURPLE}================================================================${NC}"
echo ""
echo -e "${BLUE}📈 Results Summary:${NC}"
echo -e "  Total Validations: $TOTAL_VALIDATIONS"
echo -e "  ✅ Passed: $PASSED_VALIDATIONS"
echo -e "  ❌ Failed: $FAILED_VALIDATIONS"
echo -e "  📊 Success Rate: $(( (PASSED_VALIDATIONS * 100) / TOTAL_VALIDATIONS ))%"
echo ""

if [ $FAILED_VALIDATIONS -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL VALIDATIONS PASSED${NC}"
    echo -e "${GREEN}✅ Ready for Enterprise Deployment${NC}"
    FINAL_STATUS=0
else
    echo -e "${RED}⚠️  SOME VALIDATIONS FAILED${NC}"
    echo -e "${RED}🔧 Address issues before enterprise deployment${NC}"
    FINAL_STATUS=1
fi

echo ""
echo -e "${BLUE}📁 Report Location:${NC} $REPORT_DIR"
echo -e "${BLUE}📋 Summary Report:${NC} $REPORT_DIR/comprehensive-report.md"
echo ""
echo -e "${PURPLE}================================================================${NC}"

exit $FINAL_STATUS